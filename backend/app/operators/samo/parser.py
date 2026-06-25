"""
SAMO "PRICES" response parser.

SAMO (the CRM platform behind Kompas and, per earlier discovery, likely
FunSun) doesn't return JSON from samo_action=PRICES. It returns a small
JS snippet that calls:

    samo.jQuery(samo.controls.resultset).ehtml("<table>...</table>");

The actual tour/price data lives inside that HTML string, JSON-escaped
(double quotes, backslashes, forward slashes, newlines, unicode escapes
like \\u0442...). This module:

1. Pulls that HTML out of the raw response and unescapes it.
2. Detects the "no results" placeholder response.
3. Parses every <tr> in the results table into a flat dict using the
   data-* attributes on the row (these carry the real IDs - hotel,
   room, meal, tour, dates - far more reliably than scraping cell text).
4. Reads pagination state (current page / known page numbers) so a
   caller knows whether to keep requesting PRICEPAGE=2, 3, ...

Column layout (verified against real Kompas responses, 15 <td> cells
per row when results are present):

    0  button group (booking actions, empty on search)
    1  departure date + flight time
    2  tour/program name
    3  nights (+ "in resort" extra nights marker)
    4  hotel name/link + location
    5  availability indicator dots
    6  meal code (BB, etc.)
    7  room name + occupancy code ("Superior View / DBL")
    8  attributes marker
    9  stats/dynamics placeholder
    10 price
    11 discount icon
    12 (spacer)
    13 flight numbers ("all_prices")
    14 transport/airline name + seat availability
"""

from __future__ import annotations

import json
import re
from typing import Optional

from bs4 import BeautifulSoup

_EHTML_RE = re.compile(r'ehtml\("((?:[^"\\]|\\.)*)"\)', re.DOTALL)
_NO_DATA_MARKERS = ("Нет данных", "Уточните параметры")

_EXPECTED_CELL_COUNT = 15
_EXPECTED_CELL_COUNT_SHORT = 14  # Selfie Travel — нет колонки type_price

_TOUR_NAME_CELL_IDX = 2
_HOTEL_CELL_IDX = 4
_MEAL_CELL_IDX = 6
_ROOM_CELL_IDX = 7
_PRICE_CELL_IDX = 10
_FLIGHTS_CELL_IDX = 13
_TRANSPORT_CELL_IDX = 14

# Short layout (14 cells) — нет type_price колонки между price и flights
_FLIGHTS_CELL_IDX_SHORT = 12
_TRANSPORT_CELL_IDX_SHORT = 13


# --------------------------------------------------------------------------
# Response-level extraction
# --------------------------------------------------------------------------

def extract_html_from_response(raw_response: str) -> Optional[str]:
    """
    Pull the HTML payload out of a SAMO JS response and unescape it.
    Returns None if no ehtml(...) call is found (malformed/unexpected
    response - caller should treat this as a hard failure, not "no results").
    """
    match = _EHTML_RE.search(raw_response)
    if not match:
        return None

    escaped = match.group(1)
    # SAMO's escaping (quotes, backslashes, forward slashes, newlines,
    # \\uXXXX unicode escapes) is valid JSON string escaping, so wrapping in quotes and handing it to json.loads is
    # both simpler and safer than a hand-rolled unescaper.
    try:
        return json.loads(f'"{escaped}"')
    except json.JSONDecodeError:
        # Fallback for any odd escape sequence json.loads rejects.
        return (
            escaped.replace('\\/', '/')
            .replace('\\"', '"')
            .replace('\\n', '\n')
            .encode('utf-8')
            .decode('unicode_escape')
        )


def is_empty_result(html: str) -> bool:
    """True if this is SAMO's 'no results, refine your search' placeholder."""
    return any(marker in html for marker in _NO_DATA_MARKERS) and '<table' not in html


def parse_pagination(html: str) -> dict:
    """
    Extract pager state: current page and the full set of page numbers
    SAMO has rendered links for (this is how many PRICEPAGE values exist
    for the current `rev`, not necessarily the true total - SAMO doesn't
    seem to show e.g. "8" until you've paged closer to it - but it has
    been the reliable upper bound in every sample seen so far).
    """
    soup = BeautifulSoup(html, "lxml")
    pager = soup.select_one("div.pager")
    if not pager:
        return {"current_page": 1, "total_pages": 1, "pages": [1]}

    pages = []
    current_page = 1
    for el in pager.find_all("span"):
        classes = el.get("class", [])
        if "current_page" in classes:
            current_page = _to_int(el.get_text(strip=True)) or 1
            pages.append(current_page)
        elif el.has_attr("data-page"):
            page_num = _to_int(el["data-page"])
            if page_num is not None:
                pages.append(page_num)

    pages = sorted(set(pages)) or [1]
    return {"current_page": current_page, "total_pages": pages[-1], "pages": pages}


# --------------------------------------------------------------------------
# Row-level parsing
# --------------------------------------------------------------------------

def _to_int(value) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _split_hotel_cell(cell) -> dict:
    """
    Hotel cell is either:
        plain text:        "SK Hotel Phu Quoc 2*\n(Фукуок)"
    or with a redirect link: <a href="...">Tahiti Central Hotel, 3*</a>\n(Duong Dong)

    Star rating is embedded in the name text, not a separate field, so
    pull it out with a regex rather than expecting a clean attribute.
    """
    link = cell.find("a")
    hotel_url = link.get("href") if link else None

    full_text = cell.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in full_text.split("\n") if line.strip()]

    hotel_name = lines[0] if lines else None
    location_name = lines[1].strip("()") if len(lines) > 1 else None

    stars = None
    if hotel_name:
        star_match = re.search(r"(\d)\s*\*\+?", hotel_name)
        if star_match:
            stars = int(star_match.group(1))

    return {
        "hotel_name_raw": hotel_name,
        "hotel_url": hotel_url,
        "location_name": location_name,
        "stars": stars,
    }


def _extract_tour_name(cell) -> Optional[str]:
    """
    The tour/program name cell looks like:

        <td class="tour">
            Nha Trang from Almaty Air Astana FS
            <span class="helpalt link" data-popup="PROMO">...</span>
            <br><span class="icon tr_27060"></span>
        </td>

    The name itself is the first direct text node in the cell, before
    the PROMO badge markup. Taking cell.get_text() instead would also
    pull in nested <span>/<script> text (e.g. "PROMO", "ПРОМО"), so we
    grab only that first text node.

    This is currently used only to preserve the raw string (e.g. for
    later airline extraction) - no parsing of the name's internal
    structure (airline, route) happens here yet; that needs more real
    examples before it can be done reliably.
    """
    for node in cell.contents:
        if isinstance(node, str) and node.strip():
            return node.strip()
    return None


def _extract_occupancy_from_class(tr) -> dict:
    """
    Adult/child counts aren't exposed as data-* attributes - they only
    appear as tokens in the row's class list (e.g. "adult-2 child-0"),
    alongside other key-N tokens that just duplicate the data-*
    attributes (townFromKey-367408, stateKey-293645, etc). BeautifulSoup
    already splits class into a list of tokens, so no regex on a raw
    string is needed - just scan the tokens.
    """
    classes = tr.get("class", [])
    adults = None
    children = None
    for token in classes:
        if token.startswith("adult-"):
            adults = _to_int(token.split("-", 1)[1])
        elif token.startswith("child-"):
            children = _to_int(token.split("-", 1)[1])
    return {"adults": adults, "children": children}


def _split_room_cell(cell) -> dict:
    """'Superior Garden View / DBL' -> room name + occupancy code."""
    text = cell.get_text(strip=True)
    if "/" in text:
        name, _, occupancy = text.rpartition("/")
        return {"room_name_raw": name.strip(), "occupancy_code": occupancy.strip()}
    return {"room_name_raw": text or None, "occupancy_code": None}


def _parse_price_cell(cell) -> dict:
    """
    <td class="td_price">
      <span data-cat-price="1378.79" data-cat-currency="2"
            data-converted-price-number="685259" data-currency="1"
            data-currency_title="KZT" class="price expand price_button">
        685 259 KZT
      </span>
    </td>

    A "stop" class (instead of "expand price_button") plus a title
    attribute means the variant is shown but not currently bookable -
    e.g. title="Остановка продаж на проживание с 23.10.2025 по 31.12.2026".
    This must be tracked (is_bookable) so refresh jobs don't treat dead
    listings as live prices.
    """
    span = cell.find("span", attrs={"data-converted-price-number": True})
    if not span:
        return {
            "price_value": None,
            "price_currency_code": None,
            "price_currency_title": None,
            "price_category_value": None,
            "price_category_currency_code": None,
            "is_bookable": None,
            "sale_stop_note": None,
        }

    classes = span.get("class", [])
    is_stopped = "stop" in classes

    return {
        "price_value": _to_float(span.get("data-converted-price-number")),
        "price_currency_code": span.get("data-currency"),
        "price_currency_title": span.get("data-currency_title"),
        "price_category_value": _to_float(span.get("data-cat-price")),
        "price_category_currency_code": span.get("data-cat-currency"),
        "is_bookable": not is_stopped,
        "sale_stop_note": span.get("title") if is_stopped else None,
    }


def parse_row(tr) -> dict:
    """Parse a single <tr> from the results table into a flat dict."""
    attrs = tr.attrs

    result = {
        # IDs and dates straight from data-* attributes - these are the
        # ground truth, far more reliable than scraping visible text.
        "town_from_id": _to_int(attrs.get("data-townfrom")),
        "state_id": _to_int(attrs.get("data-state")),
        "state_from_id": _to_int(attrs.get("data-statefrom")),
        "checkin_date": attrs.get("data-checkin"),  # YYYYMMDD string
        "nights": _to_int(attrs.get("data-nights")),
        "hotel_nights": _to_int(attrs.get("data-hnights")),
        "tour_id": _to_int(attrs.get("data-tour")),
        "program_type_id": _to_int(attrs.get("data-ptype")),
        "packet_type": _to_int(attrs.get("data-packet-type")),
        "hotel_id": _to_int(attrs.get("data-hotel")),
        "room_id": _to_int(attrs.get("data-room")),
        "meal_id": _to_int(attrs.get("data-meal")),
        "ht_place_id": _to_int(attrs.get("data-htplace")),
        # Opaque server-side booking/slot token - not needed for price
        # comparison, kept around in case it's needed for a future
        # "go to booking" deep link.
        "cat_claim_token": attrs.get("data-cat-claim"),
    }
    result.update(_extract_occupancy_from_class(tr))

    cells = tr.find_all("td")
    n = len(cells)

    if n >= _EXPECTED_CELL_COUNT:
        flights_idx = _FLIGHTS_CELL_IDX
        transport_idx = _TRANSPORT_CELL_IDX
    elif n >= _EXPECTED_CELL_COUNT_SHORT:
        flights_idx = _FLIGHTS_CELL_IDX_SHORT
        transport_idx = _TRANSPORT_CELL_IDX_SHORT
    else:
        result["_parse_warning"] = (
            f"expected {_EXPECTED_CELL_COUNT_SHORT} cells, got {n}"
        )
        return result

    result["tour_name_raw"] = _extract_tour_name(cells[_TOUR_NAME_CELL_IDX])
    result.update(_split_hotel_cell(cells[_HOTEL_CELL_IDX]))
    result["meal_code"] = cells[_MEAL_CELL_IDX].get_text(strip=True) or None
    result.update(_split_room_cell(cells[_ROOM_CELL_IDX]))
    result.update(_parse_price_cell(cells[_PRICE_CELL_IDX]))
    result["flight_numbers"] = cells[flights_idx].get_text(strip=True) or None

    transport_name_el = cells[transport_idx].find("span", class_="name")
    result["transport_name"] = (
        transport_name_el.get_text(strip=True) if transport_name_el else None
    )

    return result


def parse_price_rows(html: str) -> list[dict]:
    """Parse all result rows out of a PRICES response's HTML payload."""
    if is_empty_result(html):
        return []
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("table.res tbody tr")
    return [parse_row(tr) for tr in rows]


# --------------------------------------------------------------------------
# Top-level entry point
# --------------------------------------------------------------------------

def parse_samo_prices_response(raw_response: str) -> dict:
    """
    Takes a raw SAMO PRICES JS response (exactly what comes back over the
    wire) and returns parsed rows + pagination state, ready to feed into
    RawResult / NormalizedTour construction upstream.
    """
    html = extract_html_from_response(raw_response)
    if html is None:
        return {
            "rows": [],
            "pagination": {"current_page": 1, "total_pages": 1, "pages": [1]},
            "empty": True,
            "error": "could not locate ehtml(...) payload in response",
        }

    empty = is_empty_result(html)
    return {
        "rows": [] if empty else parse_price_rows(html),
        "pagination": parse_pagination(html),
        "empty": empty,
        "error": None,
    }