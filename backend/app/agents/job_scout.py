import asyncio
from datetime import UTC, datetime
from typing import Any, TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import CandidateProfile, Job
from app.services.availability import verify_job_availability
from app.services.matching import score_job
from app.services.orchestrator import rebuild_matches, sync_jobs
from app.services.vacancy_ai import analyze_vacancy_ai

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # Local fallback until the optional dependency is installed.
    END = None
    StateGraph = None


class JobScoutState(TypedDict, total=False):
    db: AsyncSession
    user_id: Any
    limit: int
    new_jobs: int
    availability: dict[str, int]
    enriched: int
    matched: int
    trace: list[str]
    defer_ai: bool


async def _collect(state: JobScoutState) -> dict:
    count = await sync_jobs(state["db"], state.get("limit", 100))
    return {"new_jobs": count, "trace": state.get("trace", []) + ["collect_public_jobs"]}


async def _check_availability(state: JobScoutState) -> dict:
    result = await verify_job_availability(state["db"], limit=30)
    return {"availability": result, "trace": state.get("trace", []) + ["check_availability"]}


async def _enrich_vacancies(state: JobScoutState) -> dict:
    db = state["db"]

    # Interactive scans should return quickly. AI enrichment can be queued as a
    # separate Celery task after the scan has completed.
    if state.get("defer_ai", True):
        return {
            "enriched": 0,
            "trace": state.get("trace", []) + ["ai_enrichment_deferred"],
        }

    # Without an API key there is nothing expensive to enrich; deterministic
    # matching remains available and the scan should finish immediately.
    if not settings.openai_api_key:
        return {
            "enriched": 0,
            "trace": state.get("trace", []) + ["ai_enrichment_skipped:no_api_key"],
        }

    profile = await db.scalar(
        select(CandidateProfile).where(CandidateProfile.user_id == state["user_id"])
    )
    if profile is None:
        return {"enriched": 0, "trace": state.get("trace", []) + ["ai_enrichment_skipped:no_profile"]}

    result = await db.execute(
        select(Job)
        .where(Job.is_active.is_(True))
        .order_by(Job.collected_at.desc())
        .limit(50)
    )
    recent_jobs = list(result.scalars().all())

    # Use the cheap deterministic matcher as a first-stage filter, then spend
    # LLM calls only on the most promising vacancies.
    candidates = [
        job
        for job in recent_jobs
        if not (job.ai_analysis or {}).get("ai_enriched")
        and score_job(profile, job)["score"] >= 40
    ]
    candidates.sort(key=lambda job: score_job(profile, job)["score"], reverse=True)
    candidates = candidates[:10]

    semaphore = asyncio.Semaphore(4)

    async def analyze(job: Job) -> tuple[Job, dict]:
        async with semaphore:
            return job, await analyze_vacancy_ai(job)

    results = await asyncio.gather(*(analyze(job) for job in candidates))
    enriched = 0
    for job, analysis in results:
        job.ai_analysis = analysis
        if analysis.get("ai_enriched"):
            job.ai_analyzed_at = datetime.now(UTC)
            enriched += 1

    await db.commit()
    return {"enriched": enriched, "trace": state.get("trace", []) + ["analyze_vacancies"]}


async def _rematch(state: JobScoutState) -> dict:
    db = state["db"]
    profile = await db.scalar(
        select(CandidateProfile).where(CandidateProfile.user_id == state["user_id"])
    )
    if profile is None:
        return {"matched": 0, "trace": state.get("trace", []) + ["no_profile"]}

    matched = await rebuild_matches(db, profile)
    return {"matched": matched, "trace": state.get("trace", []) + ["hybrid_rematch"]}


async def _run_sequential(state: JobScoutState) -> JobScoutState:
    for node in (_collect, _check_availability, _enrich_vacancies, _rematch):
        state.update(await node(state))
    return state


async def run_job_scout_agent(
    db: AsyncSession,
    user_id: Any,
    limit: int = 100,
    defer_ai: bool = True,
) -> dict[str, Any]:
    state: JobScoutState = {
        "db": db,
        "user_id": user_id,
        "limit": limit,
        "trace": ["job_scout_agent:start"],
        "defer_ai": defer_ai,
    }

    if StateGraph is None:
        result = await _run_sequential(state)
    else:
        graph = StateGraph(JobScoutState)
        graph.add_node("collect", _collect)
        graph.add_node("availability", _check_availability)
        graph.add_node("enrich", _enrich_vacancies)
        graph.add_node("rematch", _rematch)
        graph.set_entry_point("collect")
        graph.add_edge("collect", "availability")
        graph.add_edge("availability", "enrich")
        graph.add_edge("enrich", "rematch")
        graph.add_edge("rematch", END)
        result = await graph.compile().ainvoke(state)

    return {
        "new_jobs": int(result.get("new_jobs", 0)),
        "availability": result.get("availability", {}),
        "ai_enriched_jobs": int(result.get("enriched", 0)),
        "matched": int(result.get("matched", 0)),
        "agent": "job_scout",
        "engine": "langgraph" if StateGraph is not None else "sequential_fallback",
        "trace": result.get("trace", []) + ["job_scout_agent:end"],
    }
