import asyncio
from datetime import UTC, datetime

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Application, Job


CLOSED_MARKERS = (
    "job is no longer available",
    "position is no longer available",
    "position has been filled",
    "job has expired",
    "job posting has expired",
    "this job is closed",
    "this position is closed",
    "no longer accepting applications",
    "vacancy has expired",
    "this vacancy is no longer available",
)


async def _check_url(client: httpx.AsyncClient, job: Job, semaphore: asyncio.Semaphore) -> tuple[Job, bool | None]:
    """
    Return True for confirmed active, False for confirmed closed, None when uncertain.
    We intentionally do not mark 401/403/429/network failures as closed.
    """
    async with semaphore:
        try:
            response = await client.get(job.url)
        except (httpx.HTTPError, ValueError):
            return job, None

    if response.status_code in {404, 410}:
        return job, False
    if response.status_code >= 500 or response.status_code in {401, 403, 429}:
        return job, None

    text = response.text[:500_000].lower()
    if any(marker in text for marker in CLOSED_MARKERS):
        return job, False

    if 200 <= response.status_code < 400:
        return job, True
    return job, None


async def verify_job_availability(db: AsyncSession, limit: int = 140) -> dict[str, int]:
    """
    Re-check active jobs, prioritizing anything the user has saved/applied to.
    Only strong closure signals are used so anti-bot pages do not create false closures.
    """
    saved_job_ids = select(Application.job_id).distinct()
    query = (
        select(Job)
        .where(
            Job.is_active.is_(True),
            or_(Job.id.in_(saved_job_ids), Job.collected_at.is_not(None)),
        )
        .order_by(Job.collected_at.desc())
        .limit(limit)
    )
    jobs = list((await db.execute(query)).scalars().all())
    if not jobs:
        return {"checked": 0, "closed": 0, "active": 0, "uncertain": 0}

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; JobScoutAI/0.1; +https://github.com/Twinkkkie/jobscout-ai)"
    }
    semaphore = asyncio.Semaphore(12)
    async with httpx.AsyncClient(timeout=12, follow_redirects=True, headers=headers) as client:
        results = await asyncio.gather(
            *[_check_url(client, job, semaphore) for job in jobs],
            return_exceptions=False,
        )

    now = datetime.now(UTC)
    closed = 0
    active = 0
    uncertain = 0

    for job, state in results:
        job.last_checked_at = now
        if state is False:
            job.is_active = False
            job.closed_at = now
            closed += 1
        elif state is True:
            job.is_active = True
            job.closed_at = None
            active += 1
        else:
            uncertain += 1

    await db.commit()
    return {
        "checked": len(jobs),
        "closed": closed,
        "active": active,
        "uncertain": uncertain,
    }
