from datetime import UTC, datetime
from html import unescape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateProfile, Job, JobMatch
from app.services.collectors import collect_public_jobs
from app.services.matching import score_job


def _decode_job_item(item):
    for field in ("title", "company", "location", "remote_region", "description"):
        value = getattr(item, field, "")
        if isinstance(value, str):
            setattr(item, field, unescape(value))
    item.tags = [unescape(str(tag)) for tag in (item.tags or [])]
    return item


async def sync_jobs(db: AsyncSession, limit: int = 100) -> int:
    collected = await collect_public_jobs(limit)
    saved = 0
    now = datetime.now(UTC)
    for item in collected:
        item = _decode_job_item(item)
        existing = await db.scalar(
            select(Job).where(Job.source == item.source, Job.external_id == item.external_id)
        )
        if existing is None:
            db.add(
                Job(
                    **item.__dict__,
                    last_seen_at=now,
                    is_active=True,
                    closed_at=None,
                )
            )
            saved += 1
        else:
            for key, value in item.__dict__.items():
                setattr(existing, key, value)
            existing.last_seen_at = now
            existing.is_active = True
            existing.closed_at = None
    await db.commit()
    return saved


async def rebuild_matches(db: AsyncSession, profile: CandidateProfile, limit: int | None = None) -> int:
    query = (
        select(Job)
        .where(Job.is_active.is_(True))
        .order_by(Job.collected_at.desc())
    )
    if limit is not None:
        query = query.limit(limit)
    result = await db.execute(query)
    jobs = list(result.scalars().all())
    if not jobs:
        return 0

    job_ids = [job.id for job in jobs]
    existing_result = await db.execute(
        select(JobMatch).where(
            JobMatch.user_id == profile.user_id,
            JobMatch.job_id.in_(job_ids),
        )
    )
    existing_by_job = {match.job_id: match for match in existing_result.scalars().all()}

    for job in jobs:
        scored = score_job(profile, job)
        match = existing_by_job.get(job.id)
        if match is None:
            match = JobMatch(user_id=profile.user_id, job_id=job.id)
            db.add(match)
        match.score = scored["score"]
        match.matching_skills = scored["matching_skills"]
        match.skill_gaps = scored["skill_gaps"]
        match.reasons = scored["reasons"]
        match.verdict = scored["verdict"]
        # Explanations are generated on demand from the current score/requirements.
        match.ai_explanation = {}

    await db.commit()
    return len(jobs)
