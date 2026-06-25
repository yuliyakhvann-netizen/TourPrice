from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class SamoDepartureCity(Base):
    """
    Города вылета обнаруженные через samo_action=INIT для каждого оператора.
    Хранит сырые САМО-коды. Подтверждение происходит через city_mapping.
    """
    __tablename__ = "samo_departure_city"
    __table_args__ = (
        UniqueConstraint("operator_id", "city_inc", name="uq_samo_dep_city_op_inc"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    operator_id = Column(Integer, ForeignKey("operators.id"), nullable=False, index=True)
    city_inc = Column(Integer, nullable=False)
    name = Column(String(200), nullable=False)