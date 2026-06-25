"""
SQLAlchemy models for the Kompas operator catalog.

Countries are discovered via samo_action=INIT endpoint (returns ~40 countries).
Resorts are discovered automatically during PRICES search — each result row
contains ht_place_id + location_name which we upsert here.

Unlike Pegas (which has a full hotel catalog from Reference block),
Kompas resorts/hotels are built incrementally from search results.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KompasCountry(Base):
    __tablename__ = "kompas_country"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    resorts: Mapped[list["KompasResort"]] = relationship(back_populates="country")


class KompasResort(Base):
    __tablename__ = "kompas_resort"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("kompas_country.id"), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    country: Mapped["KompasCountry"] = relationship(back_populates="resorts")


class KompasDestinationTown(Base):
    """
    Города прибытия внутри страны — TOWNS ID из HTML чекбоксов САМО INIT.
    Используются при детском поиске: TOWNS_ANY=0&TOWNS=<id1,id2,...>
    """
    __tablename__ = "kompas_destination_town"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    town_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # САМО ID из value=
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("kompas_country.id"), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    country: Mapped["KompasCountry"] = relationship()