"""
Selfie Travel catalog discovery.
Reuses Kompas discovery logic — same SAMO structure.
"""
from __future__ import annotations

import asyncio
import logging
import re

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.operators.selfie import config as selfie_config


# Маппинг английских названий курортов → русские
_RESORT_EN_TO_RU: dict[str, str] = {
    "nha trang": "Нячанг",
    "da nang": "Дананг",
    "danang": "Дананг",
    "hoi an": "Хойан",
    "phu quoc": "Фукуок",
    "mui ne": "Муйне",
    "phan thiet": "Фантьет",
    "cam ranh": "Камрань",
    "hue": "Хюэ",
    "antalya": "Анталья",
    "alanya": "Аланья",
    "side": "Сиде",
    "belek": "Белек",
    "kemer": "Кемер",
    "bodrum": "Бодрум",
    "marmaris": "Мармарис",
    "fethiye": "Фетхие",
    "dubai": "Дубай",
    "abu dhabi": "Абу-Даби",
    "sharjah": "Шарджа",
    "pattaya": "Паттайя",
    "phuket": "Пхукет",
    "samui": "Самуи",
    "krabi": "Краби",
    "bali": "Бали",
    "hurghada": "Хургада",
    "sharm el sheikh": "Шарм-эль-Шейх",
    "batumi": "Батуми",
    "tbilisi": "Тбилиси",
    "male": "Мале",
}


def _normalize_resort_name(name: str) -> str:
    """Нормализует название курорта: английское → русское если есть маппинг."""
    return _RESORT_EN_TO_RU.get(name.lower().strip(), name)


async def _upsert_selfie_resort(
    db: AsyncSession,
    ht_place_id: int,
    location_name: str,
    country_id: int,
) -> None:
    """Upsert курорта Selfie в selfie_resort по ht_place_id."""
    from app.models.selfie_catalog import SelfieCountry, SelfieResort
    from sqlalchemy.dialects.postgresql import insert

    existing_country = await db.get(SelfieCountry, country_id)
    if existing_country is None:
        return

    normalized_name = _normalize_resort_name(location_name)

    stmt = insert(SelfieResort).values(
        id=ht_place_id,
        name=normalized_name,
        country_id=country_id,
    ).on_conflict_do_update(
        index_elements=["id"],
        set_={"name": normalized_name, "updated_at": func.now()},
    )
    await db.execute(stmt)

logger = logging.getLogger(__name__)

_COUNTRY_PATTERN = re.compile(r"inc:\s*'(\d+)',\s*title:\s*'([^']+)'")
_SKIP_TITLES = {"----", "Любой", "GDS туры", "Standard", "KZT", "USD", "EUR", "RUB"}


async def fetch_selfie_countries() -> dict[int, str]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{selfie_config.BASE_URL}/search_tour",
            params={"samo_action": "INIT", "TOWNFROMINC": selfie_config.TOWN_FROM_ALMATY},
        )
        r.raise_for_status()

    idx = r.text.find("STATEINC")
    if idx == -1:
        return {}

    end = r.text.find("]);", idx)
    block = r.text[idx:end]

    countries: dict[int, str] = {}
    for m in _COUNTRY_PATTERN.finditer(block):
        inc = int(m.group(1))
        title = m.group(2).strip()
        if inc == 0 or title.isdigit() or title in _SKIP_TITLES:
            continue
        if title == "----":
            break
        if any(title.startswith(p) for p in ("IND:", "GDS", "AZE:", "VIE:")):
            continue
        countries[inc] = title

    return countries


async def discover_selfie_resorts(
    db: AsyncSession,
    operator_id: int,
) -> dict[str, int]:
    """
    Runs broad PRICES search for each Selfie country and upserts resorts.
    Reuses kompas upsert_kompas_resort logic since structure is identical.
    """
    import datetime as dt
    from app.operators.samo.client import SamoSearchParams, fetch_all_prices

    today = dt.date.today()
    checkin_beg = (today + dt.timedelta(days=7)).strftime("%Y%m%d")
    checkin_end = (today + dt.timedelta(days=37)).strftime("%Y%m%d")

    countries = await fetch_selfie_countries()
    totals: dict[str, int] = {}

    # Upsert стран в selfie_country
    from app.models.selfie_catalog import SelfieCountry
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    for country_id, country_name in countries.items():
        stmt = pg_insert(SelfieCountry).values(
            id=country_id, name=country_name
        ).on_conflict_do_update(
            index_elements=["id"],
            set_={"name": country_name},
        )
        await db.execute(stmt)
    await db.commit()

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
        for country_id, country_name in countries.items():
            print(f"[selfie_discover] country={country_name} ({country_id})", flush=True)
            await asyncio.sleep(3)

            params = SamoSearchParams(
                town_from_inc=selfie_config.TOWN_FROM_ALMATY,
                state_inc=country_id,
                checkin_beg=checkin_beg,
                checkin_end=checkin_end,
                nights_from=7,
                nights_till=7,
                adults=2,
                children=0,
                currency=selfie_config.CURRENCY_KZT,
                filter_value=selfie_config.FILTER_DEFAULT,
                partition_price=selfie_config.PARTITION_PRICE_DEFAULT,
            )
            try:
                rows = await fetch_all_prices(client, selfie_config.BASE_URL, params)
            except Exception as e:
                print(f"[selfie_discover] {country_name} FAILED: {e}", flush=True)
                totals[country_name] = 0
                await asyncio.sleep(10)
                continue

            seen: set[int] = set()
            resort_count = 0
            for row in rows:
                ht_place_id = row.get("ht_place_id")
                location_name = row.get("location_name")
                if not ht_place_id or not location_name or ht_place_id in seen:
                    continue
                seen.add(ht_place_id)
                try:
                    await _upsert_selfie_resort(
                        db=db,
                        ht_place_id=ht_place_id,
                        location_name=location_name,
                        country_id=country_id,
                    )
                    await db.commit()
                    resort_count += 1
                except Exception as e:
                    await db.rollback()
                    logger.debug("selfie resort upsert skipped: %s", e) 

            totals[country_name] = resort_count

    return totals