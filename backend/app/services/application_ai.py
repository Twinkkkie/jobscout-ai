from openai import AsyncOpenAI

from app.core.config import settings
from app.models import CandidateProfile, Job


def _fallback(profile: CandidateProfile, job: Job) -> tuple[str, str]:
    skills = ", ".join((profile.skills or [])[:8])
    summary = (
        f"Candidate targeting {job.title} with {profile.years_experience} years of experience. "
        f"Relevant skills include {skills or 'software development and automation'}."
    )
    letter = (
        f"I am interested in the {job.title} role at {job.company}. "
        f"My background includes {skills or 'Python development, automation and backend work'}. "
        "The position aligns with my focus on building practical software and AI-powered solutions. "
        "I would welcome the opportunity to discuss how my experience could contribute to the team."
    )
    return summary, letter


async def prepare_application(profile: CandidateProfile, job: Job) -> tuple[str, str]:
    if not settings.openai_api_key:
        return _fallback(profile, job)

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    prompt = f"""
Create two concise outputs for a candidate applying to this job.

Candidate:
headline: {profile.headline}
summary: {profile.summary}
years: {profile.years_experience}
skills: {profile.skills}

Job:
title: {job.title}
company: {job.company}
description: {job.description[:6000]}

Return exactly:
SUMMARY:
<2-3 tailored resume-summary sentences>

COVER:
<short natural cover letter, 120-180 words>

Do not invent experience the candidate did not provide.
"""
    response = await client.responses.create(model=settings.openai_model, input=prompt)
    text = response.output_text
    if "COVER:" not in text:
        return _fallback(profile, job)
    summary_part, cover_part = text.split("COVER:", 1)
    return summary_part.replace("SUMMARY:", "").strip(), cover_part.strip()
