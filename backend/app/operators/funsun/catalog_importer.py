"""
FunSun catalog discovery.
Страны — парсятся динамически из инит-запроса (не статичный список).
Курорты — discover через broad PRICES search по каждой стране.
Новые страны подхватываются автоматически при каждом запуске.
"""
from __future__ import annotations

import asyncio
import logging
import re

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.operators.funsun import config as funsun_config

logger = logging.getLogger(__name__)

# Страны которые точно не являются направлениями — фильтруем
_SKIP_NAMES = {
    "----", "Актау", "Актобе", "Алматы", "Астана", "Атырау",
    "Караганда", "Костанай", "Уральск", "Шымкент", "Баку",
    "Ташкент", "Бишкек",
    "Блочные туры", "Туры Premium",
}
# Страны — только кириллица, без цифр, без латиницы длиннее 2 букв подряд
_COUNTRY_PATTERN = re.compile(r'^[а-яА-ЯёЁ\s\-]+$') 


async def _parse_countries_from_init(client: httpx.AsyncClient) -> dict[int, str]:
    """
    Парсит список стран из HTML инит-запроса FunSun.
    Возвращает {samo_id: normalized_name}.
    """
    r = await client.get(
        f"{funsun_config.BASE_URL}/search_tour",
        params={"TOWNFROMINC": funsun_config.TOWN_FROM_ALMATY},
        timeout=httpx.Timeout(15.0, connect=5.0),
    )
    # Ищем все option в select STATEINC
    matches = re.findall(
        r'<option value="(\d+)"[^>]*data-search-string="[^"]*"[^>]*>([^<]+)<\/option>',
        r.text,
    )
    countries: dict[int, str] = {}
    for val, name in matches:
        name = name.strip()
        samo_id = int(val)
        if not name:
            continue
        if name in _SKIP_NAMES:
            continue
        # Только чисто кириллические названия — страны всегда на русском
        if not _COUNTRY_PATTERN.match(name):
            continue
        countries[samo_id] = name
    return countries


async def _upsert_funsun_resort(
    db: AsyncSession,
    ht_place_id: int,
    location_name: str,
    country_samo_id: int,
) -> None:
    from app.models.funsun_catalog import FunSunResort

    stmt = pg_insert(FunSunResort).values(
        ht_place_id=ht_place_id,
        name=location_name,
        country_samo_id=country_samo_id,
    ).on_conflict_do_update(
        index_elements=["ht_place_id"],
        set_={"name": location_name, "country_samo_id": country_samo_id},
    )
    await db.execute(stmt)


async def discover_funsun_resorts(
    db: AsyncSession,
    operator_id: int,
) -> dict[str, int]:
    """
    1. Парсит страны из инит-запроса → upsert в funsun_country + country_mapping
    2. Broad PRICES search по каждой стране → upsert курортов в funsun_resort
    """
    import datetime as dt
    from app.models.funsun_catalog import FunSunCountry
    from app.models.mappings import CountryMapping
    from app.operators.funsun.connector import _split_date_range
    from app.operators.samo.client import SamoSearchParams, fetch_all_prices

    today = dt.date.today()

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=5.0),
        follow_redirects=True,
    ) as client:
        # Инит-запрос — получаем сессию и парсим страны
        countries = await _parse_countries_from_init(client)

        if not countries:
            logger.warning("[funsun_discover] не найдено ни одной страны в инит-запросе")
            return {}

        print(f"[funsun_discover] найдено стран: {len(countries)} → {list(countries.values())}", flush=True)

        # Upsert стран в funsun_country
        for samo_id, country_name in countries.items():
            stmt = pg_insert(FunSunCountry).values(
                samo_id=samo_id,
                name=country_name,
            ).on_conflict_do_update(
                index_elements=["samo_id"],
                set_={"name": country_name},
            )
            await db.execute(stmt)

        # Upsert стран в country_mapping (confirmed=true — scheduler сразу начнёт их собирать)
        for samo_id, country_name in countries.items():
            stmt = pg_insert(CountryMapping).values(
                operator_id=operator_id,
                raw_value=str(samo_id),
                normalized_value=country_name,
                confirmed=True,
            ).on_conflict_do_update(
                index_elements=["operator_id", "raw_value"],
                set_={"normalized_value": country_name, "confirmed": True},
            )
            await db.execute(stmt)

        await db.commit()
        logger.info("[funsun_discover] upserted %d countries", len(countries))

        totals: dict[str, int] = {}

        for samo_id, country_name in countries.items():
            print(f"[funsun_discover] country={country_name} ({samo_id})", flush=True)
            await asyncio.sleep(3)

            # Инит-запрос со страной перед PRICES
            await client.get(
                f"{funsun_config.BASE_URL}/search_tour",
                params={
                    "TOWNFROMINC": funsun_config.TOWN_FROM_ALMATY,
                    "STATEINC": samo_id,
                },
                timeout=httpx.Timeout(15.0, connect=5.0),
            )

            # FunSun лимит 10 дней — берём первый чанк для discovery
            checkin_beg = (today + dt.timedelta(days=30)).strftime("%Y%m%d")
            checkin_end = (today + dt.timedelta(days=39)).strftime("%Y%m%d")

            params = SamoSearchParams(
                town_from_inc=funsun_config.TOWN_FROM_ALMATY,
                state_inc=samo_id,
                checkin_beg=checkin_beg,
                checkin_end=checkin_end,
                nights_from=7,
                nights_till=7,
                adults=2,
                children=0,
                currency=funsun_config.CURRENCY_KZT,
                filter_value=funsun_config.FILTER_DEFAULT,
                partition_price=funsun_config.PARTITION_PRICE_DEFAULT,
            )
            try:
                rows = await fetch_all_prices(client, funsun_config.BASE_URL, params)
            except Exception as e:
                print(f"[funsun_discover] {country_name} FAILED: {e}", flush=True)
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
                    await _upsert_funsun_resort(
                        db=db,
                        ht_place_id=abs(hash(f"{samo_id}:{location_name}")) % (10**9),
                        location_name=location_name,
                        country_samo_id=samo_id,
                    )
                    await db.commit()
                    resort_count += 1
                except Exception as e:
                    await db.rollback()
                    logger.debug("funsun resort upsert skipped: %s", e)

            totals[country_name] = resort_count
            print(f"[funsun_discover] {country_name}: {resort_count} курортов", flush=True)

    return totals   