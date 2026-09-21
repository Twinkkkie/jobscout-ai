# JobScout AI architecture

JobScout uses a hybrid AI architecture. LLMs extract meaning and generate language;
deterministic code keeps scores, filters, permissions, and user constraints predictable.

## AI services

### Resume AI Analyzer
- Reads uploaded PDF/DOCX/TXT resume text.
- Extracts roles, skills, commercial years, domains, achievements, and skill evidence.
- Distinguishes commercial, project, academic, and merely-mentioned experience.
- Falls back to the deterministic parser when no AI provider is configured or unavailable.

### Vacancy AI Analyzer
- Extracts role family, seniority, must-have skills, nice-to-have skills, experience,
  responsibilities, domain, language requirements, remote policy, and location restrictions.
- Vacancy analysis is persisted so the same vacancy does not need to be analyzed for every user.
- Manual scans first use cheap deterministic relevance and spend LLM calls only on promising jobs.

### Hybrid Match Engine
- AI extracts requirements.
- Python calculates the score and enforces hard constraints.
- Must-have requirements have more weight than nice-to-have requirements.
- Selected seniority is a hard search constraint.
- Role-family, remote, experience, salary, and exclude-keyword checks remain deterministic.
- If no AI analysis exists, the expanded deterministic technology matcher is used.

### AI Match Explanation
- Generated only when a user explicitly opens/runs Match analysis.
- Explains strengths, gaps, transferable skills, and application advice.
- Does not decide the score.

## Agents

### 1. Job Scout Agent
Workflow:

```
collect public jobs
  -> verify availability
  -> deterministic prefilter
  -> AI-analyze promising vacancies
  -> hybrid rematch
```

The agent avoids spending LLM calls on obviously irrelevant vacancies.

### 2. Application Agent
Workflow:

```
analyze vacancy
  -> calculate hybrid match
  -> generate tailored application pack
  -> fact-check claims against resume/profile
  -> human review required
```

Outputs:
- tailored resume summary
- 260-340 word cover letter
- recruiter message
- interview talking points
- caution notes about claims/skills not to overstate

The agent never auto-submits applications.

### 3. Career Agent
Workflow:

```
aggregate match/application history
  -> identify recurring gaps and strongest skills
  -> synthesize next actions
```

It uses only evidence stored in JobScout and does not invent labor-market statistics.

## Agent runtime

LangGraph is the intended orchestration runtime. The code also has a sequential fallback so
local development does not fail if LangGraph has not yet been installed in an older Docker image.

After rebuilding the backend image with current dependencies, agents run through LangGraph.

## Safety and reliability

- Vacancy and resume text are treated as untrusted input in AI prompts.
- External AI failures fall back to deterministic behavior.
- API keys are read from environment variables and are never returned by the API.
- Match scores are not delegated to the LLM.
- Human review is required before any application content is sent.
