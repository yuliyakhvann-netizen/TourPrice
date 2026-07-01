"""
Kazunion connector. САМО-based, same engine as Kompas/Selfie.
No login required. Uses STATEINC/TOWNFROMINC param naming.
"""
from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Optional

import httpx

from app.operators.samo.client import SamoSearchParams, fetch_all_prices
from app.operators.kazunion import config as kazunion_config

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _split_date_range(checkin_beg: str, checkin_end: str, max_days: int) -> list[tuple[str, str]]:
    """
    Разбивает диапазон YYYYMMDD..YYYYMMDD на чанки по max_days дней.
    Например: 01.07-31.07 с max_days=14 -> [(01,14), (15,28), (29,31)]
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
        # Kazunion наблюдался зависающим на сетевом уровне посреди пагинации
        # (соединение не закрывается, дефолтный httpx timeout=60s на отдельный
        # запрос почему-то не срабатывает). Используем явный более строгий
        # таймаут на КАЖДЫЙ HTTP-запрос плюс общий лимит на один чанк дат,
        # чтобы зависание никогда не съедало больше пары минут.
        kazunion_timeout = httpx.Timeout(20.0, connect=10.0)

        import asyncio

        REINIT_EVERY = 15  # пересоздаём клиент каждые 15 страниц (защитная мера)
        CHUNK_TIMEOUT = 120.0  # таймаут на один чанк дат

        # Kazunion зависает на пагинации при широком диапазоне дат (после ~16
        # страниц). Разбиваем месяц на чанки по MAX_DATE_WINDOW_DAYS (14 дней),
        # чтобы каждый чанк укладывался в <15 страниц — как у FunSun.
        chunks = _split_date_range(
            checkin_beg, checkin_end, kazunion_config.MAX_DATE_WINDOW_DAYS
        )

        async def _make_client() -> httpx.AsyncClient:
            limits = httpx.Limits(max_keepalive_connections=0, max_connections=5)
            return httpx.AsyncClient(
                follow_redirects=True, timeout=kazunion_timeout, limits=limits
            )

        async def _init_client(client: httpx.AsyncClient) -> None:
            """Два init-запроса, устанавливающие город вылета и страну."""
            await client.get(
                f"{self.base_url}/search_tour",
                params={"TOWNFROMINC": kazunion_config.TOWN_FROM_ALMATY},
            )
            await client.get(
                f"{self.base_url}/search_tour",
                params={
                    "TOWNFROMINC": kazunion_config.TOWN_FROM_ALMATY,
                    "STATEINC": state_inc,
                },
            )

        async def _do_search_chunk(chunk_beg: str, chunk_end: str) -> list[dict]:
            from app.operators.samo.client import (
                fetch_prices_page,
                _generate_rev,
                MAX_PAGES_SAFETY_CAP,
            )
            import asyncio as _asyncio

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
                currency=kazunion_config.CURRENCY_KZT,
                filter_value=kazunion_config.FILTER_DEFAULT,
                partition_price=kazunion_config.PARTITION_PRICE_DEFAULT,
            )

            try:
                beg = dt.datetime.strptime(chunk_beg, "%Y%m%d").date()
                end = dt.datetime.strptime(chunk_end, "%Y%m%d").date()
                window_days = (end - beg).days + 1
            except Exception:
                window_days = kazunion_config.MAX_DATE_WINDOW_DAYS
            max_pages = min(3 if window_days <= 3 else MAX_PAGES_SAFETY_CAP, MAX_PAGES_SAFETY_CAP)

            all_rows: list[dict] = []
            rev = _generate_rev()
            page = 1

            client = await _make_client()
            await _init_client(client)

            try:
                while page <= max_pages:
                    # Пересоздаём клиент каждые REINIT_EVERY страниц
                    if page > 1 and (page - 1) % REINIT_EVERY == 0:
                        await client.aclose()
                        print(
                            f"[kazunion] reinitializing client at page={page}",
                            flush=True,
                        )
                        client = await _make_client()
                        await _init_client(client)
                        rev = _generate_rev()

                    result = None
                    for attempt in range(2):
                        result = await fetch_prices_page(
                            client, self.base_url, params, page=page, rev=rev
                        )
                        if not result["error"]:
                            break
                        if attempt < 1:
                            print(
                                f"[kazunion] page={page} error='{result['error']}' "
                                f"attempt={attempt+1}/2 — retrying in 2s",
                                flush=True,
                            )
                            await _asyncio.sleep(2)
                            rev = _generate_rev()

                    if result["error"]:
                        raise RuntimeError(
                            f"SAMO response could not be parsed: {result['error']}"
                        )
                    if result["empty"] or not result["rows"]:
                        break

                    all_rows.extend(result["rows"])

                    total_pages = result["pagination"]["total_pages"]
                    if page >= total_pages:
                        break

                    page += 1
            finally:
                await client.aclose()

            return all_rows

        all_rows: list[dict] = []
        for chunk_beg, chunk_end in chunks:
            try:
                chunk_rows = await asyncio.wait_for(
                    _do_search_chunk(chunk_beg, chunk_end), timeout=CHUNK_TIMEOUT
                )
            except asyncio.TimeoutError:
                print(
                    f"[kazunion] chunk {chunk_beg}..{chunk_end} timed out after "
                    f"{CHUNK_TIMEOUT}s (state_inc={state_inc}) — likely network hang",
                    flush=True,
                )
                chunk_rows = []

            all_rows.extend(chunk_rows)
            print(
                f"[kazunion] chunk {chunk_beg}..{chunk_end} → {len(chunk_rows)} строк",
                flush=True,
            )

        return all_rows