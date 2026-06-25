"""
SQLAlchemy models for the Pegas operator catalog.

Unlike the SAMO mapping tables (city_mapping, country_mapping, ...), this is
not a "raw_value -> confirmed normalized_value" mapping. Pegas' GetInitialOptions
response already ships a complete, self-contained catalog with human-readable
names and an explicit hierarchy (country -> resort -> hotel), so we import it
as-is into normalized tables rather than building a confirmation workflow.

NOTE: created_at/updated_at are declared explicitly on each model below.
If the project has (or later adopts) a shared timestamp mixin, these four
columns can be swapped for it in one pass.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PegasCountry(Base):
    __tablename__ = "pegas_country"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    resorts: Mapped[list["PegasResort"]] = relationship(back_populates="country")


class PegasResort(Base):
    __tablename__ = "pegas_resort"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pegas_country.id"), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    country: Mapped["PegasCountry"] = relationship(back_populates="resorts")
    hotels: Mapped[list["PegasHotel"]] = relationship(back_populates="resort")


class PegasHotel(Base):
    __tablename__ = "pegas_hotel"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    resort_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("pegas_resort.id"), nullable=True)
    category_group_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    category_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # List of meal-group ids (re.itmgi codes) available at this hotel, e.g. [6890, 16698]
    meal_group_ids: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    resort: Mapped["PegasResort"] = relationship(back_populates="hotels")


class PegasAirline(Base):
    __tablename__ = "pegas_airline"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PegasDepartureLocation(Base):
    """
    Города вылета Pegas, получаемые из ReferenceDescription.Locations
    в ответе /PackageSearch/GetOptions (DestinationCountryId=159, Казахстан).
    Содержит только казахстанские города — платформа kz.pegast.asia.

    airport_code: IATA-код аэропорта (ALA, NQZ, ...) — может быть пустым
    для небольших городов без прямых рейсов.
    is_top: True для городов из TopLocationIds (Алматы, Астана, Шымкент,
    Актобе, Караганда) — используем для сортировки в UI.
    """
    __tablename__ = "pegas_departure_location"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    airport_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_top: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)