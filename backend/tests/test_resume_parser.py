from app.services.resume_parser import infer_profile


def test_infer_profile_extracts_ai_backend_skills_and_roles() -> None:
    text = """
    AI-focused Python Developer with 3 years of commercial software development experience.
    Target roles: AI Developer, AI Automation Developer, Python Developer.
    Skills: Python, FastAPI, PostgreSQL, SQLAlchemy, Alembic, REST APIs, Pydantic,
    asyncio, Docker, Docker Compose, Redis, RabbitMQ, Celery, LangGraph, RAG,
    AI Agents, OpenAI API, Embeddings, Vector Search, pgvector,
    Human-in-the-Loop AI, Prompt Engineering, pytest, GitHub Actions,
    Prometheus, Kubernetes, PyQt, C, C++, JavaScript, HTML, CSS, PHP,
    Siemens TIA Portal, LAD, FBD, STL, SCL, ChatGPT, Claude, Cursor, Codex.
    """
    profile = infer_profile(text)

    expected = {
        "Python",
        "FastAPI",
        "PostgreSQL",
        "SQLAlchemy",
        "Alembic",
        "REST APIs",
        "Pydantic",
        "asyncio",
        "Docker",
        "Docker Compose",
        "Redis",
        "RabbitMQ",
        "Celery",
        "LangGraph",
        "RAG",
        "AI Agents",
        "OpenAI API",
        "Embeddings",
        "Vector Search",
        "pgvector",
        "Human-in-the-Loop AI",
        "Prompt Engineering",
        "pytest",
        "GitHub Actions",
        "Prometheus",
        "Kubernetes",
        "PyQt",
        "C",
        "C++",
        "JavaScript",
        "HTML",
        "CSS",
        "PHP",
        "Siemens TIA Portal",
        "LAD",
        "FBD",
        "STL",
        "SCL",
        "ChatGPT",
        "Claude",
        "Cursor",
        "Codex",
    }
    assert expected.issubset(set(profile["skills"]))
    assert "AI Developer" in profile["target_roles"]
    assert "Python Developer" in profile["target_roles"]
    assert profile["years_experience"] == 3
