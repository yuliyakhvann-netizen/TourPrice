"""add pegas catalog tables

Revision ID: XXXX_pegas_catalog
Revises: <ВСТАВЬТЕ_ID_ПОСЛЕДНЕЙ_МИГРАЦИИ>
Create Date: 2026-06-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "XXXX_pegas_catalog"
down_revision = "304aff457ed9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pegas_country",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "pegas_resort",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("country_id", sa.BigInteger(), sa.ForeignKey("pegas_country.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pegas_resort_country_id", "pegas_resort", ["country_id"])

    op.create_table(
        "pegas_hotel",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("resort_id", sa.BigInteger(), sa.ForeignKey("pegas_resort.id"), nullable=True),
        sa.Column("category_group_id", sa.BigInteger(), nullable=True),
        sa.Column("category_label", sa.String(length=50), nullable=True),
        # meal_group_ids: список id типов питания, доступных в этом отеле (re.itmgi коды)
        sa.Column("meal_group_ids", sa.ARRAY(sa.BigInteger()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pegas_hotel_resort_id", "pegas_hotel", ["resort_id"])

    op.create_table(
        "pegas_airline",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("pegas_airline")
    op.drop_index("ix_pegas_hotel_resort_id", table_name="pegas_hotel")
    op.drop_table("pegas_hotel")
    op.drop_index("ix_pegas_resort_country_id", table_name="pegas_resort")
    op.drop_table("pegas_resort")
    op.drop_table("pegas_country")