from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models import CandidateProfile, Job, JobMatch, User
from app.schemas import JobRead, MatchRead
from app.services.orchestrator import rebuild_matches
from app.worker import celery_app, scan_jobs_task

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
async def list_jobs(
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Job]:
    query = (
        select(Job)
        .join(JobMatch, JobMatch.job_id == Job.id)
        .where(
            JobMatch.user_id == user.id,
            JobMatch.score >= 45,
            Job.is_active.is_(True),
        )
        .order_by(Job.collected_at.desc(), JobMatch.score.desc(), Job.published_at.desc().nullslast())
    )
    if q:
        needle = f"%{q}%"
        query = query.where(
            or_(Job.title.ilike(needle), Job.company.ilike(needle), Job.description.ilike(needle))
        )
    result = await db.execute(query.limit(limit))
    return list(result.scalars().all())


@router.post("/scan", status_code=202)
async def scan_jobs(user: User = Depends(get_current_user)) -> dict:
    task = scan_jobs_task.delay(settings.job_scan_limit, str(user.id))
    return {"status": "queued", "task_id": task.id}


@router.get("/scan/{task_id}")
async def scan_status(task_id: str, user: User = Depends(get_current_user)) -> dict:
    task = celery_app.AsyncResult(task_id)
    payload = {"task_id": task_id, "status": task.status.lower()}
    if task.successful():
        payload["result"] = task.result
    elif task.failed():
        payload["error"] = str(task.result)
    return payload


@router.post("/rematch", status_code=202)
async def rematch(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    profile = await db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if profile is None:
        return {"matched": 0}
    count = await rebuild_matches(db, profile)
    return {"matched": count}


@router.get("/matches", response_model=list[MatchRead])
async def list_matches(
    verdict: str | None = None,
    min_score: float = Query(default=45, ge=0, le=100),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MatchRead]:
    query = (
        select(JobMatch, Job)
        .join(Job, Job.id == JobMatch.job_id)
        .where(
            JobMatch.user_id == user.id,
            JobMatch.score >= min_score,
            Job.is_active.is_(True),
        )
        .order_by(JobMatch.score.desc(), Job.published_at.desc().nullslast())
    )
    if verdict:
        query = query.where(JobMatch.verdict == verdict)
    rows = (await db.execute(query.limit(limit))).all()
    return [
        MatchRead(
            id=match.id,
            score=match.score,
            matching_skills=match.matching_skills,
            skill_gaps=match.skill_gaps,
            reasons=match.reasons,
            verdict=match.verdict,
            job=JobRead.model_validate(job),
        )
        for match, job in rows
    ]
