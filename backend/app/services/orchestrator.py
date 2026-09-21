from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateProfile, Job, JobMatch
from app.services.collectors import collect_public_jobs
from app.services.matching import score_job


async def sync_jobs(db: AsyncSession, limit: int = 100) -> int:
    collected = await collect_public_jobs(limit)
    saved = 0
    for item in collected:
        existing = await db.scalar(
            select(Job).where(Job.source == item.source, Job.external_id == item.external_id)
        )
        if existing is None:
            db.add(Job(**item.__dict__))
            saved += 1
        else:
            for key, value in item.__dict__.items():
                setattr(existing, key, value)
    await db.commit()
    return saved


async def rebuild_matches(db: AsyncSession, profile: CandidateProfile, limit: int = 250) -> int:
    result = await db.execute(select(Job).order_by(Job.collected_at.desc()).limit(limit))
    jobs = list(result.scalars().all())
    count = 0

    for job in jobs:
        scored = score_job(profile, job)
        match = await db.scalar(
            select(JobMatch).where(JobMatch.user_id == profile.user_id, JobMatch.job_id == job.id)
        )
        if match is None:
            match = JobMatch(user_id=profile.user_id, job_id=job.id)
            db.add(match)
        match.score = scored["score"]
        match.matching_skills = scored["matching_skills"]
        match.skill_gaps = scored["skill_gaps"]
        match.reasons = scored["reasons"]
        match.verdict = scored["verdict"]
        count += 1

    await db.commit()
    return count
