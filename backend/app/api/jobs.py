from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models import CandidateProfile, Job, JobMatch, User
from app.schemas import JobRead, MatchAnalysisRead, MatchRead
from app.services.match_ai import explain_match_ai
from app.services.matching import MATCHING_VERSION, score_job
from app.services.orchestrator import ensure_current_matches, rebuild_matches
from app.worker import analyze_job_match_task, celery_app, scan_jobs_task

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
async def list_jobs(
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Job]:
    profile = await db.scalar(
        select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    )
    if profile is not None:
        await ensure_current_matches(db, profile)

    query = (
        select(Job)
        .join(JobMatch, JobMatch.job_id == Job.id)
        .where(
            JobMatch.user_id == user.id,
            JobMatch.score >= 45,
            Job.is_active.is_(True),
        )
        .order_by(JobMatch.score.desc(), Job.published_at.desc().nullslast(), Job.collected_at.desc())
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
    task = scan_jobs_task.delay(max(settings.job_scan_limit, 250), str(user.id))
    return {"status": "queued", "task_id": task.id}


@router.get("/scan/{task_id}")
async def scan_status(task_id: str, user: User = Depends(get_current_user)) -> dict:
    task = celery_app.AsyncResult(task_id)
    payload = {"task_id": task_id, "status": task.status.lower()}
    if task.successful():
        payload["result"] = task.result
    elif task.failed():
        payload["error"] = str(task.result)
    elif isinstance(task.info, dict):
        payload["meta"] = task.info
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
    profile = await db.scalar(
        select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    )
    if profile is not None:
        await ensure_current_matches(db, profile)

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
            ai_explanation=match.ai_explanation,
            job=JobRead.model_validate(job),
        )
        for match, job in rows
    ]



@router.post("/{job_id}/match-analysis", response_model=MatchAnalysisRead)
async def analyze_match(
    job_id: UUID,
    queue_ai: bool = Query(default=True),
    locale: str = Query(default="en", pattern="^(en|ru)$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MatchAnalysisRead:
    job = await db.get(Job, job_id)
    if job is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")

    profile = await db.scalar(
        select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    )
    if profile is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="Complete your profile first")

    has_current_ai = bool(
        (job.ai_analysis or {}).get("ai_enriched")
        and (job.ai_analysis or {}).get("analysis_version") == 4
    )

    # Always return an immediate, internally consistent match. If this vacancy
    # still needs AI extraction, refine it in Celery instead of blocking the UI.
    scored = score_job(profile, job)
    match = await db.scalar(
        select(JobMatch).where(
            JobMatch.user_id == user.id,
            JobMatch.job_id == job.id,
        )
    )
    if match is None:
        match = JobMatch(user_id=user.id, job_id=job.id)
        db.add(match)

    explanation = await explain_match_ai(profile, job, scored, locale=locale)
    match.score = scored["score"]
    match.matching_skills = scored["matching_skills"]
    match.skill_gaps = scored["skill_gaps"]
    match.reasons = scored["reasons"]
    match.verdict = scored["verdict"]
    match.ai_explanation = explanation
    match.matching_version = MATCHING_VERSION
    await db.commit()
    await db.refresh(match)

    task_id = None
    if queue_ai and settings.openai_api_key and not has_current_ai:
        task = analyze_job_match_task.delay(str(user.id), str(job.id), locale)
        task_id = task.id

    read = MatchRead(
        id=match.id,
        score=match.score,
        matching_skills=match.matching_skills,
        skill_gaps=match.skill_gaps,
        reasons=match.reasons,
        verdict=match.verdict,
        ai_explanation=match.ai_explanation,
        job=JobRead.model_validate(job),
    )
    return MatchAnalysisRead(
        match=read,
        explanation=explanation,
        ai_pending=bool(task_id),
        task_id=task_id,
    )
