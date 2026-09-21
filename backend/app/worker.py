import asyncio
from uuid import UUID

from celery import Celery
from sqlalchemy import select

from app.core.config import settings
from app.db import SessionLocal
from app.agents.job_scout import run_job_scout_agent
from app.models import CandidateProfile, Job
from app.services.availability import verify_job_availability
from app.services.orchestrator import rebuild_matches, sync_jobs
from app.services.vacancy_ai import analyze_vacancy_ai

celery_app = Celery("jobscout", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "scan-public-jobs-hourly": {
            "task": "app.worker.scan_all_users_task",
            "schedule": 21600.0,
        }
    },
)


async def _scan(limit: int, user_id: str | None) -> dict:
    async with SessionLocal() as db:
        if not user_id:
            return {"new_jobs": 0, "matched": 0, "availability": {}}
        return await run_job_scout_agent(db, UUID(user_id), limit)


async def _rematch_user(user_id: str) -> dict:
    async with SessionLocal() as db:
        profile = await db.scalar(
            select(CandidateProfile).where(CandidateProfile.user_id == UUID(user_id))
        )
        if profile is None:
            return {"matched": 0}
        matched = await rebuild_matches(db, profile)
        return {"matched": matched}


async def _scan_all(limit: int) -> dict:
    async with SessionLocal() as db:
        new_jobs = await sync_jobs(db, limit)
        availability = await verify_job_availability(db, limit=100)

        recent_jobs = list(
            (
                await db.execute(
                    select(Job)
                    .where(Job.is_active.is_(True))
                    .order_by(Job.collected_at.desc())
                    .limit(40)
                )
            ).scalars().all()
        )
        enriched = 0
        for job in recent_jobs:
            if (job.ai_analysis or {}).get("ai_enriched"):
                continue
            analysis = await analyze_vacancy_ai(job)
            job.ai_analysis = analysis
            if analysis.get("ai_enriched"):
                enriched += 1
        await db.commit()

        result = await db.execute(select(CandidateProfile))
        profiles = list(result.scalars().all())
        matched = 0
        for profile in profiles:
            matched += await rebuild_matches(db, profile)
        return {
            "new_jobs": new_jobs,
            "profiles": len(profiles),
            "matches_processed": matched,
            "availability": availability,
            "ai_enriched_jobs": enriched,
        }


@celery_app.task
def scan_jobs_task(limit: int = 100, user_id: str | None = None) -> dict:
    return asyncio.run(_scan(limit, user_id))


@celery_app.task
def scan_all_users_task(limit: int = 100) -> dict:
    return asyncio.run(_scan_all(limit))



@celery_app.task
def rebuild_matches_task(user_id: str) -> dict:
    return asyncio.run(_rematch_user(user_id))
