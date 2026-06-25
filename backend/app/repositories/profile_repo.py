from sqlalchemy import select

from app.models.search_profile import SearchProfile
from app.repositories.base import BaseRepository


class ProfileRepository(BaseRepository[SearchProfile]):
    model = SearchProfile

    async def get_active(self) -> list[SearchProfile]:
        stmt = select(SearchProfile).where(SearchProfile.is_active == True)  # noqa: E712
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
