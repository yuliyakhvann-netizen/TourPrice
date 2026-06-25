from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RawResult(Base):
    __tablename__ = "raw_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), nullable=False, index=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("search_profiles.id"), nullable=False, index=True
    )
    scrape_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)  # UUID
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    tours_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
