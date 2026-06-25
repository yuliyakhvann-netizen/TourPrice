"""add samo_departure_city table

Revision ID: ZZZZ_samo_departure_city
Revises: YYYY_operator_session
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa

revision = "ZZZZ_samo_departure_city"
down_revision = "39c17dd5556a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "samo_departure_city",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("operator_id", sa.Integer(), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("city_inc", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.UniqueConstraint("operator_id", "city_inc", name="uq_samo_dep_city_op_inc"),
    )
    op.create_index("ix_samo_dep_city_operator_id", "samo_departure_city", ["operator_id"])


def downgrade() -> None:
    op.drop_index("ix_samo_dep_city_operator_id", table_name="samo_departure_city")
    op.drop_table("samo_departure_city")