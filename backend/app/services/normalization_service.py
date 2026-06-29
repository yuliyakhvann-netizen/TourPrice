"""
Turns raw SAMO PRICES rows (as returned by FunSunOperator.search() /
KompasOperator.search()) into RawResult + NormalizedTour records.

Per the project's "don't build normalization until real payloads are
confirmed" principle, this only handles fields verified against live
FunSun traffic so far: country (via CountryMapping), departure city
(via CityMapping), airline (via TourProgramMapping keyed on TOURINC).
Room/meal type use the raw parsed text as a first-pass "suggested"
value via RoomMapping/MealMapping's existing confirm-later workflow -
same pattern as city/country/tour-program, just not operator-scoped.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.normalized_tour import NormalizedTour
from app.models.raw_result import RawResult
from app.operators.kompas.catalog_importer import upsert_kompas_resort
from app.repositories.mapping_repo import (
    CityMappingRepository,
    CountryMappingRepository,
    HotelMappingRepository,
    MealMappingRepository,
    RoomMappingRepository,
    TourProgramMappingRepository,
)
from app.repositories.raw_result_repo import RawResultRepository
from app.repositories.tour_repo import SnapshotRepository, TourRepository
from app.schemas.tour import TourKey


class NormalizationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.city_repo = CityMappingRepository(session)
        self.country_repo = CountryMappingRepository(session)
        self.tour_program_repo = TourProgramMappingRepository(session)
        self.room_repo = RoomMappingRepository(session)
        self.meal_repo = MealMappingRepository(session)
        self.hotel_repo = HotelMappingRepository(session)
        self.raw_result_repo = RawResultRepository(session)
        self.tour_repo = TourRepository(session)
        self.snapshot_repo = SnapshotRepository(session)

    async def ingest_search_results(
        self,
        operator_id: int,
        profile_id: int,
        rows: list[dict[str, Any]],
        operator_code: str | None = None,
    ) -> tuple[RawResult, list[NormalizedTour]]:
        """
        Persist one scrape's raw rows as a single RawResult, then write
        one NormalizedTour per distinct tour_key found in the rows.

        Rows that aren't currently bookable (is_bookable is False) are
        dropped before normalization - NormalizedTour has no column to
        record that state, and writing a dead listing in as if it were
        a live price would contradict the point of price comparison.

        If multiple rows resolve to the same tour_key within one scrape
        (e.g. promo vs non-promo pricing for an otherwise identical
        tour), the cheapest bookable price is kept - NormalizedTour's
        unique constraint is (operator_id, tour_key, scraped_at), and
        scraped_at is a DB-side now() identical for every insert in this
        transaction, so a second insert with the same tour_key would
        violate that constraint anyway.
        """
        scrape_run_id = str(uuid.uuid4())

        raw_result = await self.raw_result_repo.create(
            operator_id=operator_id,
            profile_id=profile_id,
            scrape_run_id=scrape_run_id,
            raw_data=rows,
            tours_count=len(rows),
        )

        candidates: dict[str, dict[str, Any]] = {}
        for row in rows:
            if row.get("_parse_warning"):
                continue
            if row.get("is_bookable") is False:
                continue
            if row.get("price_value") is None:
                continue

            tour_key, fields = await self._build_tour_key(operator_id, row, operator_code=operator_code)
            if tour_key is None:
                continue

            key_hash = tour_key.hash()
            existing = candidates.get(key_hash)
            if existing is None or fields["price"] < existing["fields"]["price"]:
                candidates[key_hash] = {"tour_key": tour_key, "fields": fields}

        normalized_tours = []
        for key_hash, candidate in candidates.items():
            tour_key = candidate["tour_key"]
            fields = candidate["fields"]
            normalized_tour = await self.tour_repo.create(
                operator_id=operator_id,
                profile_id=profile_id,
                scrape_run_id=scrape_run_id,
                tour_key=key_hash,
                country=tour_key.country,
                departure_city=tour_key.departure_city,
                departure_date=tour_key.departure_date,
                nights=tour_key.nights,
                hotel=tour_key.hotel,
                resort=fields.get("resort", ""),
                room_type=tour_key.room_type,
                meal_type=tour_key.meal_type,
                airline=tour_key.airline,
                adults=tour_key.adults,
                children=tour_key.children,
                price=fields["price"],
                currency=fields["currency"],
            )
            normalized_tours.append(normalized_tour)

            await self._write_snapshot(
                normalized_tour_id=normalized_tour.id,
                operator_id=operator_id,
                tour_key=key_hash,
                price=fields["price"],
                currency=fields["currency"],
            )

        return raw_result, normalized_tours

    async def _build_tour_key(
        self, operator_id: int, row: dict[str, Any], operator_code: str | None = None
    ) -> tuple[TourKey | None, dict[str, Any]]:
        try:
            departure_date = datetime.strptime(row["checkin_date"], "%Y%m%d").date()
            price = Decimal(str(row["price_value"]))
        except (KeyError, TypeError, ValueError, InvalidOperation):
            return None, {}

        country = await self._resolve_country(operator_id, row.get("state_id"))
        departure_city = await self._resolve_city(operator_id, row.get("town_from_id"))
        airline = await self._resolve_airline(operator_id, row.get("tour_id"), row.get("tour_name_raw"))
        room_type = await self._resolve_room_type(row.get("room_name_raw"))
        meal_type = await self._resolve_meal_type(row.get("meal_code"))

        if not all([country, departure_city, airline, room_type, meal_type, row.get("hotel_name_raw")]):
            return None, {}

        # Register the raw hotel name for manual cross-operator matching
        # later (see HotelMapping docstring). This doesn't affect
        # tour_key.hotel below - that still uses the raw name, since
        # canonical-hotel-based grouping is a separate concern handled
        # by whatever reads hotel_mapping, not by normalization itself.
        await self.hotel_repo.get_or_create(operator_id, row["hotel_name_raw"])

        # Upsert Kompas resort — только если operator_code == "kompas"
        ht_place_id = row.get("ht_place_id")
        location_name = row.get("location_name")
        state_id = row.get("state_id")
        if operator_code == "kompas" and ht_place_id and location_name and state_id:
            try:
                await upsert_kompas_resort(
                    db=self.session,
                    operator_id=operator_id,
                    ht_place_id=ht_place_id,
                    location_name=location_name,
                    country_id=state_id,
                )
            except Exception as e:
                logger.debug("upsert_kompas_resort skipped: %s", e)

        if operator_code == "selfie" and ht_place_id and location_name and state_id:
            try:
                from app.operators.selfie.catalog_importer import _upsert_selfie_resort
                from app.models.selfie_catalog import SelfieCountry
                selfie_country = await self.session.get(SelfieCountry, state_id)
                if selfie_country:
                    await _upsert_selfie_resort(
                        db=self.session,
                        ht_place_id=ht_place_id,
                        location_name=location_name,
                        country_id=state_id,
                    )
            except Exception as e:
                logger.debug("upsert_selfie_resort skipped: %s", e)

        if operator_code == "kazunion" and location_name and state_id:
            try:
                from app.operators.kazunion.catalog_importer import _upsert_kazunion_resort
                synthetic_id = abs(hash(f"{state_id}:{location_name}")) % (10**9)
                await _upsert_kazunion_resort(
                    db=self.session,
                    ht_place_id=synthetic_id,
                    location_name=location_name,
                    country_samo_id=state_id,
                )
            except Exception as e:
                logger.debug("upsert_kazunion_resort skipped: %s", e)

        tour_key = TourKey(
            country=country,
            departure_city=departure_city,
            departure_date=departure_date,
            nights=row["nights"],
            hotel=row["hotel_name_raw"],
            room_type=room_type,
            meal_type=meal_type,
            airline=airline,
            adults=row.get("adults") or 0,
            children=row.get("children") or 0,
        )
        resort = await self._resolve_resort(
            operator_code=operator_code,
            ht_place_id=ht_place_id,
            hotel_name=row.get("hotel_name_raw") or "",
            location_name=location_name or "",
        )

        fields = {
            "price": price,
            "currency": row.get("price_currency_title") or "KZT",
            "resort": resort,
        }
        return tour_key, fields

    async def _resolve_country(self, operator_id: int, state_id: int | None) -> str | None:
        if state_id is None:
            return None
        raw_value = str(state_id)
        mapping = await self.country_repo.get_or_create(operator_id, raw_value, suggested=raw_value)
        return mapping.normalized_value

    async def _resolve_city(self, operator_id: int, town_from_id: int | None) -> str | None:
        if town_from_id is None:
            return None
        raw_value = str(town_from_id)
        mapping = await self.city_repo.get_or_create(operator_id, raw_value, suggested=raw_value)
        return mapping.normalized_value

    async def _resolve_resort(
        self,
        operator_code: str | None,
        ht_place_id: int | None,
        hotel_name: str,
        location_name: str,
    ) -> str:
        """
        Резолвит название курорта из каталогов операторов.
        Kompas/Selfie: kompas_resort/selfie_resort по ht_place_id.
        Pegas: pegas_hotel → pegas_resort по hotel_name.
        Fallback: location_name из raw данных.
        """
        from sqlalchemy import select

        if operator_code == "kompas" and ht_place_id:
            from app.models.kompas_catalog import KompasResort
            r = await self.session.execute(
                select(KompasResort.name).where(KompasResort.id == ht_place_id)
            )
            name = r.scalars().first()
            if name:
                return name

        if operator_code == "selfie" and ht_place_id:
            from app.models.selfie_catalog import SelfieResort
            r = await self.session.execute(
                select(SelfieResort.name).where(SelfieResort.id == ht_place_id)
            )
            name = r.scalars().first()
            if name:
                return name
            # Fallback: нормализуем location_name из raw данных
            if location_name:
                from app.operators.selfie.catalog_importer import _normalize_resort_name
                return _normalize_resort_name(location_name)

        if operator_code == "kazunion":
            # У Kazunion ht_place_id=None, location_name содержит курорт напрямую
            return location_name or ""

        if operator_code == "pegas" and hotel_name:
            from app.models.pegas_catalog import PegasHotel, PegasResort
            r = await self.session.execute(
                select(PegasResort.name)
                .join(PegasHotel, PegasHotel.resort_id == PegasResort.id)
                .where(PegasHotel.name == hotel_name)
            )
            name = r.scalars().first()
            if name:
                return name

        return location_name

    async def _resolve_airline(
        self, operator_id: int, tour_id: int | None, tour_name_raw: str | None
    ) -> str | None:
        # Pegas не имеет tour_id — используем название авиакомпании напрямую
        if tour_id is None:
            if tour_name_raw:
                return tour_name_raw[:200]
            return "Unknown"
        raw_value = str(tour_id)
        suggested = tour_name_raw or f"tour_{tour_id}"
        mapping = await self.tour_program_repo.get_or_create(operator_id, raw_value, suggested=suggested)
        return mapping.normalized_value

    async def _resolve_room_type(self, room_name_raw: str | None) -> str | None:
        if not room_name_raw:
            return None
        mapping = await self.room_repo.get_or_create(room_name_raw, suggested=room_name_raw)
        return mapping.normalized_value

    async def _resolve_meal_type(self, meal_code: str | None) -> str | None:
        if not meal_code:
            return None
        mapping = await self.meal_repo.get_or_create(meal_code, suggested=meal_code)
        return mapping.normalized_value
    async def _write_snapshot(
        self,
        normalized_tour_id: int,
        operator_id: int,
        tour_key: str,
        price: Decimal,
        currency: str,
    ) -> None:
        """
        Write a PriceSnapshot for this normalized tour. Calculate
        price_change and price_change_pct relative to the most recent
        previous snapshot for the same tour_key + operator, if any.
        """
        history = await self.snapshot_repo.get_history(tour_key, limit=1)
        previous = next(
            (s for s in history if s.operator_id == operator_id), None
        )

        price_change = None
        price_change_pct = None
        if previous is not None and previous.price is not None:
            price_change = price - previous.price
            if previous.price != 0:
                pct = Decimal(str(price_change / previous.price * 100))
                # Ограничиваем до NUMERIC(6,2) максимум ±9999.99
                price_change_pct = min(max(pct, Decimal("-9999.99")), Decimal("9999.99")).quantize(Decimal("0.01"))

        await self.snapshot_repo.create(
            normalized_tour_id=normalized_tour_id,
            operator_id=operator_id,
            tour_key=tour_key,
            price=price,
            currency=currency,
            price_change=price_change,
            price_change_pct=price_change_pct,
        )