from datetime import datetime, timezone

from sqlalchemy import select

from rapidfuzz import fuzz
from sqlalchemy import func

from app.models.mappings import (
    AirlineMapping,
    CityMapping,
    CountryMapping,
    HotelMapping,
    MealMapping,
    RoomMapping,
    TourProgramMapping,
)
from app.repositories.base import BaseRepository


class RoomMappingRepository(BaseRepository[RoomMapping]):
    model = RoomMapping

    async def get_confirmed(self) -> dict[str, str]:
        stmt = select(RoomMapping).where(RoomMapping.confirmed == True)  # noqa: E712
        result = await self.session.execute(stmt)
        return {r.raw_value: r.normalized_value for r in result.scalars().all()}

    async def get_or_create(self, raw_value: str, suggested: str) -> RoomMapping:
        stmt = select(RoomMapping).where(RoomMapping.raw_value == raw_value)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        return await self.create(raw_value=raw_value, normalized_value=suggested, confirmed=False)

    async def confirm(self, id: int, normalized_value: str) -> RoomMapping | None:
        obj = await self.get(id)
        if obj is None:
            return None
        obj.normalized_value = normalized_value
        obj.confirmed = True
        obj.confirmed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return obj


class MealMappingRepository(BaseRepository[MealMapping]):
    model = MealMapping

    async def get_confirmed(self) -> dict[str, str]:
        stmt = select(MealMapping).where(MealMapping.confirmed == True)  # noqa: E712
        result = await self.session.execute(stmt)
        return {r.raw_value: r.normalized_value for r in result.scalars().all()}

    async def get_or_create(self, raw_value: str, suggested: str) -> MealMapping:
        stmt = select(MealMapping).where(MealMapping.raw_value == raw_value)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        return await self.create(raw_value=raw_value, normalized_value=suggested, confirmed=False)

    async def confirm(self, id: int, normalized_value: str) -> MealMapping | None:
        obj = await self.get(id)
        if obj is None:
            return None
        obj.normalized_value = normalized_value
        obj.confirmed = True
        obj.confirmed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return obj


class AirlineMappingRepository(BaseRepository[AirlineMapping]):
    model = AirlineMapping

    async def get_confirmed(self) -> dict[str, str]:
        stmt = select(AirlineMapping).where(AirlineMapping.confirmed == True)  # noqa: E712
        result = await self.session.execute(stmt)
        return {r.raw_value: r.normalized_value for r in result.scalars().all()}

    async def get_or_create(self, raw_value: str, suggested: str) -> AirlineMapping:
        stmt = select(AirlineMapping).where(AirlineMapping.raw_value == raw_value)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        return await self.create(raw_value=raw_value, normalized_value=suggested, confirmed=False)

    async def confirm(self, id: int, normalized_value: str) -> AirlineMapping | None:
        obj = await self.get(id)
        if obj is None:
            return None
        obj.normalized_value = normalized_value
        obj.confirmed = True
        obj.confirmed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return obj


class CityMappingRepository(BaseRepository[CityMapping]):
    """
    Same get_confirmed/get_or_create/confirm shape as RoomMappingRepository,
    but scoped by operator_id - city/country/tour-program codes are NOT
    universal across SAMO installations (e.g. Almaty = 367408 at FunSun
    vs 9 at Kompas), so every lookup must be filtered to one operator,
    unlike the room/meal/airline-name mappings above.
    """

    model = CityMapping

    async def get_confirmed(self, operator_id: int) -> dict[str, str]:
        stmt = select(CityMapping).where(
            CityMapping.operator_id == operator_id,
            CityMapping.confirmed == True,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return {r.raw_value: r.normalized_value for r in result.scalars().all()}

    async def get_or_create(self, operator_id: int, raw_value: str, suggested: str) -> CityMapping:
        stmt = select(CityMapping).where(
            CityMapping.operator_id == operator_id,
            CityMapping.raw_value == raw_value,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        return await self.create(
            operator_id=operator_id, raw_value=raw_value, normalized_value=suggested, confirmed=False
        )

    async def get_raw_value(self, operator_id: int, normalized_value: str) -> str | None:
        """
        Reverse lookup: human-readable city name -> this operator's
        numeric code. Used by live search to resolve a person's typed
        input ("Almaty") into the operator-specific code the connector
        needs (367408 for FunSun, 9 for Kompas). Returns None if this
        operator has no confirmed mapping for that name yet - the caller
        must not fabricate a code, only report it can't search that
        operator for this city.
        """
        stmt = select(CityMapping).where(
            CityMapping.operator_id == operator_id,
            CityMapping.normalized_value == normalized_value,
        )
        result = await self.session.execute(stmt)
        mapping = result.scalar_one_or_none()
        return mapping.raw_value if mapping else None

    async def confirm(self, id: int, normalized_value: str) -> CityMapping | None:
        obj = await self.get(id)
        if obj is None:
            return None
        obj.normalized_value = normalized_value
        obj.confirmed = True
        obj.confirmed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return obj


class CountryMappingRepository(BaseRepository[CountryMapping]):
    model = CountryMapping

    async def get_confirmed(self, operator_id: int) -> dict[str, str]:
        stmt = select(CountryMapping).where(
            CountryMapping.operator_id == operator_id,
            CountryMapping.confirmed == True,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return {r.raw_value: r.normalized_value for r in result.scalars().all()}

    async def get_or_create(self, operator_id: int, raw_value: str, suggested: str) -> CountryMapping:
        stmt = select(CountryMapping).where(
            CountryMapping.operator_id == operator_id,
            CountryMapping.raw_value == raw_value,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        return await self.create(
            operator_id=operator_id, raw_value=raw_value, normalized_value=suggested, confirmed=False
        )

    async def get_raw_value(self, operator_id: int, normalized_value: str) -> str | None:
        """Reverse lookup, same purpose/caveat as CityMappingRepository.get_raw_value."""
        stmt = select(CountryMapping).where(
            CountryMapping.operator_id == operator_id,
            CountryMapping.normalized_value == normalized_value,
            CountryMapping.confirmed == True,  # noqa
        ).limit(1)
        result = await self.session.execute(stmt)
        mapping = result.scalars().first()
        return mapping.raw_value if mapping else None

    async def confirm(self, id: int, normalized_value: str) -> CountryMapping | None:
        obj = await self.get(id)
        if obj is None:
            return None
        obj.normalized_value = normalized_value
        obj.confirmed = True
        obj.confirmed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return obj


class TourProgramMappingRepository(BaseRepository[TourProgramMapping]):
    model = TourProgramMapping

    async def get_confirmed(self, operator_id: int) -> dict[str, str]:
        stmt = select(TourProgramMapping).where(
            TourProgramMapping.operator_id == operator_id,
            TourProgramMapping.confirmed == True,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return {r.raw_value: r.normalized_value for r in result.scalars().all()}

    async def get_or_create(
        self, operator_id: int, raw_value: str, suggested: str
    ) -> TourProgramMapping:
        stmt = select(TourProgramMapping).where(
            TourProgramMapping.operator_id == operator_id,
            TourProgramMapping.raw_value == raw_value,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        return await self.create(
            operator_id=operator_id, raw_value=raw_value, normalized_value=suggested, confirmed=False
        )

    async def confirm(self, id: int, normalized_value: str) -> TourProgramMapping | None:
        obj = await self.get(id)
        if obj is None:
            return None
        obj.normalized_value = normalized_value
        obj.confirmed = True
        obj.confirmed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return obj


class HotelMappingRepository(BaseRepository[HotelMapping]):
    """
    Unlike the other mapping repos, there's no single "normalized_value"
    string here - confirmation means assigning a canonical_hotel_id,
    either reusing one that's already confirmed for another operator's
    listing of "the same" hotel, or minting a fresh one. See
    HotelMapping's docstring for why hotel-name matching can't be
    auto-normalized the way room/meal codes can.
    """

    model = HotelMapping

    async def get_or_create(self, operator_id: int, raw_value: str) -> HotelMapping:
        stmt = select(HotelMapping).where(
            HotelMapping.operator_id == operator_id,
            HotelMapping.raw_value == raw_value,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        return await self.create(
            operator_id=operator_id, raw_value=raw_value, canonical_hotel_id=None, confirmed=False
        )

    async def get_pending(self) -> list[HotelMapping]:
        """Unconfirmed raw hotel names awaiting a manager's match decision."""
        stmt = select(HotelMapping).where(HotelMapping.confirmed == False)  # noqa: E712
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_next_canonical_id(self) -> int:
        """
        canonical_hotel_id has no source of truth elsewhere (it's not a
        foreign key to a 'hotels' table - none exists), so the next free
        value is just max(canonical_hotel_id) + 1. Race conditions
        between two managers confirming simultaneously aren't handled
        here - this is an internal admin tool, not a high-concurrency
        path.
        """
        result = await self.session.execute(select(func.max(HotelMapping.canonical_hotel_id)))
        current_max = result.scalar()
        return (current_max or 0) + 1

    async def confirm_as_existing(self, id: int, canonical_hotel_id: int) -> HotelMapping | None:
        """Confirm that this raw hotel name is the same hotel as canonical_hotel_id."""
        obj = await self.get(id)
        if obj is None:
            return None
        obj.canonical_hotel_id = canonical_hotel_id
        obj.confirmed = True
        obj.confirmed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return obj

    async def confirm_as_new(self, id: int) -> HotelMapping | None:
        """Confirm that this raw hotel name is a hotel not seen under any operator yet."""
        obj = await self.get(id)
        if obj is None:
            return None
        obj.canonical_hotel_id = await self.get_next_canonical_id()
        obj.confirmed = True
        obj.confirmed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return obj

    async def get_by_canonical_id(self, canonical_hotel_id: int) -> list[HotelMapping]:
        """All raw names (across operators) confirmed as the same hotel."""
        stmt = select(HotelMapping).where(HotelMapping.canonical_hotel_id == canonical_hotel_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def suggest_matches(
        self, raw_value: str, exclude_operator_id: int, limit: int = 5
    ) -> list[dict]:
        """
        Fuzzy-match raw_value against every OTHER operator's hotel
        names (confirmed or not) and return the top `limit` candidates
        by similarity score, best first. This is a suggestion aid for
        a human reviewer, not an auto-confirm mechanism - the manager
        still clicks to accept a match (see HotelMapping docstring on
        why hotel-name matching can't be done unattended).

        Candidates are deduplicated by canonical_hotel_id where one
        exists, so a hotel already confirmed under 3 operators shows
        once, not 3 times, using its first-seen raw name as the
        display label.
        """
        stmt = select(HotelMapping).where(HotelMapping.operator_id != exclude_operator_id)
        result = await self.session.execute(stmt)
        candidates = list(result.scalars().all())

        seen_canonical: set[int] = set()
        scored: list[dict] = []
        for c in candidates:
            if c.canonical_hotel_id is not None:
                if c.canonical_hotel_id in seen_canonical:
                    continue
                seen_canonical.add(c.canonical_hotel_id)

            score = fuzz.token_sort_ratio(raw_value, c.raw_value)
            scored.append(
                {
                    "hotel_mapping_id": c.id,
                    "operator_id": c.operator_id,
                    "raw_value": c.raw_value,
                    "canonical_hotel_id": c.canonical_hotel_id,
                    "confirmed": c.confirmed,
                    "score": round(score, 1),
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    async def merge(self, source_id: int, target_id: int) -> HotelMapping | None:
        """
        Confirm that the hotel_mapping rows at source_id and target_id
        are the same physical hotel, regardless of whether either one
        already has a canonical_hotel_id. Resolution order:
          - both already have one and they differ -> caller's call,
            picks target's (the one the manager clicked "same as")
          - only target has one -> source joins target's group
          - only source has one -> target joins source's group
          - neither has one -> mint a fresh canonical_hotel_id, both join it
        This is the single entry point the frontend's "this is the same
        hotel" button should use - it never needs to pre-resolve which
        side already has a canonical id, which avoids the two-request
        race the naive confirm_as_existing/confirm_as_new split has.
        """
        source = await self.get(source_id)
        target = await self.get(target_id)
        if source is None or target is None:
            return None

        if target.canonical_hotel_id is not None:
            canonical_id = target.canonical_hotel_id
        elif source.canonical_hotel_id is not None:
            canonical_id = source.canonical_hotel_id
        else:
            canonical_id = await self.get_next_canonical_id()

        now = datetime.now(timezone.utc)
        for obj in (source, target):
            obj.canonical_hotel_id = canonical_id
            obj.confirmed = True
            obj.confirmed_at = now

        await self.session.flush()
        return source

    async def get_canonical_id(self, operator_id: int, raw_value: str) -> int | None:
        stmt = select(HotelMapping).where(
            HotelMapping.operator_id == operator_id,
            HotelMapping.raw_value == raw_value,
        )
        result = await self.session.execute(stmt)
        mapping = result.scalar_one_or_none()
        return mapping.canonical_hotel_id if mapping else None

    async def get(self, id: int) -> HotelMapping | None:
        result = await self.session.execute(
            select(HotelMapping).where(HotelMapping.id == id)
        )
        return result.scalar_one_or_none()

    async def find_auto_matches(self, threshold: int = 90) -> list[dict]:
        """
        Находит пары отелей разных операторов с похожестью >= threshold.
        Только среди ещё не сопоставленных (confirmed=False).
        """
        from rapidfuzz import fuzz

        result = await self.session.execute(
            select(HotelMapping).where(HotelMapping.confirmed == False)  # noqa
        )
        pending = result.scalars().all()

        # Группируем по операторам
        by_operator: dict[int, list[HotelMapping]] = {}
        for h in pending:
            by_operator.setdefault(h.operator_id, []).append(h)

        operator_ids = list(by_operator.keys())
        matches = []

        for i, op1 in enumerate(operator_ids):
            for op2 in operator_ids[i+1:]:
                for h1 in by_operator[op1]:
                    for h2 in by_operator[op2]:
                        score = fuzz.token_sort_ratio(h1.raw_value, h2.raw_value)
                        if score >= threshold:
                            matches.append({
                                "id1": h1.id,
                                "op1": h1.operator_id,
                                "name1": h1.raw_value,
                                "id2": h2.id,
                                "op2": h2.operator_id,
                                "name2": h2.raw_value,
                                "score": score,
                            })

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches

    async def run_auto_match(self, threshold: int = 90) -> int:
        """
        Запускает авто-матчинг: находит пары >= threshold и сопоставляет их.
        Помечает auto_matched=True чтобы менеджер мог проверить.
        Возвращает количество сопоставленных пар.
        """
        from rapidfuzz import fuzz
        from datetime import datetime, timezone

        result = await self.session.execute(
            select(HotelMapping).where(HotelMapping.confirmed == False)  # noqa
        )
        pending = result.scalars().all()

        by_operator: dict[int, list[HotelMapping]] = {}
        for h in pending:
            by_operator.setdefault(h.operator_id, []).append(h)

        operator_ids = list(by_operator.keys())
        matched_count = 0
        now = datetime.now(timezone.utc)

        # Собираем все пары выше порога
        pairs: list[tuple[HotelMapping, HotelMapping, float]] = []
        for i, op1 in enumerate(operator_ids):
            for op2 in operator_ids[i+1:]:
                for h1 in by_operator[op1]:
                    for h2 in by_operator[op2]:
                        score = fuzz.token_sort_ratio(h1.raw_value, h2.raw_value)
                        if score >= threshold:
                            pairs.append((h1, h2, score))

        pairs.sort(key=lambda x: x[2], reverse=True)

        # Применяем матчинг — каждый отель только в одну группу
        already_matched: set[int] = set()
        next_canonical = await self.get_next_canonical_id()

        for h1, h2, score in pairs:
            if h1.id in already_matched and h2.id in already_matched:
                continue

            # Определяем canonical_id
            if h1.canonical_hotel_id is not None:
                canonical_id = h1.canonical_hotel_id
            elif h2.canonical_hotel_id is not None:
                canonical_id = h2.canonical_hotel_id
            else:
                canonical_id = next_canonical
                next_canonical += 1

            for h in (h1, h2):
                if h.id not in already_matched:
                    h.canonical_hotel_id = canonical_id
                    h.confirmed = True
                    h.auto_matched = True
                    h.confirmed_at = now
                    already_matched.add(h.id)

            matched_count += 1

        await self.session.commit()
        return matched_count

    async def get_confirmed_groups(self) -> list[dict]:
        """
        Возвращает все сопоставленные группы, сгруппированные по canonical_hotel_id.
        """
        result = await self.session.execute(
            select(HotelMapping)
            .where(
                HotelMapping.confirmed == True,  # noqa
                HotelMapping.canonical_hotel_id != None,  # noqa
            )
            .order_by(HotelMapping.canonical_hotel_id)
        )
        rows = result.scalars().all()

        groups: dict[int, list[dict]] = {}
        for h in rows:
            cid = h.canonical_hotel_id
            groups.setdefault(cid, []).append({
                "id": h.id,
                "operator_id": h.operator_id,
                "raw_value": h.raw_value,
                "auto_matched": h.auto_matched,
                "confirmed_at": h.confirmed_at.isoformat() if h.confirmed_at else None,
            })

        return [
            {"canonical_hotel_id": cid, "hotels": hotels}
            for cid, hotels in groups.items()
        ]