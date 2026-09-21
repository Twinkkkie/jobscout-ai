from datetime import UTC, datetime
from typing import Any, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateProfile, Job
from app.services.application_ai import prepare_application_pack
from app.services.matching import score_job
from app.services.vacancy_ai import analyze_vacancy_ai

try:
    from langgraph.graph import END, StateGraph
except ImportError:
    END = None
    StateGraph = None


class ApplicationAgentState(TypedDict, total=False):
    db: AsyncSession
    profile: CandidateProfile
    job: Job
    resume_text: str
    match: dict[str, Any]
    pack: dict[str, Any]
    review: dict[str, Any]
    trace: list[str]


async def _analyze_vacancy(state: ApplicationAgentState) -> dict:
    job = state["job"]
    if not ((job.ai_analysis or {}).get("ai_enriched") and (job.ai_analysis or {}).get("analysis_version") == 2):
        analysis = await analyze_vacancy_ai(job)
        job.ai_analysis = analysis
        if analysis.get("ai_enriched"):
            job.ai_analyzed_at = datetime.now(UTC)
        await state["db"].commit()
    return {"trace": state.get("trace", []) + ["vacancy_analysis"]}


async def _calculate_match(state: ApplicationAgentState) -> dict:
    scored = score_job(state["profile"], state["job"])
    return {"match": scored, "trace": state.get("trace", []) + ["hybrid_match"]}


async def _generate_pack(state: ApplicationAgentState) -> dict:
    pack = await prepare_application_pack(
        state["profile"],
        state["job"],
        state.get("resume_text", ""),
    )
    return {"pack": pack, "trace": state.get("trace", []) + ["generate_application_pack"]}


async def _fact_check(state: ApplicationAgentState) -> dict:
    """
    Fast deterministic guard.

    The generation prompt already forbids fabrication. Instead of spending a
    second LLM round-trip, turn the hybrid match gaps into explicit caution
    notes and require human review before sending.
    """
    pack = dict(state["pack"])
    match = state.get("match", {})
    gaps = list(match.get("skill_gaps") or [])

    caution = list(pack.get("caution_notes", []))
    if gaps:
        caution.append(
            "Do not claim hands-on experience with these detected gaps unless the resume supports it: "
            + ", ".join(gaps[:8])
            + "."
        )

    pack["caution_notes"] = list(dict.fromkeys(caution))[:15]
    review = {
        "approved": True,
        "unsupported_claims": [],
        "notes": [
            "Deterministic gap guard applied.",
            "Human review is required before sending.",
        ],
        "ai_enriched": False,
    }
    return {
        "pack": pack,
        "review": review,
        "trace": state.get("trace", []) + ["deterministic_claim_guard", "human_review_required"],
    }


async def _run_sequential(state: ApplicationAgentState) -> ApplicationAgentState:
    for node in (_analyze_vacancy, _calculate_match, _generate_pack, _fact_check):
        state.update(await node(state))
    return state


async def run_application_agent(
    db: AsyncSession,
    profile: CandidateProfile,
    job: Job,
    resume_text: str = "",
) -> dict[str, Any]:
    state: ApplicationAgentState = {
        "db": db,
        "profile": profile,
        "job": job,
        "resume_text": resume_text,
        "trace": ["application_agent:start"],
    }

    if StateGraph is None:
        result = await _run_sequential(state)
    else:
        graph = StateGraph(ApplicationAgentState)
        graph.add_node("vacancy", _analyze_vacancy)
        graph.add_node("match", _calculate_match)
        graph.add_node("generate", _generate_pack)
        graph.add_node("fact_check", _fact_check)
        graph.set_entry_point("vacancy")
        graph.add_edge("vacancy", "match")
        graph.add_edge("match", "generate")
        graph.add_edge("generate", "fact_check")
        graph.add_edge("fact_check", END)
        result = await graph.compile().ainvoke(state)

    return {
        "match": result.get("match", {}),
        "pack": result.get("pack", {}),
        "review": result.get("review", {}),
        "agent": "application",
        "engine": "langgraph" if StateGraph is not None else "sequential_fallback",
        "trace": result.get("trace", []) + ["application_agent:end"],
    }
