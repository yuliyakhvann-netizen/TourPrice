"""
Fetches departure cities from samo_action=INIT for any SAMO operator.
Cities appear in the TOWNFROMINC dropdown block.
"""
from __future__ import annotations

import re
import logging

import httpx

logger = logging.getLogger(__name__)

_CITY_PATTERN = re.compile(r"inc:\s*'(\d+)',\s*title:\s*'([^']+)'")

_SKIP_TITLES = {
    "----", "Любой", "GDS туры", "Standard",
    "KZT", "USD", "EUR", "RUB",
}
_SKIP_PREFIXES = ("IND:", "GDS", "AZE:", "VIE:")


async def fetch_samo_departure_cities(
    base_url: str,
    town_from_inc: int,
) -> dict[int, str]:
    """
    Returns {city_inc: city_name} for all valid departure cities
    found in TOWNFROMINC block of samo_action=INIT response.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{base_url}/search_tour",
            params={"samo_action": "INIT", "TOWNFROMINC": town_from_inc},
        )
        r.raise_for_status()

    text = r.text
    idx = text.find("TOWNFROMINC")
    if idx == -1:
        logger.warning("TOWNFROMINC block not found in INIT response from %s", base_url)
        return {}

    end = text.find("]);", idx)
    block = text[idx:end]

    cities: dict[int, str] = {}
    for m in _CITY_PATTERN.finditer(block):
        inc = int(m.group(1))
        title = m.group(2).strip()

        if inc == 0:
            continue
        if title in _SKIP_TITLES:
            continue
        if title.isdigit():
            break  # дальше идут цифровые дропдауны (ночи, взрослые)
        if any(title.startswith(p) for p in _SKIP_PREFIXES):
            continue

        cities[inc] = title

    logger.info("fetch_samo_departure_cities: %s → %d cities", base_url, len(cities))
    return cities