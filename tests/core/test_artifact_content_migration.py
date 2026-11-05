import ast
import hashlib
import importlib.util
import inspect
import io
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.ext.compiler import compiles, deregister

from app.core.db.models import Base
from app.domain.models import DOMAIN_TABLES

VERSIONS = Path(__file__).resolve().parents[2] / "alembic" / "versions"


def load_migration(name):
    spec = importlib.util.spec_from_file_location(name, VERSIONS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def migration_database():
    # Execute migration operations only on an in-memory SQLite double. Its batch
    # table rebuilds differ from MySQL ALTER TABLE; this is not a MySQL DDL test.
    @compiles(LONGBLOB, "sqlite")
    def blob_double(element, compiler, **kwargs):
        return "BLOB"

    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            context = MigrationContext.configure(connection)
            old = load_migration("0001_integration_foundation")
            old.op = Operations(context)
            old.upgrade()
            connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
            connection.exec_driver_sql("INSERT INTO alembic_version VALUES ('0001_integration_foundation')")
            new = load_migration("0002_artifact_content_and_failure_stage")
            new.op = Operations(context)
            yield connection, new
    finally:
        engine.dispose()
        deregister(LONGBLOB)


def table(connection, name):
    return sa.Table(name, sa.MetaData(), autoload_with=connection)


def seed(connection, corrupt=False):
    now = datetime(2026, 9, 25, tzinfo=UTC).replace(tzinfo=None)
    connection.execute(table(connection, "integration_jobs").insert(), {
        "id": 41, "source_name": "NMVS", "channel_name": "Reporting API",
        "report_type": "DailySnapshot", "status": "succeeded", "created_at": now,
    })
    data = b"original report bytes\r\n"
    connection.execute(table(connection, "acquired_artifacts").insert(), {
        "id": 73, "integration_job_id": 41, "source_name": "NMVS", "channel_name": "Reporting API",
        "report_type": "DailySnapshot", "source_uri": "/reports/73", "content_type": "text/csv",
        "content_length": len(data), "sha256": "0" * 64 if corrupt else hashlib.sha256(data).hexdigest(),
        "report_metadata": {"source": "original", "used_api_version": "1"}, "received_at": now,
        "processing_status": "staged", "artifact_bytes": data, "created_at": now,
    })
    connection.execute(table(connection, "processing_runs").insert(), {
        "id": 101, "artifact_id": 73, "run_type": "initial_extraction", "parser_version": "1",
        "transform_version": "none", "status": "succeeded", "started_at": now,
    })
    connection.execute(table(connection, "staging_datasets").insert(), {
        "id": 202, "processing_run_id": 101, "artifact_id": 73, "source_dataset_name": "Products",
        "section_order": 1, "source_headers": ["Code"], "row_count": 1,
        "extraction_status": "extracted", "created_at": now,
    })
    connection.execute(table(connection, "staging_rows").insert(), {
        "id": 303, "staging_dataset_id": 202, "source_row_number": 1,
        "source_record_hash": "b" * 64, "raw_row_json": {"Code": "001"}, "created_at": now,
    })


def snapshot(connection, names):
    return {name: [dict(row) for row in connection.execute(sa.select(table(connection, name))).mappings()]
            for name in names}


@pytest.mark.parametrize("populated", [False, True])
def test_upgrade_matches_models_and_preserves_all_ids_and_provenance(migration_database, populated):
    connection, migration = migration_database
    if populated:
        seed(connection)
    names = ["integration_jobs", "acquired_artifacts", "processing_runs", "staging_datasets", "staging_rows"]
    before = snapshot(connection, names)
    migration.upgrade()
    expected = sa.MetaData()
    for model_table in Base.metadata.sorted_tables:
        if model_table.name not in DOMAIN_TABLES:
            model_table.to_metadata(expected)
    # This historical migration stops before the separately tested 0003 column.
    expected.tables["processing_runs"]._columns.remove(expected.tables["processing_runs"].c.file_metadata)
    run_table = expected.tables["processing_runs"]
    for constraint in list(run_table.foreign_key_constraints):
        if constraint.name == "fk_processing_runs_reused_from":
            run_table.constraints.remove(constraint)
    run_table._columns.remove(run_table.c.reused_from_run_id)
    for name in ("import_executions", "import_schedules", "import_mutexes"):
        expected.remove(expected.tables[name])
    assert compare_metadata(MigrationContext.configure(connection), expected) == []
    version_column = sa.inspect(connection).get_columns("alembic_version")[0]
    assert version_column["type"].length >= len(migration.revision)
    after = snapshot(connection, names)
    for name in names:
        if name not in {"integration_jobs", "acquired_artifacts"}:
            assert before[name] == after[name]
    if populated:
        old = before["acquired_artifacts"][0]
        new = after["acquired_artifacts"][0]
        content = snapshot(connection, ["artifact_contents"])["artifact_contents"][0]
        assert new["id"] == 73 and new["content_id"] == content["id"]
        moved = {"sha256", "content_length", "artifact_bytes"}
        assert {k: new[k] for k in old if k not in moved} == {k: v for k, v in old.items() if k not in moved}
        assert all(content[k] == old[k] for k in moved)
        assert after["integration_jobs"][0] == {**before["integration_jobs"][0], "failure_stage": None}
    assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    metadata_migration = load_migration("0003_file_metadata")
    metadata_migration.op = Operations(MigrationContext.configure(connection))
    metadata_migration.upgrade()
    scheduling_migration = load_migration("0004_import_scheduling")
    scheduling_migration.op = Operations(MigrationContext.configure(connection))
    scheduling_migration.upgrade()
    scheduling_expected = sa.MetaData()
    for model_table in Base.metadata.sorted_tables:
        if model_table.name not in DOMAIN_TABLES:
            model_table.to_metadata(scheduling_expected)
    scheduling_expected.tables["import_schedules"]._columns.remove(scheduling_expected.tables["import_schedules"].c.interval_seconds)
    assert compare_metadata(MigrationContext.configure(connection), scheduling_expected) == []
    domain_migration = load_migration("0005_product_batch_model_operational_product_batch_and_sai_")
    domain_migration.op = Operations(MigrationContext.configure(connection))
    domain_migration.upgrade()
    version_migration = load_migration("0006_source_version_values_retain_unresolved_source_version_values")
    version_migration.op = Operations(MigrationContext.configure(connection))
    version_migration.upgrade()
    participant_migration = load_migration("0007_snapshot_participants_local_organisations_and_locations")
    participant_migration.op = Operations(MigrationContext.configure(connection))
    participant_migration.upgrade()
    activity_migration = load_migration("0008_user_activity_daily_coverage_and_facts")
    activity_migration.op = Operations(MigrationContext.configure(connection))
    activity_migration.upgrade()
    measures_migration = load_migration("6edb61d37736_activity_pack_metrics_separate_from_")
    measures_migration.op = Operations(MigrationContext.configure(connection))
    measures_migration.upgrade()
    exception_migration = load_migration("0010_source_exceptions_and_retained_observations")
    exception_migration.op = Operations(MigrationContext.configure(connection))
    exception_migration.upgrade()
    precision_migration = load_migration("0011_exception_timestamp_precision")
    precision_migration.op = Operations(MigrationContext.configure(connection))
    precision_migration.upgrade()
    interval_migration = load_migration("0012_import_interval")
    interval_migration.op = Operations(MigrationContext.configure(connection))
    interval_migration.upgrade()
    pack_migration=load_migration("0013_pack_audit_evidence")
    pack_migration.op=Operations(MigrationContext.configure(connection))
    pack_migration.upgrade()
    upload_migration = load_migration("0014_pack_uploads")
    upload_migration.op = Operations(MigrationContext.configure(connection))
    upload_migration.upgrade()
    control_migration = load_migration("0015_import_management")
    control_migration.op = Operations(MigrationContext.configure(connection))
    control_migration.upgrade()
    review_migration = load_migration("0016_exception_reviews")
    review_migration.op = Operations(MigrationContext.configure(connection))
    review_migration.upgrade()
    structured_migration = load_migration("0017_structured_cause")
    structured_migration.op = Operations(MigrationContext.configure(connection))
    structured_migration.upgrade()
    resolution_migration = load_migration("0018_local_resolution")
    resolution_migration.op = Operations(MigrationContext.configure(connection))
    resolution_migration.upgrade()
    intelligence_migration = load_migration("0019_intelligence_rules")
    intelligence_migration.op = Operations(MigrationContext.configure(connection))
    intelligence_migration.upgrade()
    crm_migration = load_migration("0020_crm_mahs")
    crm_migration.op = Operations(MigrationContext.configure(connection))
    crm_migration.upgrade()
    profile_migration = load_migration("0021_crm_mah_profile")
    profile_migration.op = Operations(MigrationContext.configure(connection))
    profile_migration.upgrade()
    contacts_migration = load_migration("0022_crm_contacts")
    contacts_migration.op = Operations(MigrationContext.configure(connection))
    contacts_migration.upgrade()
    contact_profiles_migration = load_migration("0023_crm_contact_profiles")
    contact_profiles_migration.op = Operations(MigrationContext.configure(connection))
    contact_profiles_migration.upgrade()
    end_user_review_migration = load_migration("0024_end_user_import_review")
    end_user_review_migration.op = Operations(MigrationContext.configure(connection))
    end_user_review_migration.upgrade()
    end_users_migration = load_migration("0025_crm_end_users")
    end_users_migration.op = Operations(MigrationContext.configure(connection))
    end_users_migration.upgrade()
    end_user_management_migration = load_migration("0026_crm_end_user_management")
    end_user_management_migration.op = Operations(MigrationContext.configure(connection))
    end_user_management_migration.upgrade()
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    end_user_management_migration.downgrade()
    end_users_migration.downgrade()
    end_user_review_migration.downgrade()
    contact_profiles_migration.downgrade()
    contacts_migration.downgrade()
    profile_migration.downgrade()
    crm_migration.downgrade()
    intelligence_migration.downgrade()
    resolution_migration.downgrade()
    structured_migration.downgrade()
    review_migration.downgrade()
    control_migration.downgrade()
    upload_migration.downgrade()
    pack_migration.downgrade()
    interval_migration.downgrade()
    precision_migration.downgrade()
    exception_migration.downgrade()
    measures_migration.downgrade()
    activity_migration.downgrade()
    participant_migration.downgrade()
    version_migration.downgrade()
    domain_migration.downgrade()
    scheduling_migration.downgrade()
    metadata_migration.downgrade()
    migration.downgrade()
    assert snapshot(connection, names) == before


def test_corrupt_legacy_content_refuses_before_ddl(migration_database):
    connection, migration = migration_database
    seed(connection, corrupt=True)
    with pytest.raises(RuntimeError, match="integrity check failed"):
        migration.upgrade()
    assert "artifact_contents" not in sa.inspect(connection).get_table_names()
    assert "failure_stage" not in table(connection, "integration_jobs").c


@pytest.mark.parametrize("kind", ["duplicate_acquisition", "failure_stage", "orphan_content"])
def test_downgrade_refuses_provenance_loss_before_ddl(migration_database, kind):
    connection, migration = migration_database
    seed(connection)
    migration.upgrade()
    if kind == "duplicate_acquisition":
        artifacts = table(connection, "acquired_artifacts")
        original = dict(connection.execute(sa.select(artifacts)).mappings().one())
        connection.execute(artifacts.insert(), {**original, "id": 74})
    elif kind == "failure_stage":
        connection.execute(table(connection, "integration_jobs").update().values(failure_stage="extraction"))
    else:
        connection.execute(table(connection, "artifact_contents").insert(), {
            "id": 99, "sha256": hashlib.sha256(b"orphan").hexdigest(), "content_length": 6,
            "artifact_bytes": b"orphan", "created_at": datetime(2026, 9, 25, tzinfo=UTC).replace(tzinfo=None),
        })
    with pytest.raises(RuntimeError, match="refused before schema changes"):
        migration.downgrade()
    assert "artifact_contents" in sa.inspect(connection).get_table_names()
    assert "artifact_bytes" not in table(connection, "acquired_artifacts").c


def test_backfill_verifier_prevents_dropping_original_bytes(migration_database, monkeypatch):
    connection, migration = migration_database
    seed(connection)
    original_verify = migration._validate_backfill

    def corrupt_then_verify(connection, artifacts, contents):
        connection.execute(contents.update().values(artifact_bytes=b"bad copy"))
        original_verify(connection, artifacts, contents)

    monkeypatch.setattr(migration, "_validate_backfill", corrupt_then_verify)
    with pytest.raises(RuntimeError, match="backfill verification failed"):
        migration.upgrade()
    assert "artifact_bytes" in table(connection, "acquired_artifacts").c
    with pytest.raises(RuntimeError, match="inspect migration state"):
        migration.upgrade()


@pytest.mark.parametrize("direction,ordered_statements", [
    ("downgrade", (
        "ALTER TABLE acquired_artifacts DROP FOREIGN KEY fk_acquired_artifacts_content;",
        "DROP INDEX ix_acquired_artifacts_content ON acquired_artifacts;",
        "ALTER TABLE acquired_artifacts DROP COLUMN content_id;",
    )),
    ("upgrade", (
        "ALTER TABLE acquired_artifacts ADD COLUMN content_id INTEGER;",
        ("ALTER TABLE acquired_artifacts ADD CONSTRAINT fk_acquired_artifacts_content "
         "FOREIGN KEY(content_id) REFERENCES artifact_contents (id);"),
        "CREATE INDEX ix_acquired_artifacts_content ON acquired_artifacts (content_id);",
    )),
])
def test_mysql_content_foreign_key_ddl_order(direction, ordered_statements):
    migration = load_migration("0002_artifact_content_and_failure_stage")
    # Compile the actual migration batch blocks, not copied operation calls.
    # Data queries/reflection cannot run offline; existing tests exercise those
    # paths separately. No connection or migration environment is created here.
    function = ast.parse(inspect.getsource(getattr(migration, direction))).body[0]
    batches = [node for node in function.body if isinstance(node, ast.With)]
    ddl = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="mysql", opts={"as_sql": True, "output_buffer": ddl},
    )
    namespace = {**vars(migration), "op": Operations(context)}
    code = compile(ast.Module(body=batches, type_ignores=[]), "<migration batches>", "exec")
    exec(code, namespace)  # noqa: S102 - trusted repository migration compiled without a connection
    sql = ddl.getvalue()
    assert all(sql.count(statement) == 1 for statement in ordered_statements)
    positions = [sql.index(statement) for statement in ordered_statements]
    assert positions == sorted(positions)
