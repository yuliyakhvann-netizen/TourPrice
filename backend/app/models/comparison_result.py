from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ComparisonResult(Base):
    __tablename__ = "comparison_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("search_profiles.id"), nullable=False, index=True
    )
    tour_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scrape_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Denormalized tour info for quick reads
    hotel: Mapped[str] = mapped_column(String(200), nullable=False)
    room_type: Mapped[str] = mapped_column(String(100), nullable=False)
    meal_type: Mapped[str] = mapped_column(String(100), nullable=False)
    airline: Mapped[str] = mapped_column(String(100), nullable=False)
    nights: Mapped[int] = mapped_column(Integer, nullable=False)

    # Prices per operator (nullable = operator didn't have this tour)
    funsun_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    pegas_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    anex_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    kompas_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    market_min_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    market_max_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    market_avg_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="KZT")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
