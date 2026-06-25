from datetime import date

from pydantic import BaseModel, Field


class LiveSearchRequest(BaseModel):
    country: str
    departure_city: str
    checkin_beg: date
    checkin_end: date
    nights_from: int = Field(ge=1, le=30)
    nights_till: int = Field(ge=1, le=30)
    adults: int = Field(default=2, ge=1, le=8)
    children: int = Field(default=0, ge=0, le=4)


class DualSearchRequest(BaseModel):
    """
    Dual-passenger search: запускает поиск дважды на каждого оператора —
    без детей и с одним ребёнком (возраст child_age, по умолчанию 4 года).
    Возвращает все найденные варианты с diff по каждой комбинации
    (отель, номер, питание, дата, количество ночей, оператор).
    """
    country: str
    departure_city: str
    checkin_beg: date
    checkin_end: date
    nights_from: int = Field(ge=1, le=30)
    nights_till: int = Field(ge=1, le=30)
    adults: int = Field(default=2, ge=1, le=8)
    child_age: int = Field(default=4, ge=0, le=17)