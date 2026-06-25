"""
Stores authenticated B2B-portal sessions for operators that require login
(Pegas now, Anex later). Sessions are acquired via Playwright (see
app/operators/playwright_session/) and reused across plain httpx searches
until they expire.

cookies is stored as the raw list of cookie dicts returned by Playwright's
BrowserContext.cookies() (name, value, domain, path, expires, httpOnly,
secure, sameSite) so it can be replayed directly into an httpx client without
reshaping.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OperatorSession(Base):
    __tablename__ = "operator_session"
    __table_args__ = (UniqueConstraint("operator_id", name="uq_operator_session_operator_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    operator_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cookies: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)