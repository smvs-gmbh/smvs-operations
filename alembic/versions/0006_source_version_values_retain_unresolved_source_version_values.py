"""Retain source version markers without claiming a valid PMD version.

Revision ID: 0006_source_version_values
Revises: 0005_product_batch_model
"""

import sqlalchemy as sa

from alembic import op

revision = "0006_source_version_values"
down_revision = "0005_product_batch_model"
branch_labels = None
depends_on = None


def upgrade():
    for table_name, number_name, text_name in (
        ("product_source_records", "reported_version", "reported_version_text"),
        ("product_versions", "version_number", "source_version_value"),
    ):
        op.add_column(table_name, sa.Column(text_name, sa.String(100), nullable=True))
        table = sa.table(
            table_name,
            sa.column(number_name, sa.Integer()),
            sa.column(text_name, sa.String(100)),
        )
        op.execute(
            table.update().values(
                {text_name: sa.cast(table.c[number_name], sa.String(100))}
            )
        )
        with op.batch_alter_table(table_name) as batch:
            batch.alter_column(number_name, existing_type=sa.Integer(), nullable=True)
            batch.alter_column(text_name, existing_type=sa.String(100), nullable=False)


def downgrade():
    # Refuse data loss before any DDL. Unresolved source values cannot be forced
    # into an invented numeric PMD version merely to support a schema rollback.
    connection = op.get_bind()
    for table_name, number_name, _ in (
        ("product_source_records", "reported_version", "reported_version_text"),
        ("product_versions", "version_number", "source_version_value"),
    ):
        table = sa.table(table_name, sa.column(number_name, sa.Integer()))
        if connection.scalar(
            sa.select(sa.func.count())
            .select_from(table)
            .where(table.c[number_name].is_(None))
        ):
            raise RuntimeError(
                "Downgrade refused: unresolved source version values must be preserved."
            )
    for table_name, number_name, text_name in (
        ("product_versions", "version_number", "source_version_value"),
        ("product_source_records", "reported_version", "reported_version_text"),
    ):
        with op.batch_alter_table(table_name) as batch:
            batch.alter_column(number_name, existing_type=sa.Integer(), nullable=False)
            batch.drop_column(text_name)
