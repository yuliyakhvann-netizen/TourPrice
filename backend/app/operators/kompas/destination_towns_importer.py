"""
Импортер городов прибытия (TOWNS) для Kompas.
Парсит HTML чекбоксы из samo_action=INIT для каждой страны
и сохраняет town_id + name в таблицу kompas_destination_town.
"""
from __future__ import annotations

import asyncio
import logging
import re

import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kompas_catalog import KompasCountry, KompasDestinationTown
from app.operators.kompas.config import BASE_URL, TOWN_FROM_ALMATY

logger = logging.getLogger(__name__)


def _parse_destination_towns(html: str) -> list[tuple[int, str]]:
    """
    Извлекает TOWNS ID и названия из HTML САМО INIT ответа.
    Города прибытия — чекбоксы с value < 10000, без class="star"/"hoteltype".
    Порядок атрибутов в HTML: <input type="checkbox" [class="..."] value="N"/>
    """
    # Unescape
    html = html.replace('\\n', '\n').replace('\\"', '"').replace('\\/', '/')

    # Ищем все input[type=checkbox] с числовым value — любой порядок атрибутов
    all_inputs = re.findall(
        r'<input type="checkbox"([^>]*)value="(\d+)"[^>]*/>\s*([^\n<]{1,80})',
        html
    )

    towns = []
    for attrs, val, after in all_inputs:
        town_id = int(val)

        # Пропускаем питание, звёзды, типы отелей по классу
        if 'star' in attrs or 'hoteltype' in attrs:
            continue

        # Пропускаем питание и спецзначения по ID (>= 10000)
        if town_id >= 10000:
            continue

        # Пропускаем групповые чекбоксы (class="group") — у них нет value обычно,
        # но на всякий случай
        if 'class="group"' in attrs:
            continue

        name = after.strip()
        if not name:
            continue

        towns.append((town_id, name))

    return towns


async def import_destination_towns_for_country(
    session: AsyncSession,
    country: KompasCountry,
    town_from_inc: int = TOWN_FROM_ALMATY,
) -> int:
    """Импортирует города прибытия для одной страны. Возвращает количество сохранённых."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{BASE_URL}/search_tour",
            params={
                "samo_action": "INIT",
                "TOWNFROMINC": str(town_from_inc),
                "STATEINC": str(country.id),
            },
        )
        r.raise_for_status()
        html = r.text

    towns = _parse_destination_towns(html)

    if not towns:
        logger.warning(f"Нет городов прибытия для страны {country.name} (id={country.id})")
        return 0

    # Удаляем старые записи для этой страны
    await session.execute(
        delete(KompasDestinationTown).where(KompasDestinationTown.country_id == country.id)
    )

    # Вставляем новые
    for town_id, name in towns:
        session.add(KompasDestinationTown(
            town_id=town_id,
            name=name,
            country_id=country.id,
        ))

    await session.flush()
    logger.info(f"Страна {country.name}: сохранено {len(towns)} городов прибытия")
    return len(towns)


async def import_all_destination_towns(session: AsyncSession) -> dict[str, int]:
    """Импортирует города прибытия для всех активных стран Kompas."""
    result = await session.execute(select(KompasCountry))
    countries = result.scalars().all()

    stats = {}
    for country in countries:
        try:
            count = await import_destination_towns_for_country(session, country)
            stats[country.name] = count
            await asyncio.sleep(1)  # пауза между запросами
        except Exception as e:
            logger.error(f"Ошибка импорта городов для {country.name}: {e}")
            stats[country.name] = 0

    await session.commit()
    return stats