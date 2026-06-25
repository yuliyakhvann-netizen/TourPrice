"""
SQLAlchemy models for the Selfie Travel operator catalog.
Structure mirrors kompas_catalog — same SAMO engine, different installation.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SelfieCountry(Base):
    __tablename__ = "selfie_country"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    resorts: Mapped[list["SelfieResort"]] = relationship(back_populates="country")


class SelfieResort(Base):
    __tablename__ = "selfie_resort"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # = ht_place_id
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("selfie_country.id"), nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    country: Mapped["SelfieCountry"] = relationship(back_populates="resorts")