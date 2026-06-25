from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class SearchProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    country: str = Field(..., min_length=1, max_length=100)
    departure_city: str = Field(..., min_length=1, max_length=100)
    departure_date: date
    nights: int = Field(..., ge=1, le=30)
    adults: int = Field(default=2, ge=1, le=9)
    children: int = Field(default=0, ge=0, le=4)


class SearchProfileUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    departure_date: date | None = None
    nights: int | None = Field(default=None, ge=1, le=30)


class SearchProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country: str
    departure_city: str
    departure_date: date
    nights: int
    adults: int
    children: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
