from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RoomMapping(Base):
    __tablename__ = "room_mapping"

    __table_args__ = (UniqueConstraint("raw_value", name="uq_room_mapping_raw"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_value: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(100), nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MealMapping(Base):
    __tablename__ = "meal_mapping"

    __table_args__ = (UniqueConstraint("raw_value", name="uq_meal_mapping_raw"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_value: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(100), nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AirlineMapping(Base):
    __tablename__ = "airline_mapping"

    __table_args__ = (UniqueConstraint("raw_value", name="uq_airline_mapping_raw"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_value: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(100), nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CityMapping(Base):
    __tablename__ = "city_mapping"

    __table_args__ = (
        UniqueConstraint("operator_id", "raw_value", name="uq_city_mapping_operator_raw"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), nullable=False, index=True)
    raw_value: Mapped[str] = mapped_column(String(200), nullable=False)  # код города у оператора, напр. "9"
    normalized_value: Mapped[str] = mapped_column(String(100), nullable=False)  # человеческое имя, напр. "Almaty"
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CountryMapping(Base):
    __tablename__ = "country_mapping"

    __table_args__ = (
        UniqueConstraint("operator_id", "raw_value", name="uq_country_mapping_operator_raw"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), nullable=False, index=True)
    raw_value: Mapped[str] = mapped_column(String(200), nullable=False)  # код страны у оператора, напр. "32"
    normalized_value: Mapped[str] = mapped_column(String(100), nullable=False)  # человеческое имя, напр. "Vietnam"
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TourProgramMapping(Base):
    __tablename__ = "tour_program_mapping"

    __table_args__ = (
        UniqueConstraint("operator_id", "raw_value", name="uq_tour_program_mapping_operator_raw"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), nullable=False, index=True)
    raw_value: Mapped[str] = mapped_column(String(200), nullable=False)  # TOURINC у оператора, напр. "27060"
    normalized_value: Mapped[str] = mapped_column(String(100), nullable=False)  # авиакомпания, напр. "Air Astana"
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HotelMapping(Base):
    """
    Maps a (operator, raw hotel name) pair to a canonical_hotel_id - an
    arbitrary integer the manager assigns when confirming two operators'
    listings are the same physical hotel. Unlike city/country/tour-program
    mapping, there's no "correct" normalized string here (operators
    spell hotel names differently: "Ana Mandara Cam Ranh 5*" vs "Ana
    Mandara Cam Ranh Resort 5*") - canonical_hotel_id is just a shared
    integer that groups rows across operators once a human confirms
    they match. Rows with confirmed=False and no canonical_hotel_id are
    surfaced via /mappings/hotels/pending for manual confirmation - see
    the project's principle that fuzzy hotel-name matching should be a
    human-in-the-loop decision, not something the backend guesses.
    """

    __tablename__ = "hotel_mapping"

    __table_args__ = (
        UniqueConstraint("operator_id", "raw_value", name="uq_hotel_mapping_operator_raw"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), nullable=False, index=True)
    raw_value: Mapped[str] = mapped_column(String(300), nullable=False)  # raw hotel name as scraped
    canonical_hotel_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_matched: Mapped[bool] = mapped_column(Boolean, default=False)  # True = сопоставлено автоматически, требует проверки
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)