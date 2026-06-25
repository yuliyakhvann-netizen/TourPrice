from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import (
    get_airline_mapping_repo,
    get_hotel_mapping_repo,
    get_meal_mapping_repo,
    get_room_mapping_repo,
)
from app.repositories.mapping_repo import (
    AirlineMappingRepository,
    HotelMappingRepository,
    MealMappingRepository,
    RoomMappingRepository,
)

router = APIRouter(prefix="/mappings", tags=["mappings"])


class ConfirmBody(BaseModel):
    normalized_value: str


class ConfirmHotelBody(BaseModel):
    canonical_hotel_id: int | None = None  # None means "this is a new hotel, mint a fresh ID"


class MergeHotelBody(BaseModel):
    target_id: int  # the hotel_mapping row this one should be merged into

@router.get("/rooms/pending")
async def pending_room_mappings(repo: RoomMappingRepository = Depends(get_room_mapping_repo)):
    return await repo.get_all(confirmed=False)


@router.patch("/rooms/{id}/confirm")
async def confirm_room_mapping(
    id: int,
    body: ConfirmBody,
    repo: RoomMappingRepository = Depends(get_room_mapping_repo),
):
    obj = await repo.confirm(id, body.normalized_value)
    if obj is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return obj


@router.get("/meals/pending")
async def pending_meal_mappings(repo: MealMappingRepository = Depends(get_meal_mapping_repo)):
    return await repo.get_all(confirmed=False)


@router.patch("/meals/{id}/confirm")
async def confirm_meal_mapping(
    id: int,
    body: ConfirmBody,
    repo: MealMappingRepository = Depends(get_meal_mapping_repo),
):
    obj = await repo.confirm(id, body.normalized_value)
    if obj is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return obj


@router.get("/airlines/pending")
async def pending_airline_mappings(repo: AirlineMappingRepository = Depends(get_airline_mapping_repo)):
    return await repo.get_all(confirmed=False)


@router.patch("/airlines/{id}/confirm")
async def confirm_airline_mapping(
    id: int,
    body: ConfirmBody,
    repo: AirlineMappingRepository = Depends(get_airline_mapping_repo),
):
    obj = await repo.confirm(id, body.normalized_value)
    if obj is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return obj


@router.get("/hotels/pending")
async def pending_hotel_mappings(repo: HotelMappingRepository = Depends(get_hotel_mapping_repo)):
    return await repo.get_pending()


@router.get("/hotels/canonical/{canonical_hotel_id}")
async def get_hotel_group(
    canonical_hotel_id: int,
    repo: HotelMappingRepository = Depends(get_hotel_mapping_repo),
):
    """All raw names across operators already confirmed as this same hotel - shown to the
    manager as 'here's what this hotel is currently matched to' while they review a new pending one."""
    return await repo.get_by_canonical_id(canonical_hotel_id)


@router.patch("/hotels/{id}/confirm")
async def confirm_hotel_mapping(
    id: int,
    body: ConfirmHotelBody,
    repo: HotelMappingRepository = Depends(get_hotel_mapping_repo),
):
    if body.canonical_hotel_id is not None:
        obj = await repo.confirm_as_existing(id, body.canonical_hotel_id)
    else:
        obj = await repo.confirm_as_new(id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return obj


@router.get("/hotels/{id}/suggestions")
async def suggest_hotel_matches(
    id: int,
    repo: HotelMappingRepository = Depends(get_hotel_mapping_repo),
):
    target = await repo.get(id)
    if target is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return await repo.suggest_matches(target.raw_value, exclude_operator_id=target.operator_id)


@router.patch("/hotels/{id}/merge")
async def merge_hotel_mapping(
    id: int,
    body: MergeHotelBody,
    repo: HotelMappingRepository = Depends(get_hotel_mapping_repo),
):
    obj = await repo.merge(source_id=id, target_id=body.target_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return obj


@router.patch("/hotels/{id}/unmatch")
async def unmatch_hotel(
    id: int,
    repo: HotelMappingRepository = Depends(get_hotel_mapping_repo),
):
    """Разъединить отель — убрать canonical_hotel_id и вернуть в pending."""
    obj = await repo.get(id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    obj.canonical_hotel_id = None
    obj.confirmed = False
    obj.auto_matched = False
    obj.confirmed_at = None
    await repo.session.commit()
    return obj


@router.get("/hotels/auto-match/preview")
async def preview_auto_match(
    threshold: int = 90,
    repo: HotelMappingRepository = Depends(get_hotel_mapping_repo),
):
    """Предпросмотр авто-матчинга без записи в БД."""
    matches = await repo.find_auto_matches(threshold=threshold)
    return {"threshold": threshold, "matches_count": len(matches), "sample": matches[:20]}


@router.post("/hotels/auto-match/run")
async def run_auto_match(
    background_tasks: BackgroundTasks,
    threshold: int = 90,
    repo: HotelMappingRepository = Depends(get_hotel_mapping_repo),
):
    """Запускает авто-матчинг в фоне. Сопоставляет отели с похожестью >= threshold%."""
    from app.database import AsyncSessionLocal

    async def do_match():
        async with AsyncSessionLocal() as db:
            from app.repositories.mapping_repo import HotelMappingRepository as R
            r = R(db)
            count = await r.run_auto_match(threshold=threshold)
            print(f"[auto_match] COMPLETE: {count} pairs matched", flush=True)

    background_tasks.add_task(do_match)
    return {"status": "started", "threshold": threshold}


@router.get("/hotels/confirmed")
async def get_confirmed_hotels(
    repo: HotelMappingRepository = Depends(get_hotel_mapping_repo),
):
    """Все сопоставленные группы отелей — для проверки менеджером."""
    return await repo.get_confirmed_groups()