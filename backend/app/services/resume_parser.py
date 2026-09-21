import io
import re
from pathlib import Path

from docx import Document
from pypdf import PdfReader

KNOWN_SKILLS = [
    "Python", "FastAPI", "Django", "Flask", "PostgreSQL", "MySQL", "SQL",
    "SQLAlchemy", "Alembic", "Docker", "Kubernetes", "Redis", "RabbitMQ",
    "Celery", "Git", "GitHub Actions", "PyQt", "C++", "JavaScript",
    "TypeScript", "React", "Next.js", "AWS", "Azure", "GCP", "LangGraph",
    "RAG", "pgvector", "OpenAI", "LLM", "REST", "pytest", "Linux",
]

ROLE_HINTS = {
    "backend": "Backend Developer",
    "python developer": "Python Developer",
    "python-разработ": "Python Developer",
    "ai developer": "AI Developer",
    "ai engineer": "AI Engineer",
    "machine learning": "Machine Learning Engineer",
    "frontend": "Frontend Developer",
    "full stack": "Full-stack Developer",
}


class UnsupportedResume(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if suffix == ".docx":
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs).strip()
    if suffix in {".txt", ".md"}:
        return data.decode("utf-8", errors="replace").strip()
    raise UnsupportedResume("Supported resume formats: PDF, DOCX, TXT")


def infer_profile(text: str) -> dict:
    lower = text.lower()
    skills = [skill for skill in KNOWN_SKILLS if skill.lower() in lower]

    roles: list[str] = []
    for needle, role in ROLE_HINTS.items():
        if needle in lower and role not in roles:
            roles.append(role)

    years = 0
    year_candidates = [
        int(value)
        for value in re.findall(r"(?<!\d)(\d{1,2})\+?\s*(?:years?|лет)", lower)
        if int(value) <= 40
    ]
    if year_candidates:
        years = max(year_candidates)

    summary_parts = []
    if roles:
        summary_parts.append(", ".join(roles[:3]))
    if skills:
        summary_parts.append("Skills: " + ", ".join(skills[:12]))

    return {
        "skills": skills,
        "target_roles": roles,
        "years_experience": years,
        "summary": ". ".join(summary_parts),
    }
