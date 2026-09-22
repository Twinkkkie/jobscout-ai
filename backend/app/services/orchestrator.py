import hashlib
from datetime import UTC, datetime
from html import unescape

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import CandidateProfile, Job, JobMatch
from app.services.collectors import collect_public_jobs
from app.services.matching import MATCHING_VERSION, score_job


def _decode_job_item(item):
    for field in ("title", "company", "location", "remote_region", "description"):
        value = getattr(item, field, "")
        if isinstance(value, str):
            setattr(item, field, unescape(value))

    # Some RSS/API providers use very long URLs as external IDs. Keep the
    # uniqueness stable without ever depending on a VARCHAR-sized identifier.
    external_id = unescape(str(getattr(item, "external_id", "") or "")).strip()
    if len(external_id) > 240:
        external_id = "sha256:" + hashlib.sha256(external_id.encode("utf-8")).hexdigest()
    item.external_id = external_id

    item.tags = [unescape(str(tag)) for tag in (item.tags or [])]
    return item


async def sync_jobs(db: AsyncSession, limit: int = 100) -> int:
    collected = [_decode_job_item(item) for item in await collect_public_jobs(limit)]
    if not collected:
        return 0

    now = datetime.now(UTC)
    keys = [(item.source, item.external_id) for item in collected]
    existing_rows = list(
        (
            await db.execute(
                select(Job).where(tuple_(Job.source, Job.external_id).in_(keys))
            )
        ).scalars().all()
    )
    existing_by_key = {(job.source, job.external_id): job for job in existing_rows}

    saved = 0
    for item in collected:
        existing = existing_by_key.get((item.source, item.external_id))
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
        match.matching_version = MATCHING_VERSION
        has_current_ai = bool(
            (job.ai_analysis or {}).get("ai_enriched")
            and (job.ai_analysis or {}).get("analysis_version") == 4
        )
        match.is_final = has_current_ai if settings.openai_api_key else True

    await db.commit()
    return len(jobs)



async def ensure_current_matches(
    db: AsyncSession,
    profile: CandidateProfile,
) -> bool:
    """
    Recalculate persisted matches only when they were produced by an older
    matching algorithm. This clears stale skills/gaps after matcher upgrades
    without making every normal page load expensive.
    """
    stale = await db.scalar(
        select(JobMatch.id)
        .where(
            JobMatch.user_id == profile.user_id,
            JobMatch.matching_version != MATCHING_VERSION,
        )
        .limit(1)
    )
    if stale is None:
        return False

    await rebuild_matches(db, profile)
    return True
