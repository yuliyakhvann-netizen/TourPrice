from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ComparisonResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tour_key: str
    hotel: str
    room_type: str
    meal_type: str
    airline: str
    nights: int
    funsun_price: Decimal | None
    pegas_price: Decimal | None
    anex_price: Decimal | None
    kompas_price: Decimal | None
    market_min_price: Decimal | None
    market_max_price: Decimal | None
    market_avg_price: Decimal | None
    currency: str
    created_at: datetime


class PriceHistoryPoint(BaseModel):
    operator_code: str
    price: Decimal
    currency: str
    recorded_at: datetime


class PriceDeviationResponse(BaseModel):
    tour_key: str
    hotel: str
    operator_code: str
    operator_price: Decimal
    market_avg: Decimal
    deviation_pct: Decimal
    signal: str  # "above_market", "below_market", "at_market"

class OperatorDualPrice(BaseModel):
    """Цены одного оператора для одной комбинации тура."""
    operator_code: str
    price_adults_only: Decimal | None   # min price без детей
    price_with_child: Decimal | None    # min price с 1 ребёнком
    child_diff: Decimal | None          # price_with_child - price_adults_only


class DualSearchTourResult(BaseModel):
    """
    Одна строка dual-результата: конкретная комбинация
    (отель, номер, питание, дата вылета, ночей) по всем операторам.
    """
    hotel: str
    resort: str = ""
    room_type: str
    meal_type: str
    departure_date: date
    nights: int
    operators: list[OperatorDualPrice]
