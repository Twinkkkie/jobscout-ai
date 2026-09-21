from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.career import run_career_agent
from app.db import get_db
from app.deps import get_current_user
from app.models import CandidateProfile, User
from app.schemas import CareerInsightRead

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/career", response_model=CareerInsightRead)
async def career_insight(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CareerInsightRead:
    profile = await db.scalar(
        select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    )
    if profile is None:
        raise HTTPException(status_code=409, detail="Complete your profile first")

    result = await run_career_agent(db, profile)
    return CareerInsightRead(**result)
