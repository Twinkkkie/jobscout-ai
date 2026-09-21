import re

from app.models import CandidateProfile, Job

STOPWORDS = {
    "and", "the", "with", "for", "you", "your", "our", "are", "will", "from",
    "this", "that", "have", "has", "job", "role", "work", "team", "remote",
}

# Broad, explicit technology vocabulary used by the deterministic matcher.
# The matcher also checks every skill from the candidate profile directly, so
# profile skills are not limited to this catalogue.
SKILL_ALIASES: dict[str, list[str]] = {
    # Python / backend
    "Python": ["python"],
    "FastAPI": ["fastapi"],
    "Django": ["django"],
    "Flask": ["flask"],
    "Starlette": ["starlette"],
    "Pydantic": ["pydantic"],
    "asyncio": ["asyncio", "async python", "asynchronous python"],
    "SQLAlchemy": ["sqlalchemy"],
    "Alembic": ["alembic"],
    "REST APIs": ["rest api", "restful api", "restful services"],
    "GraphQL": ["graphql"],
    "gRPC": ["grpc"],
    "WebSockets": ["websocket", "websockets"],
    "Webhooks": ["webhook", "webhooks"],
    "API Integration": ["api integration", "third-party api", "third party api"],
    "Microservices": ["microservices", "microservice architecture"],
    "Distributed Systems": ["distributed systems", "distributed system"],
    # Languages / frameworks
    "JavaScript": ["javascript"],
    "TypeScript": ["typescript"],
    "React": ["react", "react.js", "reactjs"],
    "Next.js": ["next.js", "nextjs"],
    "Node.js": ["node.js", "nodejs"],
    "HTML": ["html"],
    "CSS": ["css"],
    "PHP": ["php"],
    "Java": ["java"],
    "Spring Boot": ["spring boot", "springboot"],
    "Kotlin": ["kotlin"],
    "Go": ["golang", "go language"],
    "Rust": ["rust"],
    "C": ["c language"],
    "C++": ["c++"],
    "C#": ["c#", "c sharp"],
    ".NET": [".net", "dotnet"],
    # Databases / search
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "SQLite": ["sqlite"],
    "SQL": ["sql"],
    "MongoDB": ["mongodb", "mongo db"],
    "DynamoDB": ["dynamodb"],
    "Redis": ["redis"],
    "Elasticsearch": ["elasticsearch", "elastic search"],
    "OpenSearch": ["opensearch"],
    "ClickHouse": ["clickhouse"],
    "Snowflake": ["snowflake"],
    "BigQuery": ["bigquery", "big query"],
    "Supabase": ["supabase"],
    # Queues / workflow
    "Celery": ["celery"],
    "RabbitMQ": ["rabbitmq", "rabbit mq"],
    "Kafka": ["kafka", "apache kafka"],
    "SQS": ["amazon sqs", "aws sqs"],
    "Airflow": ["airflow", "apache airflow"],
    "Temporal": ["temporal.io", "temporal workflow"],
    # Infra / cloud
    "Docker": ["docker"],
    "Docker Compose": ["docker compose", "docker-compose"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Helm": ["helm"],
    "Terraform": ["terraform"],
    "Ansible": ["ansible"],
    "Linux": ["linux"],
    "Nginx": ["nginx"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"],
    "GCP": ["gcp", "google cloud platform", "google cloud"],
    "AWS Lambda": ["aws lambda", "lambda functions"],
    "ECS": ["amazon ecs", "aws ecs"],
    "EKS": ["amazon eks", "aws eks"],
    "Cloud Run": ["cloud run"],
    "Vertex AI": ["vertex ai"],
    "Azure OpenAI": ["azure openai"],
    "Amazon Bedrock": ["amazon bedrock", "aws bedrock"],
    # DevEx / observability / security
    "Git": ["git"],
    "GitHub": ["github"],
    "GitLab": ["gitlab"],
    "GitHub Actions": ["github actions"],
    "GitLab CI": ["gitlab ci", "gitlab-ci"],
    "CI/CD": ["ci/cd", "continuous integration", "continuous delivery", "continuous deployment"],
    "pytest": ["pytest"],
    "Unit Testing": ["unit testing", "unit tests"],
    "Integration Testing": ["integration testing", "integration tests"],
    "Prometheus": ["prometheus"],
    "Grafana": ["grafana"],
    "OpenTelemetry": ["opentelemetry", "open telemetry"],
    "Sentry": ["sentry"],
    "OAuth": ["oauth", "oauth2", "oauth 2.0"],
    "JWT": ["jwt", "json web token"],
    "RBAC": ["rbac", "role-based access control", "role based access control"],
    # AI / LLM
    "LLM": ["llm", "llms", "large language model", "large language models"],
    "Generative AI": ["generative ai", "genai"],
    "OpenAI API": ["openai api", "openai"],
    "Anthropic / Claude API": ["anthropic", "claude api", "claude sdk"],
    "Gemini API": ["gemini api", "google gemini"],
    "Mistral": ["mistral ai", "mistral models"],
    "Llama": ["llama model", "llama models", "llama 3"],
    "LangGraph": ["langgraph"],
    "LangChain": ["langchain"],
    "LlamaIndex": ["llamaindex", "llama index"],
    "CrewAI": ["crewai"],
    "AutoGen": ["autogen"],
    "AI Agents": ["ai agent", "ai agents", "agentic ai", "agentic workflow", "agentic workflows"],
    "Tool Calling": ["tool calling", "function calling", "function-calling"],
    "Structured Outputs": ["structured output", "structured outputs"],
    "RAG": ["rag", "retrieval-augmented generation", "retrieval augmented generation"],
    "Embeddings": ["embedding", "embeddings", "text embeddings"],
    "Vector Search": ["vector search", "semantic search", "similarity search"],
    "Vector Databases": ["vector database", "vector databases", "vector db"],
    "pgvector": ["pgvector"],
    "Pinecone": ["pinecone"],
    "Qdrant": ["qdrant"],
    "Weaviate": ["weaviate"],
    "FAISS": ["faiss"],
    "Chroma": ["chromadb", "chroma db", "chroma"],
    "Prompt Engineering": ["prompt engineering", "prompt design"],
    "Prompt Evaluation": ["prompt evaluation", "prompt evals"],
    "LLM Evaluation": ["llm evaluation", "llm eval", "llm evals", "model evaluation"],
    "Fine-tuning": ["fine-tuning", "fine tuning", "finetuning"],
    "LoRA / PEFT": ["lora", "peft"],
    "Human-in-the-Loop AI": ["human-in-the-loop", "human in the loop", "hitl"],
    "AI Automation": ["ai automation", "ai-powered automation", "intelligent automation"],
    "MCP": ["model context protocol", "mcp"],
    "Transformers": ["transformers", "transformer models"],
    "Hugging Face": ["hugging face", "huggingface"],
    "PyTorch": ["pytorch"],
    "TensorFlow": ["tensorflow"],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "Machine Learning": ["machine learning"],
    "Deep Learning": ["deep learning"],
    "NLP": ["natural language processing", "nlp"],
    "Computer Vision": ["computer vision"],
    "Multimodal AI": ["multimodal", "multi-modal"],
    "OCR": ["ocr", "optical character recognition"],
    "Speech / TTS": ["text-to-speech", "text to speech", "tts", "speech synthesis"],
    "vLLM": ["vllm"],
    "Ollama": ["ollama"],
    "MLflow": ["mlflow"],
    "Weights & Biases": ["weights & biases", "wandb"],
    # Data
    "pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Jupyter": ["jupyter"],
    "Spark": ["apache spark", "pyspark"],
    "dbt": ["dbt"],
    # Desktop / engineering
    "PyQt": ["pyqt", "pyqt5", "pyqt6"],
    "Siemens TIA Portal": ["tia portal", "siemens tia portal"],
    "LAD": ["lad"],
    "FBD": ["fbd"],
    "STL": ["stl"],
    "SCL": ["scl"],
    "Serial Communication": ["serial communication", "serial port", "rs-232", "rs232"],
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

GENERIC_TAGS = {
    "remote", "engineering", "software", "developer", "development", "programming",
    "technology", "tech", "full-time", "full time", "contract", "freelance",
    "senior", "junior", "mid", "mid-level", "worldwide", "europe", "emea",
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.\-]{1,30}", value.lower())
        if token not in STOPWORDS
    }


def _has_alias(text: str, alias: str) -> bool:
    escaped = re.escape(alias.lower().strip())
    if not escaped:
        return False
    pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def _candidate_skill_keys(skills: list[str]) -> set[str]:
    text = " | ".join(skills)
    found: set[str] = set()
    for canonical, aliases in SKILL_ALIASES.items():
        if _has_alias(text, canonical) or any(_has_alias(text, alias) for alias in aliases):
            found.add(canonical)
    return found


def _job_skill_keys(job_text: str) -> set[str]:
    found: set[str] = set()
    for canonical, aliases in SKILL_ALIASES.items():
        if any(_has_alias(job_text, alias) for alias in aliases):
            found.add(canonical)
    return found


def _direct_profile_matches(skills: list[str], job_text: str) -> list[str]:
    """Match every profile skill directly, even if it is not in the catalogue."""
    matched: list[str] = []
    for skill in skills:
        if len(skill.strip()) < 2:
            continue
        if _has_alias(job_text, skill):
            matched.append(skill)
            continue
        # If the profile skill maps to a canonical entry, honor its aliases.
        for canonical, aliases in SKILL_ALIASES.items():
            if _has_alias(skill, canonical) or any(_has_alias(skill, alias) for alias in aliases):
                if any(_has_alias(job_text, alias) for alias in aliases):
                    matched.append(skill)
                    break
    return list(dict.fromkeys(matched))


def _tag_requirements(tags: list[str], candidate_skills: list[str]) -> tuple[list[str], list[str]]:
    """Use source tags as additional explicit evidence instead of discarding them."""
    candidate_text = " | ".join(candidate_skills)
    matched: list[str] = []
    gaps: list[str] = []

    for raw in tags:
        tag = re.sub(r"\s+", " ", str(raw)).strip()
        if not tag or len(tag) > 40 or tag.lower() in GENERIC_TAGS:
            continue

        canonical = None
        for name, aliases in SKILL_ALIASES.items():
            if _has_alias(tag, name) or any(_has_alias(tag, alias) for alias in aliases):
                canonical = name
                break

        requirement = canonical or tag
        if _has_alias(candidate_text, requirement) or (
            canonical and any(_has_alias(candidate_text, alias) for alias in SKILL_ALIASES[canonical])
        ):
            matched.append(requirement)
        elif canonical:
            gaps.append(requirement)

    return list(dict.fromkeys(matched)), list(dict.fromkeys(gaps))


def _ordered_skills(keys: set[str]) -> list[str]:
    return [canonical for canonical in SKILL_ALIASES if canonical in keys]


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

    generic_role_tokens = {
        "developer", "engineer", "software", "senior", "junior", "lead",
        "specialist", "manager", "application", "applications",
    }
    title_tokens = _tokens(title) - generic_role_tokens
    target_tokens = _tokens(" ".join(target_roles)) - generic_role_tokens
    overlap = title_tokens & target_tokens
    if overlap:
        return 20.0, "The vacancy title overlaps with your target-role keywords."

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

    catalogue_matches = _ordered_skills(matched_keys)
    direct_matches = _direct_profile_matches(skills, job_text)
    tag_matches, tag_gaps = _tag_requirements(job.tags or [], skills)

    matching = list(dict.fromkeys(direct_matches + catalogue_matches + tag_matches))
    gaps = list(
        dict.fromkeys(_ordered_skills(required_keys - candidate_keys) + tag_gaps)
    )

    excluded = [word for word in (profile.exclude_keywords or []) if word.lower() in job_text]

    score = 0.0
    reasons: list[str] = []

    role_points, role_reason = _role_score(profile.target_roles or [], job.title)
    score += role_points
    if role_reason:
        reasons.append(role_reason)

    role_relevant = role_points >= 15.0

    if required_keys:
        coverage = len(matched_keys) / len(required_keys)
        skill_points = 40.0 * coverage
        score += skill_points
        reasons.append(
            f"You match {len(matched_keys)} of {len(required_keys)} detected technical requirements."
        )
    else:
        score += 20.0
        reasons.append(
            "The source provides too few explicit technical requirements for a complete gap analysis."
        )

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

    if not role_relevant and len(matched_keys) < 2:
        score = min(score, 35.0)
        reasons.append("The vacancy title is outside your target role families.")

    score = max(0.0, min(100.0, round(score, 1)))
    verdict = "apply" if score >= 75 else "maybe" if score >= 55 else "skip"

    return {
        "score": score,
        "matching_skills": matching[:40],
        "skill_gaps": gaps[:30],
        "reasons": reasons[:8],
        "verdict": verdict,
    }
