import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


@dataclass(frozen=True)
class TourKey:
    """Composite key that uniquely identifies a tour package across operators."""

    country: str
    departure_city: str
    departure_date: date
    nights: int
    hotel: str
    room_type: str
    meal_type: str
    airline: str
    adults: int
    children: int

    def hash(self) -> str:
        raw = "|".join([
            self.country.lower().strip(),
            self.departure_city.lower().strip(),
            str(self.departure_date),
            str(self.nights),
            self.hotel.lower().strip(),
            self.room_type.lower().strip(),
            self.meal_type.lower().strip(),
            self.airline.lower().strip(),
            str(self.adults),
            str(self.children),
        ])
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class NormalizedTourSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    operator_id: int
    profile_id: int
    tour_key: str
    country: str
    departure_city: str
    departure_date: date
    nights: int
    hotel: str
    room_type: str
    meal_type: str
    airline: str
    adults: int
    children: int
    price: Decimal
    currency: str
    scraped_at: datetime
