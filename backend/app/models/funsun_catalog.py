from __future__ import annotations

from sqlalchemy import Column, Integer, String, UniqueConstraint

from app.database import Base


class FunSunCountry(Base):
    __tablename__ = "funsun_country"

    id = Column(Integer, primary_key=True, autoincrement=True)
    samo_id = Column(Integer, nullable=False, unique=True)
    name = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("samo_id", name="uq_funsun_country_samo_id"),
    )


class FunSunResort(Base):
    __tablename__ = "funsun_resort"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ht_place_id = Column(Integer, nullable=False, unique=True)
    name = Column(String, nullable=False)
    country_samo_id = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("ht_place_id", name="uq_funsun_resort_ht_place_id"),
    )