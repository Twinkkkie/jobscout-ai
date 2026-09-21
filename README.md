# JobScout AI

JobScout AI is a bilingual (English/Russian), multi-user AI job-search SaaS focused on international remote work.

It combines job aggregation, resume parsing, personal search preferences, AI-assisted matching, gap analysis, application tracking, and mobile-first/PWA UX in one product.

## Current MVP

- Email/password registration and JWT authentication
- Multi-user data isolation
- Candidate profile and job-search preferences
- PDF/DOCX resume upload and parsing
- Remote job collection from public feeds that allow aggregation/attribution
- Personalized match score and skill-gap explanation
- Saved/applied/interview/offer/rejected tracking
- Background job collection with Celery + Redis
- PostgreSQL persistence
- English/Russian UI
- Responsive desktop/mobile design
- Installable PWA for iPhone/Android
- Capacitor configuration ready for a future native iOS/App Store build
- Docker Compose local environment
- GitHub Actions CI

## iPhone

The web app is built as a PWA. On iPhone: open the deployed site in Safari → Share → **Add to Home Screen**. It launches like an app with its own icon and standalone window.

A native App Store build is also prepared through Capacitor. Publishing to the App Store later requires an Apple Developer account and Xcode/macOS for signing.

## Job-source policy

The project only enables sources whose public feeds/API terms allow this usage and keeps source attribution + original apply links. Sources that require a commercial/private license for a multi-user product are not enabled by default.

## Quick start

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Frontend: http://localhost:5173  
API docs: http://localhost:8030/docs

## Stack

**Backend:** Python 3.12, FastAPI, PostgreSQL, SQLAlchemy, Redis, Celery, JWT  
**Frontend:** React, TypeScript, Vite, PWA, responsive CSS, i18n  
**AI:** profile extraction/matching architecture with deterministic fallback and optional LLM provider  
**Infra:** Docker Compose, pytest, GitHub Actions


## Vacancy freshness

Each scan adds newly discovered vacancies, refreshes existing ones, and re-checks recent/saved vacancy links. Confirmed closed listings (HTTP 404/410 or strong closed-position markers) are hidden from Jobs and Matches. Saved vacancies remain in the tracker with a visible closed status so application history is not silently lost. Network errors, rate limits and anti-bot responses are treated as uncertain rather than closed to avoid false positives.


## AI agents

JobScout now has three agent workflows:

- **Job Scout Agent** — collects jobs, checks availability, selectively analyzes promising vacancies with AI, and rebuilds hybrid matches.
- **Application Agent** — analyzes a vacancy, calculates the hybrid match, creates a tailored application pack, fact-checks claims, and hands the result to the user for review.
- **Career Agent** — analyzes match/application history to surface recurring skill gaps, strongest skills, and next actions.

The intended orchestration runtime is **LangGraph**. A sequential fallback keeps local development working when an older Docker image has not yet installed LangGraph.

The AI layer also includes:
- structured resume analysis,
- structured vacancy requirement extraction,
- hybrid deterministic+AI matching,
- on-demand AI match explanations,
- richer application packs.

See `docs/AI_ARCHITECTURE.md` for the architecture and guardrails.

### Enabling AI locally

Set `OPENAI_API_KEY` in the local `.env` file. Never commit the real key.

`GET /api/v1/agents/status` reports whether an AI key is configured and whether LangGraph is available, without exposing secrets.
