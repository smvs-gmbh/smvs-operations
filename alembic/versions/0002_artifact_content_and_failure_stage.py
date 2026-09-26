"""Separate immutable content from acquisition provenance; add job failure stage.

Revision ID: 0002_artifact_content_and_failure_stage
Revises: 0001_integration_foundation

Run with acquisition workers stopped. MySQL DDL is not transactional: a failed
partial application requires inspection, not an automatic retry or stamp.
"""
import hashlib

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision = "0002_artifact_content_and_failure_stage"
down_revision = "0001_integration_foundation"
branch_labels = None
depends_on = None


def _tables(connection):
    metadata = sa.MetaData()
    return (
        sa.Table("acquired_artifacts", metadata, autoload_with=connection),
        sa.Table("artifact_contents", metadata, autoload_with=connection),
    )


def _validate_legacy(connection, artifacts):
    rows = connection.execute(sa.select(
        artifacts.c.sha256, artifacts.c.content_length, artifacts.c.artifact_bytes,
    ))
    for digest, length, data in rows:
        if len(data) != length or hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError("Artifact integrity check failed; migration stopped.")


def _validate_backfill(connection, artifacts, contents):
    missing = connection.scalar(sa.select(sa.func.count()).select_from(
        artifacts.outerjoin(contents, artifacts.c.content_id == contents.c.id)
    ).where(contents.c.id.is_(None)))
    if missing:
        raise RuntimeError("Artifact content references are incomplete; migration stopped.")
    rows = connection.execute(sa.select(
        artifacts.c.sha256, artifacts.c.content_length, artifacts.c.artifact_bytes,
        contents.c.sha256, contents.c.content_length, contents.c.artifact_bytes,
    ).select_from(artifacts.join(contents, artifacts.c.content_id == contents.c.id)))
    for digest, length, data, copied_digest, copied_length, copied_data in rows:
        if (digest, length, data) != (copied_digest, copied_length, copied_data):
            raise RuntimeError("Artifact backfill verification failed; migration stopped.")


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "artifact_contents" in inspector.get_table_names():
        raise RuntimeError("Content table already exists; inspect migration state before retrying.")
    artifacts = sa.Table("acquired_artifacts", sa.MetaData(), autoload_with=connection)
    _validate_legacy(connection, artifacts)

    # The requested revision identifier is longer than Alembic's default 32.
    with op.batch_alter_table("alembic_version") as batch:
        batch.alter_column("version_num", existing_type=sa.String(32), type_=sa.String(64), existing_nullable=False)
    op.create_table(
        "artifact_contents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("content_length", sa.Integer(), nullable=False),
        sa.Column("artifact_bytes", sa.LargeBinary().with_variant(mysql.LONGBLOB(), "mysql"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("sha256", name="uq_artifact_contents_sha256"),
    )
    op.add_column("integration_jobs", sa.Column("failure_stage", sa.String(60), nullable=True))
    with op.batch_alter_table("acquired_artifacts") as batch:
        batch.add_column(sa.Column("content_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_acquired_artifacts_content", "artifact_contents", ["content_id"], ["id"])
        batch.create_index("ix_acquired_artifacts_content", ["content_id"])

    artifacts, contents = _tables(connection)
    # 0001 has a unique checksum per acquisition; preserve all acquisition IDs.
    connection.execute(contents.insert().from_select(
        ["id", "sha256", "content_length", "artifact_bytes", "created_at"],
        sa.select(artifacts.c.id, artifacts.c.sha256, artifacts.c.content_length,
                  artifacts.c.artifact_bytes, artifacts.c.created_at),
    ))
    connection.execute(artifacts.update().values(content_id=artifacts.c.id))
    _validate_backfill(connection, artifacts, contents)

    with op.batch_alter_table("acquired_artifacts") as batch:
        batch.alter_column("content_id", existing_type=sa.Integer(), nullable=False)
        batch.drop_constraint("uq_acquired_artifacts_sha256", type_="unique")
        batch.drop_column("sha256")
        batch.drop_column("content_length")
        batch.drop_column("artifact_bytes")


def downgrade():
    connection = op.get_bind()
    artifacts, contents = _tables(connection)
    duplicate = connection.execute(sa.select(artifacts.c.content_id).group_by(
        artifacts.c.content_id,
    ).having(sa.func.count() > 1).limit(1)).first()
    jobs = sa.Table("integration_jobs", sa.MetaData(), autoload_with=connection)
    failure_stage = connection.execute(sa.select(jobs.c.id).where(
        jobs.c.failure_stage.is_not(None),
    ).limit(1)).first()
    orphan = connection.execute(sa.select(contents.c.id).where(
        ~sa.exists(sa.select(artifacts.c.id).where(artifacts.c.content_id == contents.c.id)),
    ).limit(1)).first()
    if duplicate or failure_stage or orphan:
        raise RuntimeError("Downgrade would lose provenance or content; refused before schema changes.")
    _validate_legacy(connection, contents)

    with op.batch_alter_table("acquired_artifacts") as batch:
        batch.add_column(sa.Column("sha256", sa.String(64), nullable=True))
        batch.add_column(sa.Column("content_length", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("artifact_bytes", sa.LargeBinary().with_variant(mysql.LONGBLOB(), "mysql"), nullable=True))
    artifacts, contents = _tables(connection)
    connection.execute(artifacts.update().values(**{
        name: sa.select(contents.c[name]).where(contents.c.id == artifacts.c.content_id).scalar_subquery()
        for name in ("sha256", "content_length", "artifact_bytes")
    }))
    _validate_backfill(connection, artifacts, contents)
    with op.batch_alter_table("acquired_artifacts") as batch:
        for name, column_type in (("sha256", sa.String(64)), ("content_length", sa.Integer()),
                                  ("artifact_bytes", sa.LargeBinary().with_variant(mysql.LONGBLOB(), "mysql"))):
            batch.alter_column(name, existing_type=column_type, nullable=False)
        batch.create_unique_constraint("uq_acquired_artifacts_sha256", ["sha256"])
        batch.drop_constraint("fk_acquired_artifacts_content", type_="foreignkey")
        batch.drop_index("ix_acquired_artifacts_content")
        batch.drop_column("content_id")
    op.drop_table("artifact_contents")
    op.drop_column("integration_jobs", "failure_stage")
    # Keep the widened version column; Alembic still needs to update this revision.
