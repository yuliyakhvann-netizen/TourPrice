from sqlalchemy import select

from app.models.comparison_result import ComparisonResult
from app.repositories.base import BaseRepository


class ComparisonRepository(BaseRepository[ComparisonResult]):
    model = ComparisonResult

    async def get_latest_by_profile(self, profile_id: int) -> list[ComparisonResult]:
        # Get the latest scrape_run_id for this profile, then fetch all rows for it
        subq = (
            select(ComparisonResult.scrape_run_id)
            .where(ComparisonResult.profile_id == profile_id)
            .order_by(ComparisonResult.created_at.desc())
            .limit(1)
            .scalar_subquery()
        )
        stmt = select(ComparisonResult).where(
            ComparisonResult.profile_id == profile_id,
            ComparisonResult.scrape_run_id == subq,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
