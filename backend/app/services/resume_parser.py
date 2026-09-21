import io
import re
from pathlib import Path

from docx import Document
from pypdf import PdfReader

# Deterministic skill catalogue used when an external LLM is not configured.
# Keep canonical display names here and aliases/patterns below.
SKILL_PATTERNS: dict[str, list[str]] = {
    "Python": [r"\bpython\b"],
    "FastAPI": [r"\bfastapi\b"],
    "Django": [r"\bdjango\b"],
    "Flask": [r"\bflask\b"],
    "PostgreSQL": [r"\bpostgresql\b", r"\bpostgres\b"],
    "MySQL": [r"\bmysql\b"],
    "SQL": [r"(?<![a-z])sql(?![a-z])"],
    "SQLAlchemy": [r"\bsqlalchemy\b"],
    "Alembic": [r"\balembic\b"],
    "REST APIs": [r"\brest\s*apis?\b", r"\brestful\b"],
    "Pydantic": [r"\bpydantic\b"],
    "asyncio": [r"\basyncio\b", r"\basync\s+python\b"],
    "Docker": [r"\bdocker\b"],
    "Docker Compose": [r"\bdocker\s+compose\b"],
    "Kubernetes": [r"\bkubernetes\b", r"\bk8s\b"],
    "Redis": [r"\bredis\b"],
    "RabbitMQ": [r"\brabbitmq\b"],
    "Celery": [r"\bcelery\b"],
    "Git": [r"(?<![a-z])git(?![a-z])"],
    "GitHub": [r"\bgithub\b"],
    "GitHub Actions": [r"\bgithub\s+actions\b"],
    "pytest": [r"\bpytest\b"],
    "Prometheus": [r"\bprometheus\b"],
    "PyQt": [r"\bpyqt\d*\b"],
    "C": [r"(?<![a-z0-9+#])c(?![a-z0-9+#])"],
    "C++": [r"(?<![a-z0-9])c\+\+(?![a-z0-9])"],
    "JavaScript": [r"\bjavascript\b", r"\bjs\b"],
    "TypeScript": [r"\btypescript\b"],
    "React": [r"\breact\b"],
    "Next.js": [r"\bnext\.js\b", r"\bnextjs\b"],
    "HTML": [r"\bhtml\b"],
    "CSS": [r"\bcss\b"],
    "PHP": [r"\bphp\b"],
    "Tilda": [r"\btilda\b"],
    "AWS": [r"\baws\b", r"\bamazon\s+web\s+services\b"],
    "Azure": [r"\bazure\b"],
    "GCP": [r"\bgcp\b", r"\bgoogle\s+cloud\b"],
    "Linux": [r"\blinux\b"],
    "LangGraph": [r"\blanggraph\b"],
    "RAG": [r"(?<![a-z])rag(?![a-z])", r"retrieval[- ]augmented\s+generation"],
    "pgvector": [r"\bpgvector\b"],
    "OpenAI API": [r"\bopenai\s+api\b", r"\bopenai\b"],
    "LLM Integration": [r"\bllm\s+integration\b", r"\bllm\s+integrations\b"],
    "LLM": [r"(?<![a-z])llms?(?![a-z])"],
    "AI Agents": [r"\bai\s+agents?\b", r"\bagentic\b"],
    "RAG Systems": [r"\brag\s+systems?\b"],
    "Embeddings": [r"\bembeddings?\b"],
    "Vector Search": [r"\bvector\s+search\b", r"\bsemantic\s+search\b"],
    "Human-in-the-Loop AI": [r"\bhuman[- ]in[- ]the[- ]loop\b"],
    "AI Automation": [r"\bai\s+automation\b"],
    "Prompt Engineering": [r"\bprompt\s+engineering\b"],
    "AI-assisted Development": [r"\bai[- ]assisted\s+development\b"],
    "ChatGPT": [r"\bchatgpt\b"],
    "Claude": [r"\bclaude\b"],
    "Cursor": [r"\bcursor\b"],
    "Codex": [r"\bcodex\b"],
    "Siemens TIA Portal": [r"\btia\s+portal\b", r"\bsiemens\s+tia\b"],
    "LAD": [r"(?<![a-z])lad(?![a-z])"],
    "FBD": [r"(?<![a-z])fbd(?![a-z])"],
    "STL": [r"(?<![a-z])stl(?![a-z])"],
    "SCL": [r"(?<![a-z])scl(?![a-z])"],
    "Firmware Workflows": [r"\bfirmware[- ]related\s+workflows?\b", r"\bfirmware\s+workflows?\b"],
    "Serial Communication": [r"\bserial\s+communication\b"],
    "Code Generation": [r"\bcode\s+generation\b", r"automatic\s+generation\s+of\s+.*source\s+code"],
    "Documentation Generation": [r"\bdocumentation\s+generation\b", r"generation\s+of\s+.*documentation"],
    "SEO": [r"(?<![a-z])seo(?![a-z])"],
}

ROLE_HINTS = {
    "ai developer": "AI Developer",
    "ai application developer": "AI Application Developer",
    "ai automation developer": "AI Automation Developer",
    "ai engineer": "AI Engineer",
    "python developer": "Python Developer",
    "python-разработ": "Python Developer",
    "backend": "Backend Developer",
    "machine learning": "Machine Learning Engineer",
    "frontend": "Frontend Developer",
    "full stack": "Full-stack Developer",
}


class UnsupportedResume(ValueError):
    pass


def _docx_text(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    parts: list[str] = []

    # Normal paragraphs.
    parts.extend(p.text for p in doc.paragraphs if p.text.strip())

    # A lot of ATS resumes put the skills section in tables. python-docx does
    # not include table-cell text in doc.paragraphs, so read it explicitly.
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    if paragraph.text.strip():
                        parts.append(paragraph.text)

    return "\n".join(parts).strip()


def extract_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if suffix == ".docx":
        return _docx_text(data)
    if suffix in {".txt", ".md"}:
        return data.decode("utf-8", errors="replace").strip()
    raise UnsupportedResume("Supported resume formats: PDF, DOCX, TXT")


def _extract_skills(text: str) -> list[str]:
    lower = text.lower()
    found: list[str] = []
    for canonical, patterns in SKILL_PATTERNS.items():
        if any(re.search(pattern, lower, flags=re.IGNORECASE) for pattern in patterns):
            found.append(canonical)
    return found


def infer_profile(text: str) -> dict:
    lower = text.lower()
    skills = _extract_skills(text)

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
        summary_parts.append(", ".join(roles[:4]))
    if skills:
        summary_parts.append("Skills: " + ", ".join(skills[:20]))

    return {
        "skills": skills,
        "target_roles": roles,
        "years_experience": years,
        "summary": ". ".join(summary_parts),
    }
