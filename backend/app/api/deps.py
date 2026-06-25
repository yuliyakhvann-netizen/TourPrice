from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories.comparison_repo import ComparisonRepository
from app.repositories.mapping_repo import (
    AirlineMappingRepository,
    CityMappingRepository,
    CountryMappingRepository,
    HotelMappingRepository,
    MealMappingRepository,
    RoomMappingRepository,
)
from app.repositories.profile_repo import ProfileRepository
from app.repositories.tour_repo import SnapshotRepository, TourRepository
from app.services.comparison_service import ComparisonService
from app.services.grouped_comparison_service import GroupedComparisonService
from app.services.normalization_service import NormalizationService

async def get_profile_repo(db: AsyncSession = Depends(get_db)) -> ProfileRepository:
    return ProfileRepository(db)


async def get_comparison_repo(db: AsyncSession = Depends(get_db)) -> ComparisonRepository:
    return ComparisonRepository(db)


async def get_tour_repo(db: AsyncSession = Depends(get_db)) -> TourRepository:
    return TourRepository(db)


async def get_snapshot_repo(db: AsyncSession = Depends(get_db)) -> SnapshotRepository:
    return SnapshotRepository(db)


async def get_room_mapping_repo(db: AsyncSession = Depends(get_db)) -> RoomMappingRepository:
    return RoomMappingRepository(db)


async def get_meal_mapping_repo(db: AsyncSession = Depends(get_db)) -> MealMappingRepository:
    return MealMappingRepository(db)


async def get_airline_mapping_repo(db: AsyncSession = Depends(get_db)) -> AirlineMappingRepository:
    return AirlineMappingRepository(db)


async def get_city_mapping_repo(db: AsyncSession = Depends(get_db)) -> CityMappingRepository:
    return CityMappingRepository(db)


async def get_country_mapping_repo(db: AsyncSession = Depends(get_db)) -> CountryMappingRepository:
    return CountryMappingRepository(db)


async def get_normalization_service(db: AsyncSession = Depends(get_db)) -> NormalizationService:
    return NormalizationService(db)


async def get_comparison_service(db: AsyncSession = Depends(get_db)) -> ComparisonService:
    return ComparisonService(db)


async def get_hotel_mapping_repo(db: AsyncSession = Depends(get_db)) -> HotelMappingRepository:
    return HotelMappingRepository(db)


async def get_grouped_comparison_service(
    db: AsyncSession = Depends(get_db),
) -> GroupedComparisonService:
    return GroupedComparisonService(db)
