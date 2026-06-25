"""
Imports the Pegas catalog (countries, resorts, hotels, airlines) from
/PackageSearch/Search into normalized tables.

IMPORTANT (discovered via DevTools, see project chat history):
GetInitialOptions was the originally-assumed source for this (per the
project's first design pass) but turned out to be a dead end: calling it
with a filled-in `search` body always returns "Unexpected request body",
and calling it with search=null only ever returns reference data scoped to
whatever destination was last selected in the live browser session - it has
no usable "give me everything" mode and no separate field listing all
countries.

/PackageSearch/Search, by contrast, returns a `Reference` block (not `re` -
that was an earlier, incorrect guess at the field name) alongside the
search Items, shaped as:
  Reference.soitni                    : flat {id: name} map
  Reference.IdToHotelIndex            : {hotel_id: {Id, CategoryGroupId,
                                         LocationId, AttributeIds, ...}}
  Reference.LocationIdToRegionIdIndex : {location_id: region_id}
  Reference.RegionIdToCountryIdIndex  : {region_id: country_id}
We call Search once per seed country (with a near-term date window that
only affects "what's bookable now", not which hotels exist) and discard the
Items, using Reference purely as a catalog source.

The list of countries to import is a hardcoded seed list (PEGAS_SEED_COUNTRIES
below) rather than something fetched from the API, since no full country
registry endpoint has been found yet. Extend this list as new destinations
are needed - it mirrors the operator's "departure/destination" country ids
visible in Search payloads (e.g. Turkey=73, Vietnam=156, Cyprus=6866).

Cross-operator destination matching: unlike SAMO (FunSun/Kompas), where city/
country codes are opaque numbers requiring a human to confirm what they mean,
Pegas resort names are already human-readable (e.g. "Нячанг"). We still
register every resort name into the existing per-operator CityMapping table
(operator_id, raw_value, normalized_value, confirmed) - the same mechanism
FunSun/Kompas use - so that a profile's destination name can be resolved to
this operator's resort consistently. We pre-fill `suggested` with the resort
name itself (since there's nothing to translate), but a manager must still
click confirm before live search will use the mapping (CityMappingRepository.
get_raw_value only returns confirmed rows).

This is a full-catalog snapshot import, not an incremental mapping workflow:
every run upserts by id. Re-run periodically (e.g. weekly) since hotels open/
close and categories change over time.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pegas_catalog import PegasAirline, PegasCountry, PegasDepartureLocation, PegasHotel, PegasResort
from app.operators.pegas import config as pegas_config
from app.repositories.mapping_repo import CityMappingRepository

logger = logging.getLogger(__name__)

# country_id -> display name. Extend as new destinations are added.
PEGAS_SEED_COUNTRIES: dict[int, str] = {
    73: "Турция",
    156: "Вьетнам",
    6866: "Кипр",
    1071: "Азербайджан",
    3818574: "Грузия",
    159: "Казахстан",
    2481427: "Мальдивы",
    162: "ОАЭ",
    72: "Россия",
    164: "Таиланд",
    122410934: "Узбекистан",
}


async def fetch_search_catalog_for_country(
    cookies: list[dict], country_id: int
) -> dict[str, Any]:
    """
    Calls /PackageSearch/Search (NOT GetInitialOptions - confirmed via
    DevTools that GetInitialOptions with a filled-in search body always
    returns "Unexpected request body", while Search's response includes the
    same re.soitni / re.ho.op / re.ai catalog data alongside the actual
    Items list). We use it purely as a catalog source here and ignore Items.
    """
    cookie_dict = {c["name"]: c["value"] for c in cookies}

    async with httpx.AsyncClient(
        base_url=pegas_config.BASE_URL,
        headers=pegas_config.DEFAULT_HEADERS,
        cookies=cookie_dict,
        timeout=60.0,
    ) as client:
        today = dt.date.today()
        upcoming_dates = [(today + dt.timedelta(days=i)).isoformat() for i in range(1, 8)]

        response = await client.post(
            pegas_config.SEARCH_PATH,
            json={
                "DepartureLocationId": 553,
                "ReturnLocationId": 553,
                "DestinationCountryId": country_id,
                "DestinationLocationId": None,
                "Adults": 2,
                "ChildAges": [],
                "AirlineIds": [],
                "BasicFares": False,
                "DepartureDates": upcoming_dates,
                "DirectFlightsOnly": False,
                "DurationsInNights": [5, 6, 7],
                "FlightAvailabilityAvailable": True,
                "FlightAvailabilityOnRequest": True,
                "GroupByHotel": False,
                "HotelAttributeIds": None,
                "HotelAvailabilityAvailable": True,
                "HotelAvailabilityOnRequest": True,
                "HotelCategoryGroupIds": None,
                "HotelIds": None,
                "HotelLocationAreaIds": None,
                "HotelLocationIds": None,
                "HotelMealGroupIds": None,
                "HotelRegionIds": None,
                "LanguageCode": None,
                "MaxPrice": None,
                "MinPrice": None,
                "OutgoingDatesPeriodModel": {
                    "days": 0,
                    "min": upcoming_dates[0],
                    "max": upcoming_dates[-1],
                },
                "OutgoingFlightClassId": None,
                "OutgoingFlightClassType": None,
                "PackageId": None,
                "PackageSpoTypeIds": [],
                "PaymentCurrencyId": 8168284,
                "RenderAlternativeReturnLocations": True,
                "ReturnDates": [],
                "ReturnDatesPeriodModel": None,
                "ReturnFlightClassId": None,
                "ReturnFlightClassType": None,
                "ShowPackagesWithExternalServices": False,
            },
        )
        if response.status_code >= 400:
            logger.error("Search error body (country_id=%s): %s", country_id, response.text[:2000])
        response.raise_for_status()
        return response.json()


def _resolve_category_label(category_group_id: int | None, soitni: dict[str, str]) -> str | None:
    if category_group_id is None:
        return None
    return soitni.get(str(category_group_id))


async def _upsert_country(db: AsyncSession, country_id: int, name: str) -> bool:
    """Returns True if a new row was inserted, False if an existing row was updated."""
    existing = await db.get(PegasCountry, country_id)
    if existing is None:
        db.add(PegasCountry(id=country_id, name=name))
        return True
    existing.name = name
    return False


async def _import_one_country(
    db: AsyncSession,
    cookies: list[dict],
    country_id: int,
    country_name: str,
    operator_id: int,
) -> dict[str, int]:
    """
    Parses the Search response's `Reference` block (see module docstring -
    this is what actually carries catalog data, not a top-level `re` key).

    Reference shape (confirmed via live response, country_id=73/156/6866):
      Reference.soitni              : flat {id: name} map, same role as in
                                       the old GetInitialOptions exploration
      Reference.IdToHotelIndex      : {hotel_id: {Id, CategoryGroupId,
                                       LocationId, AttributeIds, ...}}
                                       LocationId here is the hotel's own
                                       resort/town (e.g. Belek, Side) - NOT
                                       to be confused with departure
                                       locations like Almaty (553).
      Reference.LocationIdToRegionIdIndex : {location_id: region_id}
      Reference.RegionIdToCountryIdIndex  : {region_id: country_id}
    Chaining hotel.LocationId -> LocationIdToRegionIdIndex ->
    RegionIdToCountryIdIndex gives the hotel's true country, which we use to
    sanity-check against the country_id we searched for (a hotel's resort
    should always resolve back to the country we requested).
    """
    counts = {"countries": 0, "resorts": 0, "hotels": 0, "airlines": 0}
    city_mapping_repo = CityMappingRepository(db)

    if await _upsert_country(db, country_id, country_name):
        counts["countries"] += 1

    payload = await fetch_search_catalog_for_country(cookies, country_id)
    re_data = payload.get("re") or payload.get("Reference")
    if re_data is None:
        logger.warning(
            "country_id=%s: Search response has neither 're' nor 'Reference' key — "
            "skipping catalog import for this country this run.",
            country_id,
        )
        return counts

    soitni: dict[str, str] = re_data.get("soitni", {})
    id_to_hotel: dict[str, dict[str, Any]] = re_data.get("IdToHotelIndex", {})
    location_to_region: dict[str, int] = re_data.get("LocationIdToRegionIdIndex", {})
    region_to_country: dict[str, int] = re_data.get("RegionIdToCountryIdIndex", {})
    airlines_index: dict[str, Any] = re_data.get("IdToAirlineIndex", {})

    seen_resort_ids: set[int] = set()

    for hotel_id_str, hotel_record in id_to_hotel.items():
        hotel_id = hotel_record.get("Id")
        location_id = hotel_record.get("LocationId")
        category_group_id = hotel_record.get("CategoryGroupId")

        if hotel_id is None:
            continue

        # location_id here is the resort/town the hotel is in (e.g. Belek),
        # which is what we store as pegas_resort.
        resort_id = location_id
        resolved_region_id = location_to_region.get(str(location_id)) if location_id else None
        resolved_country_id = (
            region_to_country.get(str(resolved_region_id)) if resolved_region_id else None
        )
        if resolved_country_id is not None and resolved_country_id != country_id:
            logger.debug(
                "hotel_id=%s resolves to country_id=%s via location chain, "
                "expected %s — keeping it under the requested country anyway "
                "(resort may legitimately belong to a sub-region indexed "
                "differently); this is informational, not an error.",
                hotel_id,
                resolved_country_id,
                country_id,
            )

        if resort_id is not None and resort_id not in seen_resort_ids:
            resort_name = soitni.get(str(resort_id))
            if resort_name is None:
                logger.warning(
                    "country_id=%s: no soitni name found for resort_id=%s; skipping resort row",
                    country_id,
                    resort_id,
                )
            else:
                existing_resort = await db.get(PegasResort, resort_id)
                if existing_resort is None:
                    db.add(PegasResort(id=resort_id, name=resort_name, country_id=country_id))
                    counts["resorts"] += 1
                else:
                    existing_resort.name = resort_name
                    existing_resort.country_id = country_id

                # Register this resort as an unconfirmed city_mapping row so a
                # manager can later confirm it against the cross-operator
                # normalized destination name (same workflow as FunSun/Kompas).
                await city_mapping_repo.get_or_create(
                    operator_id=operator_id,
                    raw_value=resort_name,
                    suggested=resort_name,
                )
            seen_resort_ids.add(resort_id)

        hotel_name = soitni.get(str(hotel_id))
        if hotel_name is None:
            logger.warning(
                "country_id=%s: no soitni name found for hotel_id=%s; skipping",
                country_id,
                hotel_id,
            )
            continue

        category_label = _resolve_category_label(category_group_id, soitni)
        # Meal group info isn't present per-hotel in this response shape
        # (unlike the originally-explored GetInitialOptions ho.op records) -
        # left empty for now; can be backfilled from a hotel-detail call
        # later if meal-type filtering by hotel turns out to be needed.
        meal_group_ids: list[int] = []

        existing_hotel = await db.get(PegasHotel, hotel_id)
        if existing_hotel is None:
            db.add(
                PegasHotel(
                    id=hotel_id,
                    name=hotel_name,
                    resort_id=resort_id,
                    category_group_id=category_group_id,
                    category_label=category_label,
                    meal_group_ids=meal_group_ids,
                )
            )
            counts["hotels"] += 1
        else:
            existing_hotel.name = hotel_name
            existing_hotel.resort_id = resort_id
            existing_hotel.category_group_id = category_group_id
            existing_hotel.category_label = category_label
            existing_hotel.meal_group_ids = meal_group_ids

    for airline_id_str in airlines_index:
        airline_id = int(airline_id_str)
        airline_name = soitni.get(airline_id_str)
        if airline_name is None:
            logger.warning("No soitni name found for airline_id=%s; skipping", airline_id)
            continue
        existing_airline = await db.get(PegasAirline, airline_id)
        if existing_airline is None:
            db.add(PegasAirline(id=airline_id, name=airline_name))
            counts["airlines"] += 1
        else:
            existing_airline.name = airline_name

    # Сохраняем питание из soitni в meal_mapping
    # Pegas передаёт MealId числом — ищем в soitni названия
    # Известные meal ID диапазоны: небольшие числа (7000, 3205 и т.д.)
    # Определяем по тому что значение содержит ключевые слова питания
    MEAL_KEYWORDS = {
        "без питания": "Room Only",
        "room only": "Room Only",
        "завтрак": "Bed & Breakfast",
        "bed & breakfast": "Bed & Breakfast",
        "bed&breakfast": "Bed & Breakfast",
        "полупансион": "Half Board",
        "half board": "Half Board",
        "пансион": "Full Board",
        "full board": "Full Board",
        "all inclusive": "All Inclusive",
        "всё включено": "All Inclusive",
        "ultra all inclusive": "Ultra All Inclusive",
        "ультра всё включено": "Ultra All Inclusive",
    }

    from app.models.mappings import MealMapping
    from sqlalchemy import select as sa_select

    for soitni_id, soitni_name in soitni.items():
        name_lower = soitni_name.lower()
        normalized = None
        for keyword, meal_name in MEAL_KEYWORDS.items():
            if keyword in name_lower:
                normalized = meal_name
                break
        if normalized is None:
            continue

        # Сохраняем по числовому коду
        existing = await db.execute(
            sa_select(MealMapping).where(MealMapping.raw_value == soitni_id)
        )
        meal_row = existing.scalar_one_or_none()
        if meal_row is None:
            db.add(MealMapping(
                raw_value=soitni_id,
                normalized_value=normalized,
                confirmed=True,
            ))
            counts.setdefault("meals", 0)
            counts["meals"] += 1
        else:
            if not meal_row.confirmed:
                meal_row.normalized_value = normalized
                meal_row.confirmed = True

    return counts


async def fetch_departure_locations(cookies: list[dict]) -> dict:
    """
    Вызывает Layout/GetTourOperatorOfficeOptions — возвращает полный список
    городов вылета в ReferenceDescription.Locations с IATA-кодами и
    TopLocationIds (топ-5: Алматы, Астана, Шымкент, Актобе, Караганда).
    Подтверждено через DevTools: именно этот endpoint содержит
    ReferenceDescription, в отличие от GetOptions (там сокращённые ключи).
    """
    cookie_dict = {c["name"]: c["value"] for c in cookies}
    async with httpx.AsyncClient(
        base_url=pegas_config.BASE_URL,
        headers=pegas_config.DEFAULT_HEADERS,
        cookies=cookie_dict,
        timeout=30.0,
    ) as client:
        response = await client.post(
            "/Layout/GetTourOperatorOfficeOptions",
            json={},
        )
        response.raise_for_status()
        return response.json()


async def import_pegas_departure_locations(
    db: AsyncSession,
    cookies: list[dict],
) -> int:
    data = await fetch_departure_locations(cookies)
    ref = data.get("ReferenceDescription") or {}
    locations = ref.get("Locations") or []
    top_ids: set[int] = set(data.get("TopLocationIds") or [])

    count = 0
    for loc in locations:
        loc_id = loc.get("Id")
        name = loc.get("Name")
        if loc_id is None or not name:
            continue

        airport_code = loc.get("Code") or None
        if airport_code == "":
            airport_code = None

        existing = await db.get(PegasDepartureLocation, loc_id)
        if existing is None:
            db.add(PegasDepartureLocation(
                id=loc_id,
                name=name,
                airport_code=airport_code,
                is_top=loc_id in top_ids,
            ))
            count += 1
        else:
            existing.name = name
            existing.airport_code = airport_code
            existing.is_top = loc_id in top_ids

    await db.commit()
    logger.info("Pegas departure locations import complete: %s rows", count)
    return count


async def import_pegas_catalog(
    db: AsyncSession,
    cookies: list[dict],
    operator_id: int,
    countries: dict[int, str] | None = None,
) -> dict[str, int]:
    """
    Imports the Pegas catalog one country at a time (see module docstring for
    why). Defaults to PEGAS_SEED_COUNTRIES; pass `countries` to import a
    different/extended set without editing this module.

    operator_id is the operators.id row for Pegas, used to scope the
    city_mapping rows created for each resort (see CityMappingRepository -
    mappings are per-operator since the same destination name can come from
    different operators with different raw representations).

    Returns aggregate counts of rows written across all countries.
    """
    countries = countries if countries is not None else PEGAS_SEED_COUNTRIES
    totals = {"countries": 0, "resorts": 0, "hotels": 0, "airlines": 0, "meals": 0}

    for country_id, country_name in countries.items():
        logger.info("Importing Pegas catalog for country_id=%s (%s)", country_id, country_name)
        country_counts = await _import_one_country(
            db, cookies, country_id, country_name, operator_id
        )
        for key, value in country_counts.items():
            totals[key] += value
        await db.commit()

    logger.info(
        "Pegas catalog import complete: %s countries, %s resorts, %s hotels, %s airlines",
        totals["countries"],
        totals["resorts"],
        totals["hotels"],
        totals["airlines"],
    )
    return totals