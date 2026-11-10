from sqlalchemy.dialects import mysql

from app.core.db.models import Base


def test_integration_foundation_metadata_contains_only_approved_tables() -> None:
    assert set(Base.metadata.tables) == {
        "integration_jobs",
        "acquired_artifacts",
        "artifact_contents",
        "processing_runs",
        "staging_datasets",
        "staging_rows",
        "import_schedules",
        "import_executions",
        "import_mutexes",
        "products", "product_source_records", "product_versions", "batches",
        "sai_holders", "sai_preparations", "sai_packages", "product_reference_matches",
        "mapping_runs", "current_publications",
        "participant_mapping_runs", "participant_publications", "local_organisations", "local_locations",
        "activity_publications", "activity_days", "activity_facts",
        "exception_publications", "nmvs_exceptions", "exception_revisions",
        "pack_audit_reports", "pack_audit_requests",
        "upload_reports", "upload_requests",
        "exception_reviews", "exception_review_events", "intelligence_rule_revisions", "crm_mahs", "crm_contacts", "end_user_import_reviews", "crm_end_users",
        "portal_users", "portal_passkeys", "portal_auth_tokens", "portal_list_preferences", "crm_list_views",
        "crm_agreements", "crm_agreement_exclusions", "crm_agreement_mah_links", "crm_mah_transfers", "crm_self_declarations", "crm_declaration_drafts",
        "end_user_registrations", "registration_events", "registration_receipts", "crm_deletion_events",
        "manual_import_requests", "manual_import_attempts", "scheduler_heartbeats",
    }


def test_artifact_uses_longblob_and_staging_rows_do_not_store_raw_csv_lines() -> None:
    artifact = Base.metadata.tables["artifact_contents"]
    staging_row = Base.metadata.tables["staging_rows"]

    assert isinstance(artifact.c.artifact_bytes.type.dialect_impl(mysql.dialect()), mysql.LONGBLOB)
    assert "raw_csv_line" not in staging_row.c
