from __future__ import annotations

from sqlalchemy import Column, Integer, String, UniqueConstraint

from app.database import Base


class KazunionCountry(Base):
    __tablename__ = "kazunion_country"

    id = Column(Integer, primary_key=True, autoincrement=True)
    samo_id = Column(Integer, nullable=False, unique=True)
    name = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("samo_id", name="uq_kazunion_country_samo_id"),
    )


class KazunionResort(Base):
    __tablename__ = "kazunion_resort"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ht_place_id = Column(Integer, nullable=False, unique=True)
    name = Column(String, nullable=False)
    country_samo_id = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("ht_place_id", name="uq_kazunion_resort_ht_place_id"),
    )