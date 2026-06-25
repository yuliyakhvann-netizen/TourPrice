"""
Kompas catalog discovery.

Countries: fetched once from samo_action=INIT (returns ~40 countries with
their STATEINC codes). Run periodically (weekly) to catch new destinations.

Resorts: discovered incrementally from PRICES search results — each row
contains ht_place_id (resort id) and location_name (resort name). These
are upserted here and registered in city_mapping for cross-operator matching.

Unlike Pegas (which has a full catalog endpoint), Kompas builds its resort
list organically as searches run. The discovery job runs a broad PRICES
search for each known country to populate resorts.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import asyncio

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kompas_catalog import KompasCountry, KompasResort
from app.operators.kompas import config as kompas_config
from app.repositories.mapping_repo import CityMappingRepository

logger = logging.getLogger(__name__)

INIT_URL = f"{kompas_config.BASE_URL}/search_tour"

# Matches: {inc: '32', title: 'Вьетнам', ...}
_COUNTRY_PATTERN = re.compile(r"inc:\s*'(\d+)',\s*title:\s*'([^']+)'")

# Country IDs to skip — non-country entries in SAMO dropdown
_SKIP_IDS = {0, 253, 1, 2, 3}
_SKIP_TITLES = {"----", "Любой", "GDS туры", "Standard", "KZT", "USD", "EUR"}


async def fetch_kompas_countries() -> dict[int, str]:
    """
    Fetches country list from samo_action=INIT.
    Returns {country_id: country_name} for real destination countries only.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            INIT_URL,
            params={"samo_action": "INIT", "TOWNFROMINC": kompas_config.TOWN_FROM_ALMATY},
        )
        r.raise_for_status()

    idx = r.text.find("STATEINC")
    if idx == -1:
        logger.warning("STATEINC block not found in Kompas INIT response")
        return {}

    end = r.text.find("]);", idx)
    block = r.text[idx:end]

    countries: dict[int, str] = {}
    for m in _COUNTRY_PATTERN.finditer(block):
        inc = int(m.group(1))
        title = m.group(2).strip()
        if inc in _SKIP_IDS or title in _SKIP_TITLES:
            continue
        # Skip numeric-only titles (ночи, взрослые из других дропдаунов)
        if title.isdigit():
            continue
        # Skip IND: dynamic packages and similar non-country entries
        if title.startswith("IND:") or title.startswith("GDS"):
            continue
        # Stop at separator (второй ---- означает конец списка стран)
        if title == "----":
            break
        countries[inc] = title

    logger.info("Discovered %d countries from Kompas INIT", len(countries))
    return countries


async def import_kompas_countries(db: AsyncSession) -> int:
    """
    Imports countries from Kompas INIT into kompas_country table.
    Returns number of new rows inserted.
    """
    countries = await fetch_kompas_countries()
    count = 0
    for country_id, name in countries.items():
        existing = await db.get(KompasCountry, country_id)
        if existing is None:
            db.add(KompasCountry(id=country_id, name=name))
            count += 1
        else:
            existing.name = name
    await db.commit()
    logger.info("Kompas countries import complete: %d new rows", count)
    return count


async def upsert_kompas_resort(
    db: AsyncSession,
    operator_id: int,
    ht_place_id: int,
    location_name: str,
    country_id: int,
) -> None:
    """
    Upserts a resort discovered from a PRICES search result.
    Called by NormalizationService for each Kompas search row.
    Also registers resort name in city_mapping for cross-operator matching.
    """
    existing = await db.get(KompasResort, ht_place_id)
    if existing is None:
        db.add(KompasResort(id=ht_place_id, name=location_name, country_id=country_id))
    else:
        existing.name = location_name
        existing.country_id = country_id

    city_repo = CityMappingRepository(db)
    await city_repo.get_or_create(
        operator_id=operator_id,
        raw_value=str(ht_place_id),
        suggested=location_name,
    )

async def discover_kompas_resorts(
    db: AsyncSession,
    operator_id: int,
    town_from_inc: int = kompas_config.TOWN_FROM_ALMATY,
) -> dict[str, int]:
    """
    Runs a broad PRICES search for each known country in kompas_country
    and upserts all resorts found in results.

    Uses a near-term date window just to get any results — we only care
    about ht_place_id/location_name, not actual prices here.

    Returns counts: {country_name: resorts_found}
    """
    import datetime as dt
    from sqlalchemy import select as sa_select
    from app.operators.samo.client import SamoSearchParams, fetch_all_prices

    today = dt.date.today()
    checkin_beg = (today + dt.timedelta(days=7)).strftime("%Y%m%d")
    checkin_end = (today + dt.timedelta(days=37)).strftime("%Y%m%d")

    result = await db.execute(sa_select(KompasCountry))
    countries = result.scalars().all()

    totals: dict[str, int] = {}

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
        for country in countries:
            params = SamoSearchParams(
                town_from_inc=town_from_inc,
                state_inc=country.id,
                checkin_beg=checkin_beg,
                checkin_end=checkin_end,
                nights_from=7,
                nights_till=7,
                adults=2,
                children=0,
                currency=1,
                filter_value=1,
                partition_price=160,
            )
            print(f"[discover_resorts] searching country={country.name} ({country.id})...", flush=True)
            await asyncio.sleep(3)  # пауза между странами — избегаем rate limiting
            try:
                rows = await fetch_all_prices(client, kompas_config.BASE_URL, params)
            except Exception as e:
                print(f"[discover_resorts] country={country.name} FAILED: {e}", flush=True)
                totals[country.name] = 0
                await asyncio.sleep(10)  # дополнительная пауза после ошибки
                continue

            seen: set[int] = set()
            resort_count = 0
            for row in rows:
                ht_place_id = row.get("ht_place_id")
                location_name = row.get("location_name")
                if not ht_place_id or not location_name:
                    continue
                if ht_place_id in seen:
                    continue
                seen.add(ht_place_id)
                try:
                    await upsert_kompas_resort(
                        db=db,
                        operator_id=operator_id,
                        ht_place_id=ht_place_id,
                        location_name=location_name,
                        country_id=country.id,
                    )
                    await db.commit()
                    resort_count += 1
                except Exception as e:
                    await db.rollback()
                    print(f"[discover_resorts] resort upsert skipped ht_place_id={ht_place_id} {location_name}: {e}", flush=True)
            logger.info("discover_kompas_resorts: %s → %d resorts", country.name, resort_count)
            totals[country.name] = resort_count

    return totals