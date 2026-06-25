from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    normalized_tour_id: Mapped[int] = mapped_column(
        ForeignKey("normalized_tours.id"), nullable=False, index=True
    )
    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), nullable=False, index=True)
    tour_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="KZT")
    price_change: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_change_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
