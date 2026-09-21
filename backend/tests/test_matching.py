from app.models import CandidateProfile, Job
from app.services.matching import score_job


def profile() -> CandidateProfile:
    return CandidateProfile(
        skills=[
            "Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "LangGraph",
            "RAG", "AI Agents", "OpenAI API", "Embeddings", "Vector Search",
        ],
        target_roles=[
            "AI Developer",
            "AI Application Developer",
            "AI Automation Developer",
            "Python Developer",
        ],
        preferred_regions=["Europe", "Worldwide"],
        remote_only=True,
        exclude_keywords=["onsite only"],
        min_salary_usd=50000,
        years_experience=3,
    )


def test_strong_ai_python_match_scores_high() -> None:
    job = Job(
        source="test",
        external_id="1",
        title="AI Developer",
        company="Example",
        location="Remote Europe",
        remote_region="Europe",
        description=(
            "Remote role building AI applications with Python, FastAPI, PostgreSQL, "
            "RAG, LangGraph, OpenAI and Docker. Requires 3+ years of experience."
        ),
        tags=["python", "ai", "remote"],
        salary_min=70000,
        salary_max=90000,
        currency="USD",
        url="https://example.com/job",
    )

    scored = score_job(profile(), job)

    assert scored["score"] >= 85
    assert scored["verdict"] == "apply"
    assert "Python" in scored["matching_skills"]
    assert "RAG" in scored["matching_skills"]


def test_broad_candidate_skill_list_is_not_penalized() -> None:
    candidate = profile()
    candidate.skills = candidate.skills + [
        "PyQt", "C++", "JavaScript", "HTML", "CSS", "RabbitMQ", "Celery",
        "Kubernetes", "GitHub Actions", "Prometheus",
    ]
    job = Job(
        source="test",
        external_id="2",
        title="Python AI Engineer",
        company="Example",
        location="Remote",
        remote_region="Worldwide",
        description="Python, FastAPI, PostgreSQL and RAG. Remote. 2+ years of experience.",
        tags=["python", "ai"],
        salary_min=None,
        salary_max=None,
        currency="USD",
        url="https://example.com/job2",
    )

    scored = score_job(candidate, job)

    assert scored["score"] >= 75


def test_unrelated_role_does_not_get_artificially_high_score() -> None:
    job = Job(
        source="test",
        external_id="3",
        title="Senior Java Developer",
        company="Example",
        location="Remote",
        remote_region="Europe",
        description="Java, Spring Boot, Kafka. Requires 6+ years of experience.",
        tags=["java", "spring"],
        salary_min=70000,
        salary_max=90000,
        currency="USD",
        url="https://example.com/job3",
    )

    scored = score_job(profile(), job)

    assert scored["score"] < 55
    assert scored["verdict"] == "skip"
