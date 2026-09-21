from collections import Counter
from typing import Any, TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Application, CandidateProfile, Job, JobMatch
from app.services.ai_utils import ask_openai_json, clean_string_list

try:
    from langgraph.graph import END, StateGraph
except ImportError:
    END = None
    StateGraph = None


class CareerAgentState(TypedDict, total=False):
    db: AsyncSession
    profile: CandidateProfile
    stats: dict[str, Any]
    insight: dict[str, Any]
    trace: list[str]


async def _gather(state: CareerAgentState) -> dict:
    db = state["db"]
    profile = state["profile"]

    rows = (
        await db.execute(
            select(JobMatch, Job)
            .join(Job, Job.id == JobMatch.job_id)
            .where(JobMatch.user_id == profile.user_id, Job.is_active.is_(True))
            .order_by(JobMatch.score.desc())
            .limit(120)
        )
    ).all()

    applications = list(
        (
            await db.execute(
                select(Application).where(Application.user_id == profile.user_id)
            )
        ).scalars().all()
    )

    gap_counter: Counter[str] = Counter()
    strength_counter: Counter[str] = Counter()
    scores: list[float] = []
    for match, _job in rows:
        scores.append(match.score)
        gap_counter.update(match.skill_gaps or [])
        strength_counter.update(match.matching_skills or [])

    statuses = Counter(app.status for app in applications)
    stats = {
        "matches_analyzed": len(rows),
        "average_match": round(sum(scores) / len(scores), 1) if scores else 0,
        "strong_matches": sum(1 for score in scores if score >= 75),
        "recurring_gaps": [name for name, _ in gap_counter.most_common(10)],
        "strongest_skills": [name for name, _ in strength_counter.most_common(10)],
        "application_statuses": dict(statuses),
        "target_roles": profile.target_roles or [],
        "seniority_levels": profile.seniority_levels or [],
    }
    return {"stats": stats, "trace": state.get("trace", []) + ["aggregate_history"]}


async def _synthesize(state: CareerAgentState) -> dict:
    profile = state["profile"]
    stats = state["stats"]
    fallback = {
        "summary": (
            f"Based on {stats['matches_analyzed']} current matches, the average match is "
            f"{stats['average_match']}%. The most repeated gaps are "
            f"{', '.join(stats['recurring_gaps'][:5]) or 'not yet clear'}."
        ),
        "recurring_gaps": stats["recurring_gaps"],
        "strongest_skills": stats["strongest_skills"],
        "target_role_observations": [
            f"Current targets: {', '.join(profile.target_roles or []) or 'not specified'}.",
            f"Selected seniority: {', '.join(profile.seniority_levels or []) or 'not specified'}.",
        ],
        "recommended_actions": [
            f"Prioritize learning/evidence for {gap}." for gap in stats["recurring_gaps"][:3]
        ],
        "ai_enriched": False,
    }

    prompt = f"""
Act as a career-analysis agent using only the supplied job-search evidence.
Do not invent market statistics, salary data, interview outcomes, or candidate experience.

Return ONE valid JSON object and no markdown:
{{
  "summary": "3-5 concise sentences",
  "recurring_gaps": ["..."],
  "strongest_skills": ["..."],
  "target_role_observations": ["..."],
  "recommended_actions": ["3-6 concrete actions"],
  "ai_enriched": true
}}

Candidate:
headline: {profile.headline}
years: {profile.years_experience}
skills: {profile.skills}
targets: {profile.target_roles}
seniority: {profile.seniority_levels}
AI resume profile: {profile.ai_profile or {}}

Observed JobScout history:
{stats}
"""
    parsed = await ask_openai_json(prompt)
    if not parsed:
        insight = fallback
    else:
        insight = {
            "summary": str(parsed.get("summary") or fallback["summary"]).strip()[:1800],
            "recurring_gaps": clean_string_list(parsed.get("recurring_gaps"), 12)
            or fallback["recurring_gaps"],
            "strongest_skills": clean_string_list(parsed.get("strongest_skills"), 12)
            or fallback["strongest_skills"],
            "target_role_observations": clean_string_list(
                parsed.get("target_role_observations"), 10
            ) or fallback["target_role_observations"],
            "recommended_actions": clean_string_list(parsed.get("recommended_actions"), 10)
            or fallback["recommended_actions"],
            "ai_enriched": True,
        }

    return {"insight": insight, "trace": state.get("trace", []) + ["career_synthesis"]}


async def _run_sequential(state: CareerAgentState) -> CareerAgentState:
    for node in (_gather, _synthesize):
        state.update(await node(state))
    return state


async def run_career_agent(
    db: AsyncSession,
    profile: CandidateProfile,
) -> dict[str, Any]:
    state: CareerAgentState = {
        "db": db,
        "profile": profile,
        "trace": ["career_agent:start"],
    }

    if StateGraph is None:
        result = await _run_sequential(state)
    else:
        graph = StateGraph(CareerAgentState)
        graph.add_node("gather", _gather)
        graph.add_node("synthesize", _synthesize)
        graph.set_entry_point("gather")
        graph.add_edge("gather", "synthesize")
        graph.add_edge("synthesize", END)
        result = await graph.compile().ainvoke(state)

    insight = dict(result.get("insight", {}))
    insight["agent"] = "career"
    insight["engine"] = "langgraph" if StateGraph is not None else "sequential_fallback"
    insight["trace"] = result.get("trace", []) + ["career_agent:end"]
    return insight
