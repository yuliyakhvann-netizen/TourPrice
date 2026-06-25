from sqlalchemy import select

from app.models.raw_result import RawResult
from app.repositories.base import BaseRepository


class RawResultRepository(BaseRepository[RawResult]):
    model = RawResult

    async def get_by_scrape_run(self, scrape_run_id: str) -> RawResult | None:
        stmt = select(RawResult).where(RawResult.scrape_run_id == scrape_run_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()