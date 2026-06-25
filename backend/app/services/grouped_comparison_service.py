"""
GroupedComparisonService: cross-operator price comparison grouped by
canonical hotel, NOT by exact tour_key match.

Why this exists alongside ComparisonService: tour_key is a hash of 10
raw fields (hotel name, room type, meal type, airline as scraped text),
which never matches across operators since they spell these differently
- see HotelMapping's docstring. This service groups by canonical_hotel_id
(the manager's confirmed cross-operator hotel match) plus date/nights/
occupancy instead, and lists every operator's room/price variants
side by side within that group rather than trying to find "the same"
room across operators.

Hotels with no confirmed HotelMapping yet are NOT silently dropped -
they're grouped alone (keyed by operator+raw name), so the manager still
sees them on the dashboard, just not merged with anything yet. This
avoids creating an incentive to rush hotel matching just to make data
appear.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operator import Operator
from app.repositories.mapping_repo import HotelMappingRepository
from app.repositories.tour_repo import TourRepository
from sqlalchemy import select


class GroupedComparisonService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tour_repo = TourRepository(session)
        self.hotel_repo = HotelMappingRepository(session)

    async def get_grouped_comparison(self, profile_id: int) -> list[dict[str, Any]]:
        operators_result = await self.session.execute(
            select(Operator.id, Operator.code).where(Operator.is_active == True)  # noqa: E712
        )
        operators = {op_id: op_code for op_id, op_code in operators_result.all()}

        groups: dict[tuple, dict[str, Any]] = {}

        for op_id, op_code in operators.items():
            tours = await self.tour_repo.get_latest_by_profile_and_operator(profile_id, op_id)

            for tour in tours:
                canonical_id = await self.hotel_repo.get_canonical_id(op_id, tour.hotel)

                # Unmapped hotels get their own group, keyed so they
                # never accidentally collide with another operator's
                # unmapped hotel of the same raw name (matching that
                # would be exactly the kind of unattended fuzzy
                # matching HotelMapping exists to avoid).
                group_key = (
                    ("canonical", canonical_id) if canonical_id is not None
                    else ("unmapped", op_id, tour.hotel)
                )
                date_key = (tour.departure_date, tour.nights, tour.adults, tour.children)
                key = (group_key, date_key)

                if key not in groups:
                    groups[key] = {
                        "hotel": tour.hotel,
                        "canonical_hotel_id": canonical_id,
                        "matched": canonical_id is not None,
                        "departure_date": tour.departure_date,
                        "nights": tour.nights,
                        "adults": tour.adults,
                        "children": tour.children,
                        "operators": defaultdict(list),
                    }

                groups[key]["operators"][op_code].append(
                    {
                        "hotel_raw": tour.hotel,
                        "room_type": tour.room_type,
                        "meal_type": tour.meal_type,
                        "airline": tour.airline,
                        "price": tour.price,
                        "currency": tour.currency,
                    }
                )

        result = []
        for group in groups.values():
            group["operators"] = dict(group["operators"])
            result.append(group)

        # Matched groups (real cross-operator comparisons) first, since
        # those are the actually useful rows for a manager comparing prices.
        result.sort(key=lambda g: (not g["matched"], g["hotel"]))
        return result