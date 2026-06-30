"""
Generic async HTTP client for SAMO-based operator cabinets
(samo_action=PRICES on /search_tour). Kompas, and FunSun once its search
endpoint is confirmed to ride the same platform, both plug into this -
per-operator differences are confined to base_url and numeric ID
mappings (TOWNFROMINC, STATEINC, etc.), which live in each operator's
own config/connector module, not here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from app.operators.samo.parser import parse_samo_prices_response

DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)

# Defensive cap so a pagination/parsing bug can't spin forever against a
# live cabinet. Should never actually trigger - real Kompas searches seen
# so far topped out at 7 pages.
MAX_PAGES_SAFETY_CAP = 30


@dataclass
class SamoSearchParams:
    """
    One search request's worth of parameters, kept in SAMO's own field
    names (TOWNFROMINC, STATEINC, ...) rather than inventing a parallel
    vocabulary. Resolving human concepts ("Almaty", "Vietnam") into these
    operator-specific numeric codes is each operator connector's job,
    not this class's.
    """

    town_from_inc: int
    state_inc: int
    checkin_beg: str  # YYYYMMDD
    checkin_end: str  # YYYYMMDD
    nights_from: int
    nights_till: int
    adults: int = 2
    children: int = 0
    child_ages: list[int] = field(default_factory=list)  # AGES param, e.g. [4] for one child aged 4
    currency: int = 2  # 2 = USD, confirmed against real FunSun/Kompas traffic
    tour_inc: Optional[int] = None
    program_group_inc: Optional[int] = None
    hotels: Optional[list[int]] = None  # falsy/None -> wide search (HOTELS_ANY=1)
    meals: Optional[list[int]] = None
    rooms_any: int = 1
    freight: int = 1
    filter_value: int = 1  # confirmed against real traffic; was hardcoded to 0 before, which returned 0 rows
    moment_confirm: int = 0
    partition_price: int = 224  # confirmed against real traffic; was 160 before, which returned 0 rows
    extra: dict[str, Any] = field(default_factory=dict)  # escape hatch for one-off params

    def to_query_params(self, page: int, rev: int) -> dict[str, Any]:
        hotels_any = 0 if self.hotels else 1
        meals_any = 0 if self.meals else 1

        params: dict[str, Any] = {
            "samo_action": "PRICES",
            "TOWNFROMINC": self.town_from_inc,
            "STATEINC": self.state_inc,
            "FREIGHTTYPE": 0,
            "CHECKIN_BEG": self.checkin_beg,
            "NIGHTS_FROM": self.nights_from,
            "CHECKIN_END": self.checkin_end,
            "NIGHTS_TILL": self.nights_till,
            "ADULT": self.adults,
            "CURRENCY": self.currency,
            "CHILD": self.children,
            "AGES": ",".join(str(a) for a in self.child_ages) if self.child_ages else "",
            "TOWNS_ANY": 1,
            "townssearch": 0,
            "STARS_ANY": 1,
            "HOTELS_ANY": hotels_any,
            "hotelsearch": 0,
            "HOTELS": ",".join(str(h) for h in self.hotels) if self.hotels else "",
            "MEALS_ANY": meals_any,
            "MEALS": ",".join(str(m) for m in self.meals) if self.meals else "",
            "ROOMS_ANY": self.rooms_any,
            "ROOMS": "",
            "FREIGHT": self.freight,
            "FILTER": self.filter_value,
            "MOMENT_CONFIRM": self.moment_confirm,
            "UFILTER": "",
            "PARTITION_PRICE": self.partition_price,
            "PRICEPAGE": page,
            "DYN_SEPARATE": 1,
            "rev": rev,
            "_": int(time.time() * 1000),
        }
        if self.tour_inc is not None:
            params["TOURINC"] = self.tour_inc
        if self.program_group_inc is not None:
            params["PROGRAMGROUPINC"] = self.program_group_inc
        params.update(self.extra)
        return params


def _generate_rev() -> int:
    """
    OPEN QUESTION, not yet resolved empirically: in every captured Kompas
    response, `rev` stayed identical across PRICEPAGE values within one
    search, but we haven't confirmed whether SAMO validates this value
    server-side or accepts anything. This timestamp-based default is a
    placeholder, not a verified-safe value - if pagination starts
    returning unexpected/empty results against the live cabinet, this is
    the first thing to re-check in DevTools.
    """
    return int(time.time())


async def fetch_prices_page(
    client: httpx.AsyncClient,
    base_url: str,
    params: SamoSearchParams,
    page: int,
    rev: int,
) -> dict:
    """Fetch and parse a single PRICEPAGE of a SAMO PRICES search."""
    query = params.to_query_params(page=page, rev=rev)
    response = await client.get(
        f"{base_url}/search_tour", params=query, timeout=DEFAULT_TIMEOUT
    )
    response.raise_for_status()
    return parse_samo_prices_response(response.text)


async def fetch_all_prices(
    client: httpx.AsyncClient,
    base_url: str,
    params: SamoSearchParams,
    max_pages: int = MAX_PAGES_SAFETY_CAP,
) -> list[dict]:
    """
    Fetch every page of a SAMO PRICES search and return the combined,
    parsed rows. Stops when the page comes back empty, when SAMO's own
    pager says we've reached the last page, or when the safety cap is hit.
    
    При ошибке "could not locate ehtml" повторяет запрос до 3 раз с паузой —
    САМО иногда возвращает notify() вместо ehtml() при перегрузке.
    """
    rev = _generate_rev()
    all_rows: list[dict] = []

    page = 1
    while page <= max_pages:
        import time as _time
        _page_start = _time.monotonic()
        print(f"[samo] {base_url} page={page} starting at {_page_start:.1f}", flush=True)
        # Retry logic для случая когда САМО возвращает notify() вместо ehtml()
        result = None
        for attempt in range(2):
            result = await fetch_prices_page(client, base_url, params, page=page, rev=rev)
            if not result["error"]:
                break
            if attempt < 1:
                import asyncio
                print(
                    f"[samo] page={page} error='{result['error']}' "
                    f"attempt={attempt+1}/2 — retrying in 2s",
                    flush=True,
                )
                await asyncio.sleep(2)
                rev = _generate_rev()  # новый rev на каждую попытку

        print(f"[samo] {base_url} page={page} finished in {_time.monotonic() - _page_start:.1f}s", flush=True)
        if result["error"]:
            raise RuntimeError(f"SAMO response could not be parsed: {result['error']}")

        if result["empty"]:
            break

        new_rows = result["rows"]
        if not new_rows:
            break  # пустая страница — останавливаемся даже если total_pages говорит продолжать

        all_rows.extend(new_rows)

        total_pages = result["pagination"]["total_pages"]
        if page >= total_pages:
            break
        page += 1

    return all_rows