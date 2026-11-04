"""Idempotent extraction references and persistent import scheduling.

Revision ID: 0004_import_scheduling
Revises: 0003_file_metadata
"""

import sqlalchemy as sa

from alembic import op

revision = "0004_import_scheduling"
down_revision = "0003_file_metadata"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("processing_runs") as batch:
        batch.add_column(sa.Column("reused_from_run_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_processing_runs_reused_from",
            "processing_runs",
            ["reused_from_run_id"],
            ["id"],
        )
    op.create_table(
        "import_mutexes", sa.Column("import_key", sa.String(100), primary_key=True)
    )
    op.create_table(
        "import_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("import_key", sa.String(100), nullable=False, unique=True),
        sa.Column("enabled", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(100), nullable=False),
        sa.Column("daily_time", sa.String(5), nullable=False),
        sa.Column("next_run_at", sa.DateTime(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("retry_delay_seconds", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
    )
    op.create_table(
        "import_executions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "schedule_id",
            sa.Integer(),
            sa.ForeignKey("import_schedules.id"),
            nullable=False,
        ),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "integration_job_id",
            sa.Integer(),
            sa.ForeignKey("integration_jobs.id"),
            nullable=True,
        ),
        sa.Column("failure_code", sa.String(100), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_import_executions_schedule_status",
        "import_executions",
        ["schedule_id", "status"],
    )


def downgrade():
    op.drop_table("import_executions")
    op.drop_table("import_schedules")
    op.drop_table("import_mutexes")
    with op.batch_alter_table("processing_runs") as batch:
        batch.drop_constraint("fk_processing_runs_reused_from", type_="foreignkey")
        batch.drop_column("reused_from_run_id")
