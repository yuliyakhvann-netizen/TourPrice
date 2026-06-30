"""
FunSun connector. САМО-based, same engine as Kompas/Selfie/Kazunion.
Требует инит-запрос перед PRICES (как Kazunion).
CURRENCY=11 (KZT), PARTITION_PRICE=224.
ВАЖНО: FunSun принимает максимум 10 дней в одном запросе.
Connector автоматически разбивает диапазон на чанки по MAX_DATE_WINDOW_DAYS.
"""
from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Optional

import httpx

from app.operators.samo.client import SamoSearchParams, fetch_all_prices
from app.operators.funsun import config as funsun_config

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _split_date_range(checkin_beg: str, checkin_end: str, max_days: int) -> list[tuple[str, str]]:
    """
    Разбивает диапазон YYYYMMDD..YYYYMMDD на чанки по max_days дней.
    Например: 01.08–31.08 с max_days=10 → [01–10, 11–20, 21–31]
    """
    beg = dt.datetime.strptime(checkin_beg, "%Y%m%d").date()
    end = dt.datetime.strptime(checkin_end, "%Y%m%d").date()
    chunks = []
    cursor = beg
    while cursor <= end:
        chunk_end = min(cursor + dt.timedelta(days=max_days - 1), end)
        chunks.append((cursor.strftime("%Y%m%d"), chunk_end.strftime("%Y%m%d")))
        cursor = chunk_end + dt.timedelta(days=1)
    return chunks


class FunSunOperator:
    operator_code = funsun_config.OPERATOR_CODE

    def __init__(self, base_url: str = funsun_config.BASE_URL):
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
        db: Optional["AsyncSession"] = None,
    ) -> list[dict]:
        chunks = _split_date_range(
            checkin_beg, checkin_end, funsun_config.MAX_DATE_WINDOW_DAYS
        )

        all_rows: list[dict] = []

        async with httpx.AsyncClient(follow_redirects=True) as client:
            # Инит-запрос 1: устанавливаем город вылета
            await client.get(
                f"{self.base_url}/search_tour",
                params={"TOWNFROMINC": funsun_config.TOWN_FROM_ALMATY},
                timeout=httpx.Timeout(15.0, connect=5.0),
            )
            # Инит-запрос 2: устанавливаем страну назначения
            await client.get(
                f"{self.base_url}/search_tour",
                params={
                    "TOWNFROMINC": funsun_config.TOWN_FROM_ALMATY,
                    "STATEINC": state_inc,
                },
                timeout=httpx.Timeout(15.0, connect=5.0),
            )

            for chunk_beg, chunk_end in chunks:
                params = SamoSearchParams(
                    town_from_inc=town_from_inc,
                    state_inc=state_inc,
                    checkin_beg=chunk_beg,
                    checkin_end=chunk_end,
                    nights_from=nights_from,
                    nights_till=nights_till,
                    adults=adults,
                    children=children,
                    child_ages=child_ages or [],
                    tour_inc=tour_inc,
                    hotels=hotel_ids,
                    meals=meal_ids,
                    currency=funsun_config.CURRENCY_KZT,
                    filter_value=funsun_config.FILTER_DEFAULT,
                    partition_price=funsun_config.PARTITION_PRICE_DEFAULT,
                )
                chunk_days = (dt.datetime.strptime(chunk_end, "%Y%m%d").date() - dt.datetime.strptime(chunk_beg, "%Y%m%d").date()).days + 1
                max_pages = 3 if chunk_days <= 3 else 30
                rows = await fetch_all_prices(client, self.base_url, params, max_pages=max_pages)
                all_rows.extend(rows)
                print(
                    f"[funsun] chunk {chunk_beg}..{chunk_end} → {len(rows)} строк",
                    flush=True,
                )

        return all_rows