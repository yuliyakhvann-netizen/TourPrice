from sqlalchemy import select

from app.models.normalized_tour import NormalizedTour
from app.models.price_snapshot import PriceSnapshot
from app.repositories.base import BaseRepository


class TourRepository(BaseRepository[NormalizedTour]):
    model = NormalizedTour

    async def get_by_tour_key(self, tour_key: str) -> list[NormalizedTour]:
        stmt = (
            select(NormalizedTour)
            .where(NormalizedTour.tour_key == tour_key)
            .order_by(NormalizedTour.scraped_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_by_profile(self, profile_id: int, scrape_run_id: str) -> list[NormalizedTour]:
        stmt = select(NormalizedTour).where(
            NormalizedTour.profile_id == profile_id,
            NormalizedTour.scrape_run_id == scrape_run_id,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_by_profile_and_operator(
        self, profile_id: int, operator_id: int
    ) -> list[NormalizedTour]:
        """
        Returns all NormalizedTour rows for the most recent scrape of
        (profile, operator). Used by ComparisonService to fetch per-operator
        prices before cross-operator comparison.
        """
        subq = (
            select(NormalizedTour.scrape_run_id)
            .where(
                NormalizedTour.profile_id == profile_id,
                NormalizedTour.operator_id == operator_id,
            )
            .order_by(NormalizedTour.scraped_at.desc())
            .limit(1)
            .scalar_subquery()
        )
        stmt = select(NormalizedTour).where(
            NormalizedTour.profile_id == profile_id,
            NormalizedTour.operator_id == operator_id,
            NormalizedTour.scrape_run_id == subq,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class SnapshotRepository(BaseRepository[PriceSnapshot]):
    model = PriceSnapshot

    async def get_history(self, tour_key: str, limit: int = 50) -> list[PriceSnapshot]:
        stmt = (
            select(PriceSnapshot)
            .where(PriceSnapshot.tour_key == tour_key)
            .order_by(PriceSnapshot.recorded_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
