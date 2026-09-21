from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import CandidateProfile, User
from app.schemas import ProfileRead, ProfileUpdate
from app.services.orchestrator import rebuild_matches

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
) -> CandidateProfile:
    profile = await _get_profile(db, user)
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)

    # Deterministic rematching is now batched and fast enough to complete here.
    # Returning only after it finishes prevents the UI from showing stale scores,
    # matching skills, and gaps after a profile edit.
    await rebuild_matches(db, profile)
    return profile
