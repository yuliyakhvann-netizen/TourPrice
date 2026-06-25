from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NormalizedTour(Base):
    __tablename__ = "normalized_tours"

    __table_args__ = (
        UniqueConstraint(
            "operator_id",
            "tour_key",
            "scraped_at",
            name="uq_normalized_tour_operator_key_time",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), nullable=False, index=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("search_profiles.id"), nullable=False, index=True
    )
    scrape_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Composite key fields (normalized values)
    tour_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA256 hash
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    departure_city: Mapped[str] = mapped_column(String(100), nullable=False)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)
    nights: Mapped[int] = mapped_column(Integer, nullable=False)
    hotel: Mapped[str] = mapped_column(String(200), nullable=False)
    resort: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    room_type: Mapped[str] = mapped_column(String(100), nullable=False)
    meal_type: Mapped[str] = mapped_column(String(100), nullable=False)
    airline: Mapped[str] = mapped_column(String(100), nullable=False)
    adults: Mapped[int] = mapped_column(Integer, nullable=False)
    children: Mapped[int] = mapped_column(Integer, nullable=False)

    # Price
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="KZT")

    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
