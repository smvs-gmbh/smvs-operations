"""Preserve source alert and query timestamp precision.

Revision ID: 0011_exception_precision
Revises: 0010_exceptions
"""

import json
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

from alembic import op

revision = "0011_exception_precision"
down_revision = "0010_exceptions"
branch_labels = None
depends_on = None

COLUMNS = {
    "exception_publications": [
        "period_start",
        "period_end",
        "query_started_at",
        "captured_at",
        "published_at",
    ],
    "nmvs_exceptions": [
        "alert_at",
        "selection_time",
        "first_observed_at",
        "last_observed_at",
    ],
    "exception_revisions": ["observed_at"],
}


def parsed(value):
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return d.astimezone(UTC).replace(tzinfo=None) if d.tzinfo else None
    except (ValueError, AttributeError):
        return None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        for table, columns in COLUMNS.items():
            for column in columns:
                op.alter_column(
                    table,
                    column,
                    existing_type=sa.DateTime(),
                    type_=DATETIME(fsp=6),
                    existing_nullable=column == "alert_at",
                )
    meta = sa.MetaData()
    pubs = sa.Table("exception_publications", meta, autoload_with=bind)
    runs = sa.Table("processing_runs", meta, autoload_with=bind)
    artifacts = sa.Table("acquired_artifacts", meta, autoload_with=bind)
    for identifier, metadata in bind.execute(
        sa.select(pubs.c.id, artifacts.c.report_metadata)
        .join(runs, pubs.c.processing_run_id == runs.c.id)
        .join(artifacts, runs.c.artifact_id == artifacts.c.id)
    ):
        metadata = json.loads(metadata) if isinstance(metadata, str) else metadata
        f = metadata.get("filter", {})
        a, b = parsed(f.get("startTimestamp")), parsed(f.get("endTimestamp"))
        if a is None or b is None:
            raise RuntimeError(
                "Exception source query interval unavailable; precision repair refused."
            )
        bind.execute(
            pubs.update()
            .where(pubs.c.id == identifier)
            .values(period_start=a, period_end=b)
        )
    records = sa.Table("nmvs_exceptions", meta, autoload_with=bind)
    for identifier, evidence in bind.execute(
        sa.select(records.c.id, records.c.evidence)
    ):
        evidence = json.loads(evidence) if isinstance(evidence, str) else evidence
        bind.execute(
            records.update()
            .where(records.c.id == identifier)
            .values(alert_at=parsed(evidence.get("alertDateTime")))
        )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        for table, columns in COLUMNS.items():
            for column in columns:
                if bind.execute(
                    sa.text(
                        f"SELECT COUNT(*) FROM {table} WHERE MICROSECOND({column}) <> 0"
                    )
                ).scalar_one():
                    raise RuntimeError(
                        "Exception precision downgrade refused: timestamp precision would be lost."
                    )
        for table, columns in COLUMNS.items():
            for column in columns:
                op.alter_column(
                    table,
                    column,
                    existing_type=DATETIME(fsp=6),
                    type_=sa.DateTime(),
                    existing_nullable=column == "alert_at",
                )
