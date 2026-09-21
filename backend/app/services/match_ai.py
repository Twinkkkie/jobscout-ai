from typing import Any

from app.models import CandidateProfile, Job


async def explain_match_ai(
    profile: CandidateProfile,
    job: Job,
    scored: dict[str, Any],
    resume_text: str = "",
    locale: str = "en",
) -> dict[str, Any]:
    """
    Fast localized explanation layer.

    Vacancy understanding may be AI-enriched, but this explanation is generated
    deterministically from the current hybrid score so opening Match stays instant.
    """
    is_ru = locale == "ru"
    raw_analysis = job.ai_analysis or {}
    ai_enriched = bool(
        raw_analysis.get("ai_enriched")
        and raw_analysis.get("analysis_version") == 3
    )
    analysis = raw_analysis if ai_enriched else {}

    strengths = list(scored.get("matching_skills") or [])[:10]
    gaps = list(scored.get("skill_gaps") or [])[:10]

    role_family = str(analysis.get("role_family") or "").strip()
    seniority = str(analysis.get("seniority") or "").strip()
    must_have = [str(x) for x in (analysis.get("must_have_skills") or [])][:12]
    nice_to_have = [str(x) for x in (analysis.get("nice_to_have_skills") or [])][:10]

    if is_ru:
        summary_parts = [
            f"Совпадение: {scored.get('score', 0)}%.",
            (
                f"Самые сильные совпадения по стеку: {', '.join(strengths[:6])}."
                if strengths
                else "Явных сильных технических совпадений не найдено."
            ),
            (
                f"Основные пробелы: {', '.join(gaps[:6])}."
                if gaps
                else "Дополнительных явных технических пробелов не найдено."
            ),
        ]
        if role_family:
            summary_parts.append(f"Направление вакансии: {role_family}.")
        if seniority:
            summary_parts.append(f"Определенный грейд: {seniority}.")
    else:
        summary_parts = [
            f"Match score: {scored.get('score', 0)}%.",
            (
                f"Strongest detected overlap: {', '.join(strengths[:6])}."
                if strengths
                else "No strong explicit technical overlap was detected."
            ),
            (
                f"Main detected gaps: {', '.join(gaps[:6])}."
                if gaps
                else "No additional explicit technical gaps were detected."
            ),
        ]
        if role_family:
            summary_parts.append(f"Vacancy role family: {role_family}.")
        if seniority:
            summary_parts.append(f"Detected seniority: {seniority}.")

    transferable: list[str] = []
    candidate_skills = {str(skill).lower(): str(skill) for skill in (profile.skills or [])}
    for skill in nice_to_have:
        if skill.lower() in candidate_skills and candidate_skills[skill.lower()] not in strengths:
            transferable.append(candidate_skills[skill.lower()])

    advice: list[str] = []
    if gaps:
        advice.append(
            "Главные gaps лучше обозначить прямо и не выдавать их за существующий опыт."
            if is_ru
            else "Address the most important gaps directly and do not present them as existing experience."
        )
    if strengths:
        advice.append(
            "В отклике сделай акцент на самых сильных совпадениях по стеку и добавь один конкретный пример из проекта или опыта."
            if is_ru
            else "Lead the application with the strongest matching technologies and one concrete project/example."
        )
    if must_have:
        missing_must = [skill for skill in must_have if skill in gaps]
        if missing_must:
            prefix = (
                "Особенно обрати внимание на отсутствующие must-have требования: "
                if is_ru
                else "Pay special attention to missing must-have requirements: "
            )
            advice.append(prefix + ", ".join(missing_must[:5]) + ".")

    return {
        "summary": " ".join(summary_parts),
        "strengths": strengths,
        "gaps": gaps,
        "transferable_skills": transferable[:8],
        "application_advice": advice[:5],
        "ai_enriched": ai_enriched,
        "locale": locale,
    }
