from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_comparison_repo, get_grouped_comparison_service, get_snapshot_repo
from app.repositories.comparison_repo import ComparisonRepository
from app.repositories.tour_repo import SnapshotRepository
from app.schemas.comparison import ComparisonResultResponse, PriceHistoryPoint
from app.services.grouped_comparison_service import GroupedComparisonService

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


@router.get("/", response_model=list[ComparisonResultResponse])
async def get_comparisons(
    profile_id: int,
    repo: ComparisonRepository = Depends(get_comparison_repo),
):
    return await repo.get_latest_by_profile(profile_id)


@router.get("/history", response_model=list[PriceHistoryPoint])
async def get_price_history(
    tour_key: str,
    limit: int = 50,
    repo: SnapshotRepository = Depends(get_snapshot_repo),
):
    snapshots = await repo.get_history(tour_key, limit=limit)
    # Join with operator to return operator_code — simplified: operator_id returned for now
    return [
        PriceHistoryPoint(
            operator_code=str(s.operator_id),
            price=s.price,
            currency=s.currency,
            recorded_at=s.recorded_at,
        )
        for s in snapshots
    ]


@router.get("/grouped")
async def get_grouped_comparison(
    profile_id: int,
    service: GroupedComparisonService = Depends(get_grouped_comparison_service),
):
    return await service.get_grouped_comparison(profile_id)
