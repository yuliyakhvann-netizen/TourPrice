"""
Kazunion catalog discovery.
Страны — статичный список из config.COUNTRIES (взяты из HTML формы).
Курорты — discover через broad PRICES search по каждой стране.
"""
from __future__ import annotations

import asyncio
import logging

import httpx
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.operators.kazunion import config as kazunion_config

logger = logging.getLogger(__name__)


async def _upsert_kazunion_resort(
    db: AsyncSession,
    ht_place_id: int,
    location_name: str,
    country_samo_id: int,
) -> None:
    from app.models.kazunion_catalog import KazunionResort

    stmt = pg_insert(KazunionResort).values(
        ht_place_id=ht_place_id,
        name=location_name,
        country_samo_id=country_samo_id,
    ).on_conflict_do_update(
        index_elements=["ht_place_id"],
        set_={"name": location_name, "country_samo_id": country_samo_id},
    )
    await db.execute(stmt)


async def discover_kazunion_resorts(
    db: AsyncSession,
    operator_id: int,
) -> dict[str, int]:
    """
    Upsert стран из config, затем broad PRICES search для каждой страны
    и upsert курортов в kazunion_resort.
    """
    import datetime as dt
    from app.operators.samo.client import SamoSearchParams, fetch_all_prices
    from app.models.kazunion_catalog import KazunionCountry

    today = dt.date.today()
    checkin_beg = (today + dt.timedelta(days=7)).strftime("%Y%m%d")
    checkin_end = (today + dt.timedelta(days=37)).strftime("%Y%m%d")

    # Upsert стран из статичного конфига
    for samo_id, country_name in kazunion_config.COUNTRIES.items():
        stmt = pg_insert(KazunionCountry).values(
            samo_id=samo_id,
            name=country_name,
        ).on_conflict_do_update(
            index_elements=["samo_id"],
            set_={"name": country_name},
        )
        await db.execute(stmt)
    await db.commit()
    logger.info(f"Kazunion: upserted {len(kazunion_config.COUNTRIES)} countries")

    totals: dict[str, int] = {}

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=5.0),
        follow_redirects=True,
    ) as client:
        # Kazunion требует куку SAMO-сессии — получаем её через инит-запрос
        await client.get(
            f"{kazunion_config.BASE_URL}/search_tour",
            params={"TOWNFROMINC": kazunion_config.TOWN_FROM_ALMATY},
            timeout=httpx.Timeout(15.0, connect=5.0),
        )
        for samo_id, country_name in kazunion_config.COUNTRIES.items():
            print(f"[kazunion_discover] country={country_name} ({samo_id})", flush=True)
            await asyncio.sleep(3)

            params = SamoSearchParams(
                town_from_inc=kazunion_config.TOWN_FROM_ALMATY,
                state_inc=samo_id,
                checkin_beg=checkin_beg,
                checkin_end=checkin_end,
                nights_from=7,
                nights_till=7,
                adults=2,
                children=0,
                currency=kazunion_config.CURRENCY_KZT,
                filter_value=kazunion_config.FILTER_DEFAULT,
                partition_price=kazunion_config.PARTITION_PRICE_DEFAULT,
            )
            try:
                rows = await fetch_all_prices(
                    client, kazunion_config.BASE_URL, params
                )
            except Exception as e:
                print(f"[kazunion_discover] {country_name} FAILED: {e}", flush=True)
                totals[country_name] = 0
                await asyncio.sleep(10)
                continue

            seen: set[str] = set()
            resort_count = 0
            for row in rows:
                location_name = row.get("location_name")
                if not location_name or location_name in seen:
                    continue
                seen.add(location_name)
                try:
                    await _upsert_kazunion_resort(
                        db=db,
                        ht_place_id=abs(hash(f"{samo_id}:{location_name}")) % (10**9),
                        location_name=location_name,
                        country_samo_id=samo_id,
                    )
                    await db.commit()
                    resort_count += 1
                except Exception as e:
                    await db.rollback()
                    logger.debug("kazunion resort upsert skipped: %s", e)

            totals[country_name] = resort_count

    return totals