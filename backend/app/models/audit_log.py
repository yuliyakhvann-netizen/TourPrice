from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    scrape_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    operator_id: Mapped[int | None] = mapped_column(
        ForeignKey("operators.id"), nullable=True, index=True
    )
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("search_profiles.id"), nullable=True, index=True
    )
    event: Mapped[str] = mapped_column(String(100), nullable=False)  # login, search, normalize, compare
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, error, partial
    tours_found: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tours_normalized: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
