"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operators",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("base_url", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("session_data", postgresql.JSONB(), nullable=True),
        sa.Column("session_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("health_status", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "search_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("departure_city", sa.String(100), nullable=False),
        sa.Column("departure_date", sa.Date(), nullable=False),
        sa.Column("nights", sa.Integer(), nullable=False),
        sa.Column("adults", sa.Integer(), nullable=False, default=2),
        sa.Column("children", sa.Integer(), nullable=False, default=0),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "raw_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operator_id", sa.Integer(), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("search_profiles.id"), nullable=False),
        sa.Column("scrape_run_id", sa.String(36), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False),
        sa.Column("tours_count", sa.Integer(), nullable=False, default=0),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_raw_results_operator_id", "raw_results", ["operator_id"])
    op.create_index("ix_raw_results_profile_id", "raw_results", ["profile_id"])
    op.create_index("ix_raw_results_scrape_run_id", "raw_results", ["scrape_run_id"])

    op.create_table(
        "normalized_tours",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operator_id", sa.Integer(), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("search_profiles.id"), nullable=False),
        sa.Column("scrape_run_id", sa.String(36), nullable=False),
        sa.Column("tour_key", sa.String(64), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("departure_city", sa.String(100), nullable=False),
        sa.Column("departure_date", sa.Date(), nullable=False),
        sa.Column("nights", sa.Integer(), nullable=False),
        sa.Column("hotel", sa.String(200), nullable=False),
        sa.Column("room_type", sa.String(100), nullable=False),
        sa.Column("meal_type", sa.String(100), nullable=False),
        sa.Column("airline", sa.String(100), nullable=False),
        sa.Column("adults", sa.Integer(), nullable=False),
        sa.Column("children", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, default="KZT"),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "operator_id", "tour_key", "scraped_at",
            name="uq_normalized_tour_operator_key_time"
        ),
    )
    op.create_index("ix_normalized_tours_tour_key", "normalized_tours", ["tour_key"])
    op.create_index("ix_normalized_tours_operator_id", "normalized_tours", ["operator_id"])

    op.create_table(
        "price_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("normalized_tour_id", sa.Integer(), sa.ForeignKey("normalized_tours.id"), nullable=False),
        sa.Column("operator_id", sa.Integer(), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("tour_key", sa.String(64), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, default="KZT"),
        sa.Column("price_change", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_change_pct", sa.Numeric(6, 2), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_price_snapshots_tour_key", "price_snapshots", ["tour_key"])
    op.create_index("ix_price_snapshots_operator_id", "price_snapshots", ["operator_id"])

    op.create_table(
        "comparison_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("search_profiles.id"), nullable=False),
        sa.Column("tour_key", sa.String(64), nullable=False),
        sa.Column("scrape_run_id", sa.String(36), nullable=False),
        sa.Column("hotel", sa.String(200), nullable=False),
        sa.Column("room_type", sa.String(100), nullable=False),
        sa.Column("meal_type", sa.String(100), nullable=False),
        sa.Column("airline", sa.String(100), nullable=False),
        sa.Column("nights", sa.Integer(), nullable=False),
        sa.Column("funsun_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("pegas_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("anex_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("kompas_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("market_min_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("market_max_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("market_avg_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, default="KZT"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_comparison_results_profile_id", "comparison_results", ["profile_id"])
    op.create_index("ix_comparison_results_tour_key", "comparison_results", ["tour_key"])

    for table in ("room_mapping", "meal_mapping", "airline_mapping"):
        op.create_table(
            table,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("raw_value", sa.String(200), nullable=False),
            sa.Column("normalized_value", sa.String(100), nullable=False),
            sa.Column("confirmed", sa.Boolean(), nullable=False, default=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("raw_value", name=f"uq_{table}_raw"),
        )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scrape_run_id", sa.String(36), nullable=False),
        sa.Column("operator_id", sa.Integer(), sa.ForeignKey("operators.id"), nullable=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("search_profiles.id"), nullable=True),
        sa.Column("event", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("tours_found", sa.Integer(), nullable=True),
        sa.Column("tours_normalized", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_scrape_run_id", "audit_logs", ["scrape_run_id"])

    # Seed operators
    op.execute("""
        INSERT INTO operators (code, name, base_url, is_active) VALUES
        ('funsun', 'Fun&Sun', 'https://b2b.funsun.kz', true),
        ('pegas', 'Pegas Touristik', 'https://b2b.pegast.kz', true),
        ('anex', 'Anex Tour', 'https://b2b.anextour.com', false),
        ('kompas', 'Kompas Tour', 'https://b2b.kompastour.kz', false)
    """)

    # Seed confirmed meal mappings (common cases)
    op.execute("""
        INSERT INTO meal_mapping (raw_value, normalized_value, confirmed) VALUES
        ('UAI', 'Ultra All Inclusive', true),
        ('UALL', 'Ultra All Inclusive', true),
        ('Ultra All Inclusive', 'Ultra All Inclusive', true),
        ('AI', 'All Inclusive', true),
        ('ALL', 'All Inclusive', true),
        ('All Inclusive', 'All Inclusive', true),
        ('HB', 'Half Board', true),
        ('Half Board', 'Half Board', true),
        ('BB', 'Bed & Breakfast', true),
        ('RO', 'Room Only', true),
        ('FB', 'Full Board', true)
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    for t in [
        "audit_logs", "comparison_results", "price_snapshots",
        "normalized_tours", "raw_results", "search_profiles",
        "room_mapping", "meal_mapping", "airline_mapping", "operators",
    ]:
        op.drop_table(t)
