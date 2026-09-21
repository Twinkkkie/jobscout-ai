from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import Application, Job, JobMatch, User
from app.schemas import DashboardStats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DashboardStats:
    jobs_total = await db.scalar(
        select(func.count(Job.id)).where(Job.is_active.is_(True))
    ) or 0
    strong = await db.scalar(
        select(func.count(JobMatch.id))
        .join(Job, Job.id == JobMatch.job_id)
        .where(
            JobMatch.user_id == user.id,
            JobMatch.score >= 75,
            Job.is_active.is_(True),
        )
    ) or 0

    async def count_status(status: str) -> int:
        return int(
            await db.scalar(
                select(func.count(Application.id)).where(
                    Application.user_id == user.id,
                    Application.status == status,
                )
            )
            or 0
        )

    saved = await count_status("saved")
    applied = await count_status("applied")
    interviews = await count_status("interview")
    offers = await count_status("offer")

    return DashboardStats(
        jobs_total=int(jobs_total),
        strong_matches=int(strong),
        saved=saved,
        applied=applied,
        interviews=interviews,
        offers=offers,
    )
