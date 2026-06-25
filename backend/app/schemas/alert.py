from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel


class AlertType(StrEnum):
    ABOVE_MARKET = "above_market"
    BELOW_MARKET = "below_market"
    PRICE_DROP = "price_drop"
    PRICE_RISE = "price_rise"


class AlertEvent(BaseModel):
    alert_type: AlertType
    operator_code: str
    tour_key: str
    hotel: str
    current_price: Decimal
    reference_price: Decimal
    change_pct: Decimal
    currency: str
    message: str
