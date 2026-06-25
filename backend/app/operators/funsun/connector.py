"""
Thin FunSun-specific wrapper around the generic SAMO client. Mirrors
KompasOperator - same shared parsing/pagination logic in app.operators.samo,
only base_url and operator_code differ here.
"""

from __future__ import annotations

from typing import Optional

import httpx

from app.operators.funsun.config import BASE_URL
from app.operators.samo.client import SamoSearchParams, fetch_all_prices


class FunSunOperator:
    operator_code = "funsun"

    def __init__(self, base_url: str = BASE_URL):
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
    ) -> list[dict]:
        """
        Runs a (possibly multi-page) SAMO PRICES search against FunSun
        and returns the combined parsed rows as plain dicts - FunSun's
        raw, operator-native fields, NOT yet normalized into
        NormalizedTour.

        NOTE: town_from_inc / state_inc are FunSun's own SAMO codes -
        confirmed so far: TOWN_FROM_ALMATY=367408, STATE_VIETNAM=293645
        (see config.py). Same caveat as KompasOperator: no human-readable
        name resolution yet, callers pass numeric codes directly.
        """
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
        )

        async with httpx.AsyncClient() as client:
            return await fetch_all_prices(client, self.base_url, params)