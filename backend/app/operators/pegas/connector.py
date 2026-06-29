"""
Pegas connector. Unlike FunSun/Kompas (SamoOperator-based, public search,
no login), Pegas:

- requires an authenticated session (handled via PlaywrightSessionManager +
  app.operators.playwright_session.login, not done per-search here)
- exposes its own JSON REST API (PackageSearch/Search), not SAMO
- needs HotelIds/HotelRegionIds/HotelCategoryGroupIds/HotelMealGroupIds
  filled in explicitly on every search request. The Pegas frontend derives
  these client-side from its full catalog response; we derive the same
  thing server-side from our imported pegas_resort/pegas_hotel tables
  (see catalog_importer.py) instead of calling a separate lookup endpoint.

NOTE: cookie refresh-on-401 is not yet wired in here - if a search comes
back looking unauthenticated, the caller is responsible for invoking
session_manager.force_refresh() and retrying. This connector only consumes
cookies, it doesn't manage their lifecycle.
"""
from __future__ import annotations

from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pegas_catalog import PegasHotel
from app.operators.pegas import config as pegas_config


class PegasOperator:
    operator_code = pegas_config.OPERATOR_CODE

    def __init__(self, base_url: str = pegas_config.BASE_URL):
        self.base_url = base_url

    @staticmethod
    async def _resolve_hotel_filters(db: AsyncSession, resort_id: int) -> dict:
        """
        Pulls every known hotel for this resort from our imported catalog
        and derives the HotelIds/HotelCategoryGroupIds/HotelMealGroupIds
        lists the Search endpoint expects - mirroring what the Pegas
        frontend itself sends (a hotel/category/meal filter that's really
        just "everything available at this resort", not a narrowed-down
        selection).
        """
        stmt = select(PegasHotel).where(PegasHotel.resort_id == resort_id)
        result = await db.execute(stmt)
        hotels = list(result.scalars().all())

        hotel_ids: list[int] = []
        category_group_ids: set[int] = set()
        meal_group_ids: set[int] = set()

        for hotel in hotels:
            hotel_ids.append(hotel.id)
            if hotel.category_group_id is not None:
                category_group_ids.add(hotel.category_group_id)
            for meal_id in hotel.meal_group_ids or []:
                meal_group_ids.add(meal_id)

        return {
            "HotelIds": hotel_ids,
            "HotelRegionIds": [resort_id],
            "HotelCategoryGroupIds": sorted(category_group_ids),
            "HotelMealGroupIds": sorted(meal_group_ids),
        }

    async def search(
        self,
        *,
        db: AsyncSession,
        cookies: list[dict],
        departure_location_id: int,
        destination_country_id: int,
        resort_id: int,
        departure_dates: list[str],
        durations_in_nights: list[int],
        adults: int = 2,
        child_ages: Optional[list[int]] = None,
        airline_ids: Optional[list[int]] = None,
        payment_currency_id: int = 8168284,  # KZT, confirmed in original Search dump
    ) -> list[dict]:
        """
        Calls Pegas' PackageSearch/Search and returns the raw `Items` list
        as plain dicts - these are Pegas's raw, operator-native fields, NOT
        yet normalized into NormalizedTour. That mapping is
        NormalizationService's job, downstream of this, same as Kompas.

        resort_id must be a pegas_resort.id (e.g. resolved upstream via
        CityMappingRepository.get_raw_value(operator_id, profile_destination_name),
        then looked up by name in pegas_resort - see catalog_importer.py for
        why resort names, not opaque codes, are what's mapped here).
        """
        hotel_filters = await self._resolve_hotel_filters(db, resort_id)

        payload = {
            "DepartureLocationId": departure_location_id,
            "ReturnLocationId": departure_location_id,
            "DestinationCountryId": destination_country_id,
            "DestinationLocationId": None,
            "Adults": adults,
            "ChildAges": child_ages or [],
            "DepartureDates": departure_dates,
            "DurationsInNights": durations_in_nights,
            "PackageId": None,
            "PackageSpoTypeIds": [],
            "BasicFares": False,
            "PaymentCurrencyId": payment_currency_id,
            "MinPrice": None,
            "MaxPrice": None,
            "HotelLocationIds": [],
            "HotelLocationAreaIds": [],
            "HotelAttributeIds": [],
            "AirlineIds": airline_ids or [],
            "OutgoingFlightClassId": None,
            "ReturnFlightClassId": None,
            "DirectFlightsOnly": False,
            "HotelAvailabilityAvailable": True,
            "HotelAvailabilityOnRequest": True,
            "FlightAvailabilityAvailable": True,
            "FlightAvailabilityOnRequest": True,
            "GroupByHotel": False,
            "RenderAlternativeReturnLocations": True,
            "LanguageCode": None,
            "ShowPackagesWithExternalServices": False,
            "OutgoingFlightClassType": None,
            "ReturnFlightClassType": None,
            "ReturnDates": [],
            "OutgoingDatesPeriodModel": None,
            "ReturnDatesPeriodModel": None,
            **hotel_filters,
        }

        cookie_dict = {c["name"]: c["value"] for c in cookies}

        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=pegas_config.DEFAULT_HEADERS,
            cookies=cookie_dict,
            timeout=60.0,
        ) as client:
            response = await client.post(pegas_config.SEARCH_PATH, json=payload)
            response.raise_for_status()
            data = response.json()
            items = data.get("Items", [])
            return await self._normalize_items(
                db, items,
                destination_country_id=destination_country_id,
                departure_location_id=departure_location_id,
                adults=adults,
                child_ages=child_ages or [],
                durations_in_nights=durations_in_nights,
            )

    async def _normalize_items(
        self,
        db: AsyncSession,
        items: list[dict],
        destination_country_id: int = 0,
        departure_location_id: int = 0,
        adults: int = 2,
        child_ages: list[int] = None,
        durations_in_nights: list[int] = None,
    ) -> list[dict]:
        if child_ages is None:
            child_ages = []
        if durations_in_nights is None:
            durations_in_nights = []
        """
        Конвертирует Pegas Items в формат совместимый с NormalizationService.
        Поля: price_value, checkin_date, nights, hotel_name_raw,
              room_name_raw, meal_code, tour_id, is_bookable.
        """
        from app.models.pegas_catalog import PegasHotel, PegasAirline

        # Кэш отелей и авиакомпаний чтобы не делать запрос на каждую строку
        hotel_cache: dict[int, str] = {}
        airline_cache: dict[int, str] = {}

        results = []
        if not items:
            return []
        for item in items:
            try:
                price = item.get("Price")
                if price is None:
                    continue

                hotel_services = item.get("HotelServices", [])
                if not hotel_services:
                    continue
                hs = hotel_services[0]

                flight_services = item.get("FlightServices", [])
                airline_name = ""
                if flight_services:
                    fs = flight_services[0]
                    segments = fs.get("Segments", [])
                    if segments:
                        airline_id = segments[0].get("AirlineId")
                        if airline_id:
                            if airline_id not in airline_cache:
                                res = await db.execute(
                                    select(PegasAirline).where(PegasAirline.id == airline_id)
                                )
                                airline = res.scalar_one_or_none()
                                airline_cache[airline_id] = airline.name if airline else str(airline_id)
                            airline_name = airline_cache[airline_id]

                hotel_id = hs.get("HotelId")
                if not hotel_id:
                    continue

                if hotel_id not in hotel_cache:
                    res = await db.execute(
                        select(PegasHotel).where(PegasHotel.id == hotel_id)
                    )
                    hotel = res.scalar_one_or_none()
                    hotel_cache[hotel_id] = hotel.name if hotel else None
                hotel_name = hotel_cache[hotel_id]

                # Пропускаем если отель не найден в каталоге
                if not hotel_name:
                    continue

                checkin_raw = hs.get("CheckInDate", "")
                checkin_date = checkin_raw[:10].replace("-", "") if checkin_raw else None
                if not checkin_date:
                    continue

                nights = hs.get("DurationInNights")
                meal_id = hs.get("MealId")
                room_category_id = hs.get("RoomCategoryId")
                availability = hs.get("Availability", 1)

                # Фильтруем по запрошенным ночам
                if durations_in_nights and nights not in durations_in_nights:
                    continue

                results.append({
                    "price_value": float(price),
                    "checkin_date": checkin_date,
                    "nights": nights,
                    "hotel_name_raw": hotel_name[:200] if hotel_name else "",
                    "room_name_raw": str(room_category_id)[:200] if room_category_id else "",
                    "meal_code": str(meal_id)[:200] if meal_id else "",
                    "tour_id": None,
                    "tour_name_raw": airline_name[:200] if airline_name else "",
                    "is_bookable": availability != 2,
                    "ht_place_id": None,
                    "location_name": None,
                    "currency": "KZT",
                    "state_id": destination_country_id,
                    "town_from_id": departure_location_id,
                    "adults": adults,
                    "children": len(child_ages),
                })
            except Exception as e:
                print(f"[pegas_normalize] item failed: {e}", flush=True)
                continue

        return results