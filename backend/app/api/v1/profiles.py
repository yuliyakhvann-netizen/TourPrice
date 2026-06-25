from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_profile_repo
from app.core.exceptions import NotFoundError
from app.repositories.profile_repo import ProfileRepository
from app.schemas.profile import SearchProfileCreate, SearchProfileResponse, SearchProfileUpdate

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/", response_model=list[SearchProfileResponse])
async def list_profiles(repo: ProfileRepository = Depends(get_profile_repo)):
    return await repo.get_all()


@router.post("/", response_model=SearchProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    body: SearchProfileCreate,
    repo: ProfileRepository = Depends(get_profile_repo),
):
    return await repo.create(**body.model_dump())


@router.get("/{profile_id}", response_model=SearchProfileResponse)
async def get_profile(profile_id: int, repo: ProfileRepository = Depends(get_profile_repo)):
    obj = await repo.get(profile_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return obj


@router.patch("/{profile_id}", response_model=SearchProfileResponse)
async def update_profile(
    profile_id: int,
    body: SearchProfileUpdate,
    repo: ProfileRepository = Depends(get_profile_repo),
):
    obj = await repo.get(profile_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(obj, field, value)
    await repo.session.flush()
    return obj


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(profile_id: int, repo: ProfileRepository = Depends(get_profile_repo)):
    deleted = await repo.delete(profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Profile not found")
