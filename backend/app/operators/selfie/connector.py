"""
Selfie Travel connector. SAMO-based, same engine as Kompas/FunSun.
No login required.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import httpx

from app.operators.samo.client import SamoSearchParams, fetch_all_prices
from app.operators.selfie import config as selfie_config

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SelfieOperator:
    operator_code = selfie_config.OPERATOR_CODE

    def __init__(self, base_url: str = selfie_config.BASE_URL):
        self.base_url = base_url

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
        db: Optional["AsyncSession"] = None,  # принимаем но не используем
    ) -> list[dict]:
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
            currency=selfie_config.CURRENCY_KZT,
            filter_value=selfie_config.FILTER_DEFAULT,
            partition_price=selfie_config.PARTITION_PRICE_DEFAULT,
        )
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(20.0, connect=5.0),  # 20 сек на страницу, не 60
        ) as client:
            # Selfie требует куку сессии — получаем через инит-запрос
            await client.get(
                f"{self.base_url}/search_tour",
                params={"TOWNFROMINC": selfie_config.TOWN_FROM_ALMATY},
                timeout=httpx.Timeout(15.0, connect=5.0),
            )
            return await fetch_all_prices(client, self.base_url, params)