"""local organisations and locations

Revision ID: 0007_snapshot_participants
Revises: 0006_source_version_values
Create Date: 2026-11-04 14:01:32.507245
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_snapshot_participants"
down_revision: str | None = "0006_source_version_values"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.bulk_insert(
        sa.table("import_mutexes", sa.column("import_key", sa.String(100))),
        [{"import_key": "mapping:participants"}],
    )
    op.create_table(
        "participant_mapping_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("input_key", sa.String(length=64), nullable=False),
        sa.Column("snapshot_run_id", sa.Integer(), nullable=False),
        sa.Column("source_namespace", sa.String(length=255), nullable=False),
        sa.Column("mapping_version", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("statistics", sa.JSON(), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["snapshot_run_id"],
            ["processing_runs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("input_key"),
    )
    op.create_table(
        "participant_publications",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("mapping_run_id", sa.Integer(), nullable=False),
        sa.Column("source_namespace", sa.String(length=255), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["mapping_run_id"],
            ["participant_mapping_runs.id"],
        ),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_table(
        "local_organisations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=64), nullable=False),
        sa.Column("source_namespace", sa.String(length=255), nullable=False),
        sa.Column("source_organisation_id", sa.String(length=100), nullable=False),
        sa.Column("organisation_name", sa.Text(), nullable=True),
        sa.Column("organisation_type", sa.String(length=100), nullable=True),
        sa.Column("organisation_subtype", sa.String(length=100), nullable=True),
        sa.Column("organisation_status", sa.String(length=100), nullable=True),
        sa.Column("creation_date_text", sa.Text(), nullable=True),
        sa.Column("registration_date_text", sa.Text(), nullable=True),
        sa.Column("expiry_date_text", sa.Text(), nullable=True),
        sa.Column("is_observed", sa.Integer(), nullable=False),
        sa.Column("last_participant_run_id", sa.Integer(), nullable=False),
        sa.Column("source_row_id", sa.Integer(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["last_participant_run_id"],
            ["participant_mapping_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_row_id"], ["staging_rows.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key"),
    )
    op.create_index(
        "ix_local_org_namespace_observed",
        "local_organisations",
        ["source_namespace", "is_observed"],
        unique=False,
    )
    op.create_table(
        "local_locations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=64), nullable=False),
        sa.Column("source_namespace", sa.String(length=255), nullable=False),
        sa.Column("source_location_id", sa.String(length=100), nullable=False),
        sa.Column("source_organisation_id", sa.String(length=100), nullable=True),
        sa.Column("organisation_id", sa.Integer(), nullable=True),
        sa.Column("organisation_link_status", sa.String(length=40), nullable=False),
        sa.Column("location_name", sa.Text(), nullable=True),
        sa.Column("location_status", sa.String(length=100), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("postal_code", sa.String(length=100), nullable=True),
        sa.Column("legitimacy_information", sa.Text(), nullable=True),
        sa.Column("equipment_count", sa.BigInteger(), nullable=True),
        sa.Column("creation_date_text", sa.Text(), nullable=True),
        sa.Column("is_observed", sa.Integer(), nullable=False),
        sa.Column("last_participant_run_id", sa.Integer(), nullable=False),
        sa.Column("source_row_id", sa.Integer(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["last_participant_run_id"],
            ["participant_mapping_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["local_organisations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_row_id"], ["staging_rows.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key"),
    )
    op.create_index(
        "ix_local_location_namespace_observed",
        "local_locations",
        ["source_namespace", "is_observed"],
        unique=False,
    )
    op.create_index(
        "ix_local_location_org_observed",
        "local_locations",
        ["organisation_id", "is_observed"],
        unique=False,
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM import_mutexes WHERE import_key = 'mapping:participants'")
    )
    op.drop_index("ix_local_location_org_observed", table_name="local_locations")
    op.drop_index("ix_local_location_namespace_observed", table_name="local_locations")
    op.drop_table("local_locations")
    op.drop_index("ix_local_org_namespace_observed", table_name="local_organisations")
    op.drop_table("local_organisations")
    op.drop_table("participant_publications")
    op.drop_table("participant_mapping_runs")
