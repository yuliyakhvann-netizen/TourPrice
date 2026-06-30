"""
Kazunion connector. САМО-based, same engine as Kompas/Selfie.
No login required. Uses STATEINC/TOWNFROMINC param naming.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import httpx

from app.operators.samo.client import SamoSearchParams, fetch_all_prices
from app.operators.kazunion import config as kazunion_config

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class KazunionOperator:
    operator_code = kazunion_config.OPERATOR_CODE

    def __init__(self, base_url: str = kazunion_config.BASE_URL):
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
            currency=kazunion_config.CURRENCY_KZT,
            filter_value=kazunion_config.FILTER_DEFAULT,
            partition_price=kazunion_config.PARTITION_PRICE_DEFAULT,
        )
        # Kazunion наблюдался зависающим на сетевом уровне посреди пагинации
        # (соединение не закрывается, дефолтный httpx timeout=60s на отдельный
        # запрос почему-то не срабатывает). Используем явный более строгий
        # таймаут на КАЖДЫЙ HTTP-запрос плюс общий лимит на весь сбор страны,
        # чтобы зависание никогда не съедало больше пары минут.
        kazunion_timeout = httpx.Timeout(20.0, connect=10.0)

        import asyncio
        import datetime as dt

        async def _do_search() -> list[dict]:
            # limits=httpx.Limits(max_keepalive_connections=0) отключает
            # переиспользование TCP-соединений — каждый запрос открывает
            # новое. Это исключает гипотезу про "мёртвый" keep-alive сокет
            # как причину зависаний на середине пагинации.
            limits = httpx.Limits(max_keepalive_connections=0, max_connections=5)
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=kazunion_timeout, limits=limits
            ) as client:
                # Инит-запрос 1: устанавливаем город вылета
                await client.get(
                    f"{self.base_url}/search_tour",
                    params={"TOWNFROMINC": kazunion_config.TOWN_FROM_ALMATY},
                )
                # Инит-запрос 2: устанавливаем страну назначения
                await client.get(
                    f"{self.base_url}/search_tour",
                    params={
                        "TOWNFROMINC": kazunion_config.TOWN_FROM_ALMATY,
                        "STATEINC": state_inc,
                    },
                )
                try:
                    beg = dt.datetime.strptime(checkin_beg, "%Y%m%d").date()
                    end = dt.datetime.strptime(checkin_end, "%Y%m%d").date()
                    window_days = (end - beg).days + 1
                except Exception:
                    window_days = 30
                max_pages = 3 if window_days <= 3 else 30
                return await fetch_all_prices(client, self.base_url, params, max_pages=max_pages)

        try:
            return await asyncio.wait_for(_do_search(), timeout=120.0)
        except asyncio.TimeoutError:
            print(
                f"[kazunion] search timed out after 120s "
                f"(state_inc={state_inc}, {checkin_beg}..{checkin_end}) — likely network hang",
                flush=True,
            )
            return []