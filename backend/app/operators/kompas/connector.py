from __future__ import annotations

from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.operators.kompas.config import (
    BASE_URL,
    CURRENCY_KZT,
    FILTER_DEFAULT,
    PARTITION_PRICE_DEFAULT,
)
from app.operators.samo.client import SamoSearchParams, fetch_all_prices


class KompasOperator:
    operator_code = "kompas"

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url

    async def _get_destination_town_ids(
        self, db: AsyncSession, state_inc: int
    ) -> list[int]:
        """Возвращает TOWNS ID для страны из kompas_destination_town."""
        from app.models.kompas_catalog import KompasDestinationTown
        result = await db.execute(
            select(KompasDestinationTown.town_id).where(
                KompasDestinationTown.country_id == state_inc
            )
        )
        return [row[0] for row in result.all()]

    async def search(
        self,
        *,
        town_from_inc: int,
        state_inc: int,
        checkin_beg: str,
        checkin_end: str,
        nights_from: int,
        nights_till: int,
        adults: int = 2,
        children: int = 0,
        child_ages: Optional[list[int]] = None,
        tour_inc: Optional[int] = None,
        hotel_ids: Optional[list[int]] = None,
        meal_ids: Optional[list[int]] = None,
        resort_ids: Optional[list[int]] = None,
        db: Optional[AsyncSession] = None,
    ) -> list[dict]:
        extra = {}
        if children > 0:
            # При детском поиске нужны конкретные TOWNS ID иначе САМО возвращает 0 строк
            town_ids: list[int] = []
            if db is not None:
                town_ids = await self._get_destination_town_ids(db, state_inc)
            if town_ids:
                extra["TOWNS_ANY"] = 0
                extra["TOWNS"] = ",".join(str(t) for t in town_ids)

        params = SamoSearchParams(
            town_from_inc=town_from_inc,
            state_inc=state_inc,
            checkin_beg=checkin_beg,
            checkin_end=checkin_end,
            nights_from=nights_from,
            nights_till=nights_till,
            adults=adults,
            children=children,
            child_ages=child_ages or [],
            tour_inc=tour_inc,
            hotels=hotel_ids,
            meals=meal_ids,
            currency=CURRENCY_KZT,
            filter_value=FILTER_DEFAULT,
            partition_price=PARTITION_PRICE_DEFAULT,
            extra=extra,
        )

        async with httpx.AsyncClient() as client:
            return await fetch_all_prices(client, self.base_url, params)