from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import CandidateProfile, User
from app.schemas import ProfileRead, ProfileUpdate
from app.worker import rebuild_matches_task

router = APIRouter(prefix="/profile", tags=["profile"])


async def _get_profile(db: AsyncSession, user: User) -> CandidateProfile:
    profile = await db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if profile is None:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


@router.get("", response_model=ProfileRead)
async def get_profile(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CandidateProfile:
    return await _get_profile(db, user)


@router.put("", response_model=ProfileRead)
async def update_profile(
    payload: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProfileRead:
    profile = await _get_profile(db, user)
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)

    task_id = None
    try:
        task = rebuild_matches_task.delay(str(user.id))
        task_id = task.id
    except Exception:
        task_id = None

    response = ProfileRead.model_validate(profile)
    return response.model_copy(
        update={
            "rematch_queued": bool(task_id),
            "rematch_task_id": task_id,
        }
    )
