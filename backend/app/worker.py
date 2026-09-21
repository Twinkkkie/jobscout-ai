import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

from celery import Celery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.job_scout import run_job_scout_agent
from app.core.config import settings
from app.models import CandidateProfile, Job
from app.services.availability import verify_job_availability
from app.services.matching import score_job
from app.services.orchestrator import rebuild_matches, sync_jobs
from app.services.vacancy_ai import analyze_vacancies_batch_ai

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


@asynccontextmanager
async def _worker_db():
    """
    Celery calls asyncio.run() per task, which creates a new event loop each time.
    Reusing the API's global async SQLAlchemy pool across those loops can leave
    pooled asyncpg futures attached to an old loop. Give every Celery task its
    own short-lived engine/pool and dispose it before that loop closes.
    """
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    try:
        async with session_factory() as db:
            yield db
    finally:
        await engine.dispose()


async def _scan(limit: int, user_id: str | None) -> dict:
    async with _worker_db() as db:
        if not user_id:
            return {"new_jobs": 0, "matched": 0, "availability": {}}
        return await run_job_scout_agent(
            db,
            UUID(user_id),
            limit,
            defer_ai=True,
        )


async def _rematch_user(user_id: str) -> dict:
    async with _worker_db() as db:
        profile = await db.scalar(
            select(CandidateProfile).where(CandidateProfile.user_id == UUID(user_id))
        )
        if profile is None:
            return {"matched": 0}
        matched = await rebuild_matches(db, profile)
        return {"matched": matched}


async def _enrich_user_jobs(user_id: str) -> dict:
    async with _worker_db() as db:
        profile = await db.scalar(
            select(CandidateProfile).where(CandidateProfile.user_id == UUID(user_id))
        )
        if profile is None or not settings.openai_api_key:
            return {"ai_enriched_jobs": 0, "matched": 0}

        result = await db.execute(
            select(Job)
            .where(Job.is_active.is_(True))
            .order_by(Job.collected_at.desc())
            .limit(60)
        )
        recent_jobs = list(result.scalars().all())

        candidates = [
            job
            for job in recent_jobs
            if not (job.ai_analysis or {}).get("ai_enriched")
            and score_job(profile, job)["score"] >= 40
        ]
        candidates.sort(
            key=lambda job: score_job(profile, job)["score"],
            reverse=True,
        )
        candidates = candidates[:10]

        analyses = await analyze_vacancies_batch_ai(candidates)
        enriched = 0
        now = datetime.now(UTC)
        for job in candidates:
            analysis = analyses.get(str(job.id))
            if not analysis:
                continue
            job.ai_analysis = analysis
            if analysis.get("ai_enriched"):
                job.ai_analyzed_at = now
                enriched += 1

        await db.commit()

        # Recalculate every active match so old percentages/skills/gaps cannot
        # survive after a new AI analysis or matching-rule change.
        matched = await rebuild_matches(db, profile)
        return {
            "ai_enriched_jobs": enriched,
            "matched": matched,
        }


async def _scan_all(limit: int) -> dict:
    async with _worker_db() as db:
        new_jobs = await sync_jobs(db, limit)
        availability = await verify_job_availability(db, limit=100)

        result = await db.execute(
            select(Job)
            .where(Job.is_active.is_(True))
            .order_by(Job.collected_at.desc())
            .limit(40)
        )
        recent_jobs = list(result.scalars().all())

        enriched = 0
        if settings.openai_api_key:
            candidates = [
                job
                for job in recent_jobs
                if not (job.ai_analysis or {}).get("ai_enriched")
            ][:20]

            # Two compact batch calls are much faster than one request per job.
            now = datetime.now(UTC)
            for start in range(0, len(candidates), 10):
                batch = candidates[start : start + 10]
                analyses = await analyze_vacancies_batch_ai(batch)
                for job in batch:
                    analysis = analyses.get(str(job.id))
                    if not analysis:
                        continue
                    job.ai_analysis = analysis
                    if analysis.get("ai_enriched"):
                        job.ai_analyzed_at = now
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
def enrich_jobs_task(user_id: str) -> dict:
    return asyncio.run(_enrich_user_jobs(user_id))


@celery_app.task
def scan_jobs_task(limit: int = 100, user_id: str | None = None) -> dict:
    result = asyncio.run(_scan(limit, user_id))
    if user_id and settings.openai_api_key:
        enrich_jobs_task.delay(user_id)
        result["ai_enrichment_queued"] = True
    else:
        result["ai_enrichment_queued"] = False
    return result


@celery_app.task
def scan_all_users_task(limit: int = 100) -> dict:
    return asyncio.run(_scan_all(limit))


@celery_app.task
def rebuild_matches_task(user_id: str) -> dict:
    return asyncio.run(_rematch_user(user_id))
