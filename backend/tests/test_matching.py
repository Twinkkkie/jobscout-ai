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



def test_displayed_skill_counts_match_scoring_reason() -> None:
    candidate = profile()
    candidate.skills = candidate.skills + ["Cursor"]
    job = Job(
        source="test",
        external_id="4",
        title="AI Software Engineer",
        company="Example",
        location="Remote",
        remote_region="Worldwide",
        description=(
            "Build AI applications with Python, FastAPI, PostgreSQL, RAG, "
            "LangGraph, OpenAI, Docker and Cursor."
        ),
        tags=["ai", "python"],
        salary_min=None,
        salary_max=None,
        currency="USD",
        url="https://example.com/job4",
    )

    scored = score_job(candidate, job)
    total = len(scored["matching_skills"]) + len(scored["skill_gaps"])

    assert total > 0
    assert any(
        f"You match {len(scored['matching_skills'])} of {total}" in reason
        for reason in scored["reasons"]
    )


def test_selected_seniority_hard_filters_senior_role() -> None:
    candidate = profile()
    candidate.seniority_levels = ["junior", "middle"]
    job = Job(
        source="test",
        external_id="5",
        title="Senior Python AI Engineer",
        company="Example",
        location="Remote",
        remote_region="Europe",
        description=(
            "Python, FastAPI, PostgreSQL, RAG, LangGraph, Docker and OpenAI. "
            "Remote role requiring 3+ years of experience."
        ),
        tags=["python", "ai", "senior"],
        salary_min=70000,
        salary_max=90000,
        currency="USD",
        url="https://example.com/job5",
    )

    scored = score_job(candidate, job)

    assert scored["score"] < 45
    assert scored["verdict"] == "skip"
    assert any("outside your selected levels" in reason for reason in scored["reasons"])



def test_web_php_role_exposes_missing_ecommerce_stack() -> None:
    candidate = profile()
    candidate.skills = candidate.skills + ["JavaScript", "PHP", "React"]
    job = Job(
        source="test",
        external_id="6",
        title=(
            "Web-Entwickler:in E-Commerce PHP / Laravel / JavaScript "
            "(Shopify, PlentyONE) - Vollzeit (m/w/d) in Dortmund"
        ),
        company="apio GmbH",
        location="Dortmund",
        remote_region="",
        description=(
            "Develop e-commerce applications with PHP, Laravel, JavaScript, React, "
            "Shopify and PlentyONE."
        ),
        tags=["php", "javascript", "e-commerce"],
        salary_min=None,
        salary_max=None,
        currency="EUR",
        url="https://example.com/job6",
    )

    scored = score_job(candidate, job)

    assert "JavaScript" in scored["matching_skills"]
    assert "PHP" in scored["matching_skills"]
    assert "Laravel" in scored["skill_gaps"]
    assert "Shopify" in scored["skill_gaps"]
    assert "PlentyONE" in scored["skill_gaps"]
    assert scored["score"] < 45
    assert scored["verdict"] == "skip"
    assert any("role family is outside" in reason for reason in scored["reasons"])



def test_ai_software_engineer_is_recognized_as_ai_family() -> None:
    candidate = profile()
    candidate.seniority_levels = ["junior", "middle"]
    candidate.skills = candidate.skills + ["Kubernetes", "React", "TypeScript", "Claude", "Cursor"]
    job = Job(
        source="test",
        external_id="7",
        title="AI Software Engineer",
        company="Example",
        location="Remote",
        remote_region="Worldwide",
        description=(
            "Build AI software with AI Agents, Claude, Kubernetes, LLMs, "
            "PostgreSQL, React and TypeScript. Remote."
        ),
        tags=["software engineering"],
        salary_min=None,
        salary_max=None,
        currency="USD",
        url="https://example.com/job7",
    )

    scored = score_job(candidate, job)

    assert scored["score"] >= 85
    assert scored["verdict"] == "apply"
    assert any("same AI role family" in reason for reason in scored["reasons"])



def test_ai_analysis_drives_structured_gaps() -> None:
    candidate = profile()
    candidate.skills = candidate.skills + ["Docker", "Kubernetes"]
    job = Job(
        source="test",
        external_id="8",
        title="AI Platform Engineer",
        company="Example",
        location="Remote",
        remote_region="Worldwide",
        description="Build AI platform services.",
        tags=["ai"],
        salary_min=None,
        salary_max=None,
        currency="USD",
        url="https://example.com/job8",
        ai_analysis={
            "ai_enriched": True,
            "analysis_version": 4,
            "role_family": "ai",
            "seniority": "middle",
            "must_have_skills": ["Python", "FastAPI", "LangGraph", "AWS Bedrock"],
            "nice_to_have_skills": ["Docker", "Kubernetes"],
            "years_required": 3,
        },
    )

    scored = score_job(candidate, job)

    assert "Python" in scored["matching_skills"]
    assert "FastAPI" in scored["matching_skills"]
    assert "LangGraph" in scored["matching_skills"]
    assert "Docker" in scored["matching_skills"]
    assert "Kubernetes" in scored["matching_skills"]
    assert "AWS Bedrock" in scored["skill_gaps"]
    assert any("Hybrid analysis found" in reason for reason in scored["reasons"])


def test_ai_seniority_is_a_hard_constraint_even_when_title_is_ambiguous() -> None:
    candidate = profile()
    candidate.seniority_levels = ["junior", "middle"]
    job = Job(
        source="test",
        external_id="9",
        title="AI Engineer",
        company="Example",
        location="Remote",
        remote_region="Europe",
        description="Python, FastAPI, RAG and LangGraph.",
        tags=["ai"],
        salary_min=None,
        salary_max=None,
        currency="USD",
        url="https://example.com/job9",
        ai_analysis={
            "ai_enriched": True,
            "analysis_version": 4,
            "role_family": "ai",
            "seniority": "senior",
            "must_have_skills": ["Python", "FastAPI", "RAG", "LangGraph"],
            "nice_to_have_skills": [],
            "years_required": 5,
        },
    )

    scored = score_job(candidate, job)

    assert scored["score"] < 45
    assert scored["verdict"] == "skip"
    assert any("outside your selected levels" in reason for reason in scored["reasons"])



def test_broad_ai_capabilities_use_full_candidate_evidence() -> None:
    candidate = profile()
    candidate.summary = (
        "AI-focused Python software developer building LLM, RAG and agentic applications "
        "and using AI-assisted development tools in day-to-day engineering."
    )
    candidate.ai_profile = {
        "skills": ["Prompt Engineering", "Llama", "Ollama"],
        "experience_signals": [
            "Uses Cursor, Codex and ChatGPT to test and adopt new AI tools in development."
        ],
        "skill_evidence": [
            {
                "skill": "Prompt Engineering",
                "evidence_level": "project",
                "evidence": "Designed prompts and structured outputs for AI applications.",
            }
        ],
    }
    job = Job(
        source="test",
        external_id="10",
        title="AI Software Engineer",
        company="Example",
        location="Remote",
        remote_region="Worldwide",
        description="Build and test AI-powered software products.",
        tags=["ai", "software engineering"],
        salary_min=None,
        salary_max=None,
        currency="USD",
        url="https://example.com/job10",
        ai_analysis={
            "ai_enriched": True,
            "analysis_version": 4,
            "role_family": "ai",
            "seniority": "middle",
            "must_have_skills": [
                "Software engineering",
                "Artificial intelligence",
                "Open-source AI tools and models",
                "Testing and adopting new AI tools and models",
                "Prompt engineering",
            ],
            "nice_to_have_skills": [],
            "years_required": 3,
        },
    )

    scored = score_job(candidate, job)

    gap_keys = {gap.lower() for gap in scored["skill_gaps"]}
    assert "software engineering" not in gap_keys
    assert "artificial intelligence" not in gap_keys
    assert "open-source ai tools and models" not in gap_keys
    assert "testing and adopting new ai tools and models" not in gap_keys
    assert "prompt engineering" not in gap_keys
    assert any(skill.lower() == "prompt engineering" for skill in scored["matching_skills"])



def test_ai_company_suffix_does_not_turn_cco_into_ai_engineering_match() -> None:
    candidate = profile()
    job = Job(
        source="test",
        external_id="11",
        title="Chief Commercial Officer (CCO) | AI Product Company",
        company="Newbridge",
        location="Remote",
        remote_region="Worldwide",
        description="Lead commercial strategy, revenue, partnerships and go-to-market.",
        tags=["ai", "commercial", "leadership"],
        salary_min=None,
        salary_max=None,
        currency="USD",
        url="https://example.com/job11",
        ai_analysis={
            "ai_enriched": True,
            "analysis_version": 4,
            "role_family": "ai",
            "seniority": "lead",
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "years_required": None,
        },
    )

    scored = score_job(candidate, job)

    assert scored["score"] <= 25
    assert scored["verdict"] == "skip"
    assert scored["matching_skills"] == []
    assert any("non-technical commercial/business role" in reason for reason in scored["reasons"])


def test_no_technical_requirements_cannot_create_high_confidence_match() -> None:
    candidate = profile()
    candidate.seniority_levels = []
    job = Job(
        source="test",
        external_id="12",
        title="AI Developer",
        company="Example",
        location="Remote",
        remote_region="Worldwide",
        description="Join our AI product company and work with the team.",
        tags=["ai", "remote"],
        salary_min=None,
        salary_max=None,
        currency="USD",
        url="https://example.com/job12",
    )

    scored = score_job(candidate, job)

    assert scored["score"] <= 64
    assert scored["verdict"] != "apply"
    assert scored["matching_skills"] == []
    assert scored["skill_gaps"] == []
