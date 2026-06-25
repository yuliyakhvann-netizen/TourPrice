"""
ComparisonService: cross-operator price comparison for a SearchProfile.

Takes the latest NormalizedTour rows per operator for a given profile,
groups them by tour_key, and writes one ComparisonResult row per unique
tour. market_min/max/avg are computed across all operators that have a
price for that tour_key.

scrape_run_id on ComparisonResult is a fresh UUID per comparison run —
it's not tied to any single operator's scrape_run_id, since FunSun and
Kompas are scraped independently and will always have different run IDs.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comparison_result import ComparisonResult
from app.models.operator import Operator
from app.repositories.comparison_repo import ComparisonRepository
from app.repositories.tour_repo import TourRepository


# Maps operator.code → ComparisonResult column name.
# Extend this when Anex/Pegas are added.
OPERATOR_PRICE_FIELD: dict[str, str] = {
    "funsun": "funsun_price",
    "kompas": "kompas_price",
    "pegas": "pegas_price",
    "anex": "anex_price",
}


class ComparisonService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tour_repo = TourRepository(session)
        self.comparison_repo = ComparisonRepository(session)

    async def run_for_profile(self, profile_id: int) -> list[ComparisonResult]:
        """
        Build (or rebuild) ComparisonResult rows for profile_id using
        the latest available NormalizedTour data from every operator.
        Returns the newly written rows.
        """
        # Resolve all active operator ids and their codes in one query.
        operators_result = await self.session.execute(
            select(Operator.id, Operator.code).where(Operator.is_active == True)  # noqa: E712
        )
        operators = operators_result.all()

        # Collect latest tours per operator, keyed by tour_key.
        # Structure: {tour_key: {operator_code: NormalizedTour}}
        by_tour_key: dict[str, dict[str, object]] = {}

        for op_id, op_code in operators:
            if op_code not in OPERATOR_PRICE_FIELD:
                continue
            tours = await self.tour_repo.get_latest_by_profile_and_operator(profile_id, op_id)
            for tour in tours:
                if tour.tour_key not in by_tour_key:
                    by_tour_key[tour.tour_key] = {}
                by_tour_key[tour.tour_key][op_code] = tour

        if not by_tour_key:
            return []

        comparison_run_id = str(uuid.uuid4())
        results: list[ComparisonResult] = []

        for tour_key, op_tours in by_tour_key.items():
            # Use any available tour as the source of denormalized fields.
            sample = next(iter(op_tours.values()))

            prices: dict[str, Optional[Decimal]] = {
                code: None for code in OPERATOR_PRICE_FIELD
            }
            for op_code, tour in op_tours.items():
                prices[op_code] = tour.price

            non_null = [p for p in prices.values() if p is not None]
            market_min = min(non_null) if non_null else None
            market_max = max(non_null) if non_null else None
            market_avg = (
                Decimal(sum(non_null) / len(non_null)).quantize(Decimal("0.01"))
                if non_null
                else None
            )

            # Currency: prefer USD (funsun), fall back to whatever is available.
            currency = "USD"
            for op_code in ("funsun", "kompas", "pegas", "anex"):
                if op_code in op_tours:
                    currency = op_tours[op_code].currency
                    if currency == "USD":
                        break

            row = await self.comparison_repo.create(
                profile_id=profile_id,
                tour_key=tour_key,
                scrape_run_id=comparison_run_id,
                hotel=sample.hotel,
                room_type=sample.room_type,
                meal_type=sample.meal_type,
                airline=sample.airline,
                nights=sample.nights,
                funsun_price=prices.get("funsun"),
                pegas_price=prices.get("pegas"),
                anex_price=prices.get("anex"),
                kompas_price=prices.get("kompas"),
                market_min_price=market_min,
                market_max_price=market_max,
                market_avg_price=market_avg,
                currency=currency,
            )
            results.append(row)

        return results