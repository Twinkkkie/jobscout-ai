from openai import AsyncOpenAI

from app.core.config import settings
from app.models import CandidateProfile, Job
from app.services.matching import score_job


def _fallback(profile: CandidateProfile, job: Job, resume_text: str = "") -> tuple[str, str]:
    match = score_job(profile, job)
    matched = ", ".join(match["matching_skills"][:10])
    gaps = ", ".join(match["skill_gaps"][:5])

    summary = (
        f"{profile.headline or 'Python / AI Developer'} with {profile.years_experience} years of "
        f"commercial software development experience, applying for the {job.title} role at {job.company}. "
        f"The strongest overlap with this vacancy includes {matched or 'Python development, backend engineering and automation'}. "
        f"The candidate's background combines practical software delivery with AI-focused development, APIs, data workflows and automation. "
        f"The profile is especially relevant where the role values hands-on implementation, ownership and the ability to learn adjacent technologies quickly."
    )

    gap_sentence = (
        f"Some technologies mentioned in the vacancy, including {gaps}, are not currently listed in the candidate profile; "
        "they should be discussed transparently rather than presented as existing experience. "
        if gaps
        else ""
    )

    letter = (
        f"Dear {job.company} Hiring Team,\n\n"
        f"I am applying for the {job.title} position. I have {profile.years_experience} years of commercial "
        "software development experience and currently focus on Python, backend systems and AI-powered applications. "
        f"My most relevant overlap with this role includes {matched or 'Python development, APIs, automation and backend engineering'}.\n\n"
        f"{profile.summary.strip() or 'My background includes commercial Python development, internal engineering tools, automation, web development and recent AI-focused portfolio work.'} "
        "In recent projects I have worked on practical systems involving APIs, databases, background processing, AI integrations and workflow automation. "
        "I am comfortable taking a feature from requirements through implementation and testing, and I use AI-assisted development tools as part of the engineering workflow while still validating architecture and final behavior myself.\n\n"
        f"What interests me about this opportunity is the chance to apply that background to the problems described in your vacancy. "
        f"{gap_sentence}"
        "I would be glad to discuss the role in more detail and explain which parts of my experience are directly transferable to your stack and product.\n\n"
        "Best regards"
    )
    return summary, letter


async def prepare_application(
    profile: CandidateProfile,
    job: Job,
    resume_text: str = "",
) -> tuple[str, str]:
    if not settings.openai_api_key:
        return _fallback(profile, job, resume_text)

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    match = score_job(profile, job)

    prompt = f"""
You are preparing an application pack for a real candidate. Be specific, useful and natural.

STRICT RULES:
- Never invent employment, projects, achievements, metrics, education, clients or technologies.
- Only state experience that is supported by the candidate profile or resume text below.
- If the vacancy asks for a skill the candidate does not have, do not pretend they have it.
- Avoid generic corporate filler and exaggerated enthusiasm.
- Use the vacancy's wording where appropriate, but do not copy large passages.
- Write in professional international English.

CANDIDATE PROFILE:
Headline: {profile.headline}
Summary: {profile.summary}
Years of commercial software development experience: {profile.years_experience}
Skills: {profile.skills}
Target roles: {profile.target_roles}

RESUME TEXT:
{resume_text[:10000]}

VACANCY:
Title: {job.title}
Company: {job.company}
Location: {job.location}
Tags: {job.tags}
Description:
{job.description[:10000]}

DETERMINISTIC MATCH ANALYSIS:
Matching skills: {match["matching_skills"]}
Detected gaps: {match["skill_gaps"]}
Match reasons: {match["reasons"]}

Return exactly these two sections:

SUMMARY:
Write a tailored professional summary of 4-6 substantial sentences, around 110-160 words.
It should position the candidate for this exact vacancy, mention the strongest relevant experience and technologies,
and make clear why their background is transferable. Do not write in first person.

COVER:
Write a tailored cover letter of 260-340 words.
Use 4-6 short paragraphs.
Paragraph 1: role + concise reason for fit.
Paragraphs 2-4: connect specific candidate experience/projects/technologies to the vacancy.
Mention concrete relevant tools from the resume when supported.
If there are gaps, frame them honestly and briefly rather than hiding them.
Final paragraph: concise call to action.
Do not use bullet points unless the vacancy itself strongly suggests that format.
Do not use clichés such as "I am thrilled", "perfect fit", or "passionate about".
"""
    response = await client.responses.create(model=settings.openai_model, input=prompt)
    text = response.output_text.strip()
    if "COVER:" not in text:
        return _fallback(profile, job, resume_text)

    summary_part, cover_part = text.split("COVER:", 1)
    summary = summary_part.replace("SUMMARY:", "").strip()
    cover = cover_part.strip()

    # Guard against unexpectedly tiny generations.
    if len(summary.split()) < 60 or len(cover.split()) < 180:
        return _fallback(profile, job, resume_text)

    return summary, cover
