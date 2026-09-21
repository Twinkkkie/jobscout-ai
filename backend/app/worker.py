import asyncio
from uuid import UUID

from celery import Celery
from sqlalchemy import select

from app.core.config import settings
from app.db import SessionLocal
from app.models import CandidateProfile
from app.services.orchestrator import rebuild_matches, sync_jobs

celery_app = Celery("jobscout", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_track_started=True, task_acks_late=True, worker_prefetch_multiplier=1)


async def _scan(limit: int, user_id: str | None) -> dict:
    async with SessionLocal() as db:
        new_jobs = await sync_jobs(db, limit)
        matched = 0
        if user_id:
            profile = await db.scalar(
                select(CandidateProfile).where(CandidateProfile.user_id == UUID(user_id))
            )
            if profile:
                matched = await rebuild_matches(db, profile)
        return {"new_jobs": new_jobs, "matched": matched}


@celery_app.task
def scan_jobs_task(limit: int = 100, user_id: str | None = None) -> dict:
    return asyncio.run(_scan(limit, user_id))
