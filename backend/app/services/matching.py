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
    "Laravel": ["laravel"],
    "Symfony": ["symfony"],
    "Composer": ["composer"],
    "PHPUnit": ["phpunit"],
    "Vue.js": ["vue.js", "vuejs", "vue js"],
    "Nuxt": ["nuxt", "nuxt.js", "nuxtjs"],
    "Shopify": ["shopify"],
    "Shopify Liquid": ["shopify liquid", "liquid template", "liquid templating"],
    "PlentyONE": ["plentyone", "plentymarkets", "plenty markets"],
    "Magento / Adobe Commerce": ["magento", "adobe commerce"],
    "WooCommerce": ["woocommerce"],
    "WordPress": ["wordpress"],
    "Shopware": ["shopware"],
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

SENIORITY_ALIASES: dict[str, list[str]] = {
    "intern": ["intern", "internship", "trainee"],
    "junior": ["junior", "jr.", "jr ", "entry level", "entry-level", "graduate"],
    "middle": ["middle", "mid-level", "mid level", "midweight", "intermediate"],
    "senior": ["senior", "sr.", "sr ", "staff", "principal"],
    "lead": ["lead", "tech lead", "technical lead", "team lead", "head of"],
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
    "web": [
        "web developer", "web-developer", "web entwickler", "web-entwickler",
        "frontend", "front-end", "php developer", "php entwickler",
        "laravel developer", "shopify developer", "e-commerce developer",
        "ecommerce developer",
    ],
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


def _canonical_for_profile_skill(skill: str) -> str | None:
    for canonical, aliases in SKILL_ALIASES.items():
        if _has_alias(skill, canonical) or any(_has_alias(skill, alias) for alias in aliases):
            return canonical
    return None


def _display_label_for_requirement(canonical: str, skills: list[str]) -> str:
    """Prefer the candidate's own skill label for a matched canonical requirement."""
    for skill in skills:
        if _canonical_for_profile_skill(skill) == canonical:
            return skill
    return canonical


def _unknown_profile_matches(skills: list[str], job_text: str) -> list[str]:
    """
    Preserve exact profile skills that are mentioned by the vacancy but are not
    represented by the canonical catalogue. These count as real overlap and
    keep the UI/scoring aligned without inventing gaps we cannot detect.
    """
    matched: list[str] = []
    for skill in skills:
        if _canonical_for_profile_skill(skill) is not None:
            continue
        if len(skill.strip()) >= 2 and _has_alias(job_text, skill):
            matched.append(skill)
    return list(dict.fromkeys(matched))


def _flatten_profile_evidence(value) -> list[str]:
    result: list[str] = []
    if isinstance(value, str):
        text = value.strip()
        if text:
            result.append(text)
    elif isinstance(value, list):
        for item in value:
            result.extend(_flatten_profile_evidence(item))
    elif isinstance(value, dict):
        for item in value.values():
            result.extend(_flatten_profile_evidence(item))
    return result


def _effective_profile_skills(profile: CandidateProfile) -> list[str]:
    values = [str(skill).strip() for skill in (profile.skills or []) if str(skill).strip()]
    ai_profile = profile.ai_profile or {}

    for skill in ai_profile.get("skills", []) or []:
        text = str(skill).strip()
        if text:
            values.append(text)

    for item in ai_profile.get("skill_evidence", []) or []:
        if isinstance(item, dict):
            text = str(item.get("skill") or "").strip()
            if text:
                values.append(text)

    return list(dict.fromkeys(values))


def _profile_evidence_text(profile: CandidateProfile, skills: list[str]) -> str:
    parts = [
        *skills,
        profile.headline or "",
        profile.summary or "",
        *(profile.target_roles or []),
        *_flatten_profile_evidence(profile.ai_profile or {}),
    ]
    return " | ".join(str(part) for part in parts if str(part).strip()).lower()


def _broad_capability_match(requirement: str, evidence_text: str) -> str | None:
    req = requirement.lower().strip()

    if "software engineering" in req or "software development" in req:
        markers = (
            "software engineer", "software developer", "software development",
            "python developer", "backend developer", "application developer",
        )
        if any(marker in evidence_text for marker in markers):
            return requirement

    if (
        "artificial intelligence" in req
        or req in {"ai", "ai development", "ai engineering"}
    ):
        markers = (
            "ai developer", "ai application", "ai automation", "llm", "rag",
            "langgraph", "ai agents", "openai", "generative ai", "genai",
        )
        if any(marker in evidence_text for marker in markers):
            return requirement

    if (
        ("testing" in req or "evaluat" in req or "adopt" in req)
        and ("ai tool" in req or "ai model" in req or "models" in req)
    ):
        markers = (
            "cursor", "codex", "chatgpt", "openai", "langgraph", "rag",
            "llm", "ai agents", "prompt engineering", "model evaluation",
            "ai-assisted", "ai assisted",
        )
        if sum(1 for marker in markers if marker in evidence_text) >= 2:
            return requirement

    if "open-source" in req or "open source" in req:
        if "ai" in req or "model" in req:
            markers = (
                "hugging face", "huggingface", "ollama", "llama", "mistral",
                "vllm", "open-source ai", "open source ai",
            )
            if any(marker in evidence_text for marker in markers):
                return requirement

    return None


def _match_requirement_to_profile(
    requirement: str,
    skills: list[str],
    evidence_text: str = "",
) -> str | None:
    requirement = requirement.strip()
    if not requirement:
        return None

    # Canonical/alias-aware comparison first.
    requirement_canonical = _canonical_for_profile_skill(requirement)
    if requirement_canonical:
        for skill in skills:
            if _canonical_for_profile_skill(skill) == requirement_canonical:
                return skill

    # Exact phrase overlap for technologies not in our catalogue.
    for skill in skills:
        if _has_alias(skill, requirement) or _has_alias(requirement, skill):
            return skill

    # Conservative token overlap for variants such as "REST API development"
    # versus "REST APIs". Require at least one non-generic technical token.
    req_tokens = _tokens(requirement)
    for skill in skills:
        skill_tokens = _tokens(skill)
        overlap = req_tokens & skill_tokens
        if overlap and (len(overlap) >= 2 or any(len(token) >= 5 for token in overlap)):
            return skill
    broad_match = _broad_capability_match(requirement, evidence_text)
    if broad_match:
        return broad_match

    return None


def _requirement_key(value: str) -> str:
    canonical = _canonical_for_profile_skill(value)
    if canonical:
        return canonical.lower()
    return re.sub(r"[^a-z0-9+#.]+", " ", value.lower()).strip()


def _unique_requirements(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = _requirement_key(value)
        if value and key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _ai_requirement_sets(
    job: Job,
    skills: list[str],
    evidence_text: str = "",
) -> tuple[list[str], list[str], list[str], list[str]]:
    analysis = job.ai_analysis or {}
    if not analysis.get("ai_enriched") or analysis.get("analysis_version") != 4:
        return [], [], [], []

    must = [str(item).strip() for item in analysis.get("must_have_skills", []) if str(item).strip()]
    nice = [str(item).strip() for item in analysis.get("nice_to_have_skills", []) if str(item).strip()]
    matched_must: list[str] = []
    missing_must: list[str] = []
    matched_nice: list[str] = []
    missing_nice: list[str] = []

    for requirement in must:
        matched = _match_requirement_to_profile(requirement, skills, evidence_text)
        if matched:
            matched_must.append(matched)
        else:
            missing_must.append(requirement)

    for requirement in nice:
        matched = _match_requirement_to_profile(requirement, skills, evidence_text)
        if matched:
            matched_nice.append(matched)
        else:
            missing_nice.append(requirement)

    return (
        list(dict.fromkeys(matched_must + matched_nice)),
        list(dict.fromkeys(missing_must + missing_nice)),
        list(dict.fromkeys(matched_must)),
        list(dict.fromkeys(missing_must)),
    )


def _role_families_for_text(value: str) -> set[str]:
    value_lower = value.lower()
    families = {
        family
        for family, markers in ROLE_FAMILIES.items()
        if any(marker in value_lower for marker in markers)
    }

    # Real vacancy titles often insert words between the family marker and the
    # role noun: "AI Software Engineer", "Generative AI Backend Engineer",
    # "Python AI Developer", etc. Phrase-only matching misses these.
    tokens = _tokens(value_lower)
    if (
        {"ai", "llm", "genai"} & tokens
        or "artificial intelligence" in value_lower
        or "generative ai" in value_lower
        or "rag " in value_lower
        or value_lower.startswith("rag")
        or "agentic" in value_lower
    ):
        families.add("ai")
    if "python" in tokens:
        families.add("python")
    if "backend" in tokens or "back-end" in value_lower:
        families.add("backend")
    if "software" in tokens and ({"engineer", "developer"} & tokens):
        families.add("software")
    if ("machine" in tokens and "learning" in tokens) or "ml" in tokens:
        families.add("ml")
    if (
        ("web" in tokens and ({"developer", "entwickler"} & tokens))
        or "frontend" in tokens
        or "front-end" in value_lower
        or "laravel" in tokens
        or "shopify" in tokens
    ):
        families.add("web")

    return families


def _role_score(target_roles: list[str], title: str) -> tuple[float, str | None]:
    title_lower = title.lower()
    targets = [role.lower() for role in target_roles if role]

    if any(target in title_lower for target in targets):
        return 35.0, "Target role directly matches the vacancy title."

    candidate_families = _role_families_for_text(" ".join(targets))
    job_families = _role_families_for_text(title_lower)

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


def _detected_seniority(title: str, tags: list[str]) -> str | None:
    haystack = " ".join([title, *[str(tag) for tag in tags]]).lower()
    for level, aliases in SENIORITY_ALIASES.items():
        if any(_has_alias(haystack, alias) for alias in aliases):
            return level
    return None


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

    skills = _effective_profile_skills(profile)
    evidence_text = _profile_evidence_text(profile, skills)
    active_ai_analysis = job.ai_analysis if ((job.ai_analysis or {}).get("ai_enriched") and (job.ai_analysis or {}).get("analysis_version") == 4) else {}
    candidate_keys = _candidate_skill_keys(skills)
    required_keys = _job_skill_keys(job_text)
    matched_keys = candidate_keys & required_keys

    ai_matching, ai_gaps, ai_matched_must, ai_missing_must = _ai_requirement_sets(
        job,
        skills,
        evidence_text,
    )

    deterministic_matching = [
        _display_label_for_requirement(key, skills)
        for key in _ordered_skills(matched_keys)
    ]
    deterministic_matching.extend(_unknown_profile_matches(skills, job_text))
    deterministic_matching = _unique_requirements(deterministic_matching)
    deterministic_gaps = _unique_requirements(_ordered_skills(required_keys - candidate_keys))

    if active_ai_analysis and (ai_matching or ai_gaps):
        # Merge both sources instead of letting the LLM replace explicit text
        # detection. AI catches uncommon technologies; deterministic matching
        # catches explicit stack items the model may omit.
        matching = _unique_requirements(ai_matching + deterministic_matching)
        matched_requirement_keys = {_requirement_key(value) for value in matching}
        gaps = [
            value
            for value in _unique_requirements(ai_gaps + deterministic_gaps)
            if _requirement_key(value) not in matched_requirement_keys
        ]
        requirement_source = "hybrid_ai"
    else:
        matching = deterministic_matching
        gaps = deterministic_gaps
        requirement_source = "deterministic"

    detected_requirement_count = len(matching) + len(gaps)

    excluded = [word for word in (profile.exclude_keywords or []) if word.lower() in job_text]

    score = 0.0
    reasons: list[str] = []

    role_points, role_reason = _role_score(profile.target_roles or [], job.title)
    candidate_role_families = _role_families_for_text(" ".join(profile.target_roles or []))
    job_role_families = _role_families_for_text(job.title)

    ai_role_family = str(active_ai_analysis.get("role_family") or "").lower()
    if ai_role_family and ai_role_family != "other":
        job_role_families.add(ai_role_family)
        if ai_role_family in candidate_role_families:
            role_points = max(role_points, 33.0 if ai_role_family == "ai" else 29.0)
            role_reason = "AI vacancy analysis confirms the role family matches your targets."

    score += role_points
    if role_reason:
        reasons.append(role_reason)

    role_relevant = role_points >= 15.0
    compatible_adjacent = (
        "ai" in candidate_role_families
        and bool(job_role_families & {"python", "backend", "software", "ml"})
    )
    role_family_mismatch = bool(
        candidate_role_families
        and job_role_families
        and not (candidate_role_families & job_role_families)
        and not compatible_adjacent
    )

    selected_seniority = {level.lower() for level in (profile.seniority_levels or [])}
    detected_seniority = str(active_ai_analysis.get("seniority") or "").lower() or _detected_seniority(job.title, job.tags or [])
    seniority_mismatch = False
    if selected_seniority and detected_seniority:
        if detected_seniority in selected_seniority:
            score += 7.0
            reasons.append(
                f"The vacancy seniority ({detected_seniority}) matches your selected level."
            )
        else:
            seniority_mismatch = True
            reasons.append(
                f"The vacancy seniority ({detected_seniority}) is outside your selected levels."
            )

    if detected_requirement_count:
        if requirement_source == "hybrid_ai":
            analysis = active_ai_analysis
            must = [str(item).strip() for item in (analysis.get("must_have_skills", []) or []) if str(item).strip()]
            nice = [str(item).strip() for item in (analysis.get("nice_to_have_skills", []) or []) if str(item).strip()]

            matched_must_count = sum(1 for requirement in must if _match_requirement_to_profile(requirement, skills, evidence_text))
            matched_nice_count = sum(1 for requirement in nice if _match_requirement_to_profile(requirement, skills, evidence_text))

            ai_requirement_keys = {
                _requirement_key(requirement)
                for requirement in must + nice
                if _requirement_key(requirement)
            }
            deterministic_requirements = _unique_requirements(
                deterministic_matching + deterministic_gaps
            )
            deterministic_extras = [
                requirement
                for requirement in deterministic_requirements
                if _requirement_key(requirement) not in ai_requirement_keys
            ]
            matched_keys_display = {_requirement_key(value) for value in matching}
            matched_extra_count = sum(
                1
                for requirement in deterministic_extras
                if _requirement_key(requirement) in matched_keys_display
            )

            # Must-have requirements matter most, while explicit technologies
            # found directly in the vacancy text still count even if AI omitted them.
            total_weight = (4 * len(must)) + len(nice) + (2 * len(deterministic_extras))
            matched_weight = (
                (4 * matched_must_count)
                + matched_nice_count
                + (2 * matched_extra_count)
            )
            skill_points = 40.0 * (matched_weight / total_weight) if total_weight else 20.0
            score += skill_points
            reasons.append(
                f"Hybrid analysis found {detected_requirement_count} technical requirements; "
                f"you match {len(matching)}."
            )
            if ai_missing_must:
                reasons.append(
                    "Missing must-have skills: " + ", ".join(ai_missing_must[:6])
                )
        else:
            coverage = len(matching) / detected_requirement_count
            skill_points = 40.0 * coverage
            score += skill_points
            reasons.append(
                f"You match {len(matching)} of {detected_requirement_count} detected technical requirements."
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

    if role_family_mismatch:
        score = min(score, 39.0)
        reasons.append("The vacancy role family is outside your selected target roles.")
    elif not role_relevant and len(matching) < 2:
        score = min(score, 35.0)
        reasons.append("The vacancy title is outside your target role families.")

    # Selected seniority is a search constraint, not a soft preference.
    # Example: Junior + Middle must not surface Senior / Staff / Principal roles.
    if seniority_mismatch:
        score = min(score, 39.0)

    score = max(0.0, min(100.0, round(score, 1)))
    verdict = "apply" if score >= 75 else "maybe" if score >= 55 else "skip"

    return {
        "score": score,
        "matching_skills": matching[:40],
        "skill_gaps": gaps[:30],
        "reasons": reasons[:8],
        "verdict": verdict,
    }
