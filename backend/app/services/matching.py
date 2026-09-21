import re

from app.models import CandidateProfile, Job

STOPWORDS = {
    "and", "the", "with", "for", "you", "your", "our", "are", "will", "from",
    "this", "that", "have", "has", "job", "role", "work", "team", "remote",
}

SKILL_ALIASES: dict[str, list[str]] = {
    "python": ["python"],
    "fastapi": ["fastapi"],
    "django": ["django"],
    "flask": ["flask"],
    "postgresql": ["postgresql", "postgres"],
    "sql": ["sql"],
    "sqlalchemy": ["sqlalchemy"],
    "alembic": ["alembic"],
    "docker": ["docker"],
    "kubernetes": ["kubernetes", "k8s"],
    "redis": ["redis"],
    "celery": ["celery"],
    "rabbitmq": ["rabbitmq"],
    "aws": ["aws", "amazon web services"],
    "azure": ["azure"],
    "gcp": ["gcp", "google cloud"],
    "react": ["react"],
    "typescript": ["typescript"],
    "javascript": ["javascript"],
    "rag": ["rag", "retrieval-augmented generation", "retrieval augmented generation"],
    "llm": ["llm", "large language model", "large language models", "generative ai", "genai"],
    "langgraph": ["langgraph"],
    "openai": ["openai"],
    "embeddings": ["embedding", "embeddings"],
    "vector search": ["vector search", "semantic search"],
    "pgvector": ["pgvector"],
    "ai agents": ["ai agent", "ai agents", "agentic"],
    "pydantic": ["pydantic"],
    "pytest": ["pytest"],
    "git": ["git"],
    "github actions": ["github actions"],
    "prometheus": ["prometheus"],
    "linux": ["linux"],
}

ROLE_FAMILIES: dict[str, list[str]] = {
    "ai": [
        "ai developer", "ai engineer", "artificial intelligence", "llm engineer",
        "llm developer", "generative ai", "genai", "ai application",
        "ai automation", "agent developer", "rag engineer",
    ],
    "python": ["python developer", "python engineer", "python software"],
    "backend": ["backend", "back-end", "backend engineer", "backend developer"],
    "software": ["software engineer", "software developer"],
    "ml": ["machine learning", "ml engineer"],
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.\-]{1,30}", value.lower())
        if token not in STOPWORDS
    }


def _contains_phrase(text: str, phrase: str) -> bool:
    return phrase.lower() in text.lower()


def _candidate_skill_keys(skills: list[str]) -> set[str]:
    text = " ".join(skills).lower()
    found: set[str] = set()
    for key, aliases in SKILL_ALIASES.items():
        if any(alias in text for alias in aliases):
            found.add(key)
    return found


def _job_skill_keys(job_text: str) -> set[str]:
    found: set[str] = set()
    for key, aliases in SKILL_ALIASES.items():
        if any(alias in job_text for alias in aliases):
            found.add(key)
    return found


def _role_score(target_roles: list[str], title: str) -> tuple[float, str | None]:
    title_lower = title.lower()
    targets = [role.lower() for role in target_roles if role]

    if any(target in title_lower for target in targets):
        return 35.0, "Target role directly matches the vacancy title."

    candidate_families: set[str] = set()
    for family, markers in ROLE_FAMILIES.items():
        if any(any(marker in target for marker in markers) for target in targets):
            candidate_families.add(family)

    job_families = {
        family
        for family, markers in ROLE_FAMILIES.items()
        if any(marker in title_lower for marker in markers)
    }

    if "ai" in candidate_families and "ai" in job_families:
        return 33.0, "The vacancy is in the same AI role family as your target roles."
    if candidate_families & job_families:
        return 29.0, "The vacancy title is in the same role family as your target roles."

    title_tokens = _tokens(title)
    target_tokens = _tokens(" ".join(target_roles))
    overlap = title_tokens & target_tokens
    if overlap:
        return 20.0, "The vacancy title overlaps with your target-role keywords."

    # AI-focused Python candidates can still be relevant for generic software/backend roles.
    if "ai" in candidate_families and ({"backend", "python", "software"} & job_families):
        return 15.0, "The role is adjacent to your AI/Python backend focus."

    return 0.0, None


def _required_years(job_text: str) -> int | None:
    values = [
        int(value)
        for value in re.findall(
            r"(?<!\d)(\d{1,2})\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:professional\s+)?experience",
            job_text,
        )
        if int(value) <= 20
    ]
    return min(values) if values else None


def score_job(profile: CandidateProfile, job: Job) -> dict:
    job_text = " ".join(
        [job.title, job.description, " ".join(job.tags or []), job.location, job.remote_region]
    ).lower()

    skills = [skill for skill in (profile.skills or []) if skill]
    candidate_keys = _candidate_skill_keys(skills)
    required_keys = _job_skill_keys(job_text)
    matched_keys = candidate_keys & required_keys

    # Preserve the user's original skill names in the UI when possible.
    matching = []
    for skill in skills:
        skill_lower = skill.lower()
        for key in matched_keys:
            aliases = SKILL_ALIASES[key]
            if any(alias in skill_lower for alias in aliases):
                matching.append(skill)
                break
    # De-duplicate while retaining order.
    matching = list(dict.fromkeys(matching))

    gaps = sorted(required_keys - candidate_keys)

    excluded = [word for word in (profile.exclude_keywords or []) if word.lower() in job_text]

    score = 0.0
    reasons: list[str] = []

    role_points, role_reason = _role_score(profile.target_roles or [], job.title)
    score += role_points
    if role_reason:
        reasons.append(role_reason)

    # Avoid surfacing completely unrelated remote roles just because their
    # descriptions mention one generic AI/tech term.
    role_relevant = role_points >= 15.0

    # Score skill coverage against what the vacancy asks for, not against every
    # skill the candidate happens to know. A broad profile should not be penalized.
    if required_keys:
        coverage = len(matched_keys) / len(required_keys)
        skill_points = 40.0 * coverage
        score += skill_points
        if matched_keys:
            reasons.append(
                f"You match {len(matched_keys)} of {len(required_keys)} detected technical requirements."
            )
    else:
        # If a listing has no detectable tech stack, keep skills neutral rather
        # than punishing the candidate.
        score += 20.0
        reasons.append("The listing does not expose enough structured technical requirements.")

    remote_text = " ".join([job.location, job.remote_region, job.description]).lower()
    if profile.remote_only:
        if "remote" in remote_text:
            score += 10.0
            reasons.append("The role is described as remote.")
    else:
        score += 10.0

    required_years = _required_years(job_text)
    if required_years is None:
        score += 8.0
    elif profile.years_experience >= required_years:
        score += 10.0
        reasons.append(
            f"Your {profile.years_experience} years of experience meet the detected {required_years}+ year requirement."
        )
    elif required_years - profile.years_experience == 1:
        score += 5.0
        reasons.append(
            f"The listing asks for about {required_years}+ years; you are one year below that detected requirement."
        )
    else:
        reasons.append(
            f"The listing appears to ask for {required_years}+ years, above your stated {profile.years_experience} years."
        )

    # Salary should only reduce the score when the listing explicitly states a
    # maximum below the user's floor. Missing salary is not a negative signal.
    if profile.min_salary_usd and job.salary_max:
        if job.salary_max >= profile.min_salary_usd:
            score += 5.0
            reasons.append("The published salary range reaches your minimum.")
        else:
            score -= 15.0
            reasons.append("The published maximum salary is below your minimum.")
    else:
        score += 5.0

    if excluded:
        score -= min(50.0, 20.0 * len(excluded))
        reasons.append("Excluded keywords detected: " + ", ".join(excluded))

    # Hard relevance guard: a title outside the candidate's target/adjacent
    # role families must have at least two concrete technical skill matches.
    # This filters roles such as voice actors, psychiatrists, sales, support,
    # and similar listings that happen to mention AI in the description.
    if not role_relevant and len(matched_keys) < 2:
        score = min(score, 35.0)
        reasons.append("The vacancy title is outside your target role families.")

    score = max(0.0, min(100.0, round(score, 1)))
    verdict = "apply" if score >= 75 else "maybe" if score >= 55 else "skip"

    return {
        "score": score,
        "matching_skills": matching[:15],
        "skill_gaps": gaps[:8],
        "reasons": reasons[:6],
        "verdict": verdict,
    }
