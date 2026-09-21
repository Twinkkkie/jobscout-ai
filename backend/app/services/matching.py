import re

from app.models import CandidateProfile, Job

STOPWORDS = {
    "and", "the", "with", "for", "you", "your", "our", "are", "will", "from",
    "this", "that", "have", "has", "job", "role", "work", "team", "remote",
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.\-]{1,30}", value.lower())
        if token not in STOPWORDS
    }


def score_job(profile: CandidateProfile, job: Job) -> dict:
    job_text = " ".join(
        [job.title, job.description, " ".join(job.tags or []), job.location, job.remote_region]
    ).lower()

    skills = [skill for skill in (profile.skills or []) if skill]
    matching = [skill for skill in skills if skill.lower() in job_text]

    role_hit = any(role.lower() in job.title.lower() for role in (profile.target_roles or []))
    excluded = [word for word in (profile.exclude_keywords or []) if word.lower() in job_text]

    candidate_skill_tokens = _tokens(" ".join(skills))
    job_tokens = _tokens(job_text)
    gap_candidates = sorted(job_tokens - candidate_skill_tokens)

    technical_markers = [
        "python", "fastapi", "django", "flask", "postgresql", "docker", "kubernetes",
        "redis", "celery", "aws", "azure", "gcp", "react", "typescript", "sqlalchemy",
        "rabbitmq", "rag", "llm", "langgraph",
    ]
    gaps = [marker for marker in technical_markers if marker in job_text and marker not in candidate_skill_tokens]

    score = 30.0
    if role_hit:
        score += 25
    if skills:
        score += min(30, (len(matching) / max(1, len(skills))) * 40)
    if profile.remote_only and "remote" in job_text:
        score += 8
    if (
        profile.min_salary_usd
        and job.salary_max
        and job.salary_max < profile.min_salary_usd
    ):
        score -= 20
    if excluded:
        score -= min(50, 20 * len(excluded))

    score = max(0.0, min(100.0, round(score, 1)))
    verdict = "apply" if score >= 75 else "maybe" if score >= 55 else "skip"

    reasons = []
    if role_hit:
        reasons.append("Target role matches the vacancy title.")
    if matching:
        reasons.append(f"{len(matching)} profile skills appear in the vacancy.")
    if "remote" in job_text:
        reasons.append("The role is described as remote.")
    if excluded:
        reasons.append("Excluded keywords detected: " + ", ".join(excluded))

    return {
        "score": score,
        "matching_skills": matching[:15],
        "skill_gaps": gaps[:8],
        "reasons": reasons[:6],
        "verdict": verdict,
        "debug_gap_candidates": gap_candidates[:5],
    }
