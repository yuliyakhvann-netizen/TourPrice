"""add operator_session table

Revision ID: YYYY_operator_session
Revises: XXXX_pegas_catalog
Create Date: 2026-06-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "YYYY_operator_session"
down_revision = "XXXX_pegas_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operator_session",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("operator_id", sa.BigInteger(), nullable=False),
        sa.Column("cookies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("operator_id", name="uq_operator_session_operator_id"),
    )


def downgrade() -> None:
    op.drop_table("operator_session")