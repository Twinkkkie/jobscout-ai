import asyncio
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models import CandidateProfile, Resume, User
from app.schemas import ResumeRead
from app.worker import enrich_resume_task, rebuild_matches_task
from app.services.resume_parser import UnsupportedResume, extract_text, infer_profile

router = APIRouter(prefix="/resumes", tags=["resumes"])


def _queue_resume_enrichment(user_id: str, resume_id: str) -> None:
    """Queue slow AI work only after the upload response has been sent."""
    try:
        enrich_resume_task.delay(user_id, resume_id)
    except Exception:
        try:
            rebuild_matches_task.delay(user_id)
        except Exception:
            pass


@router.post("", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Resume:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Resume must be 10 MB or smaller")

    # PDF/DOCX parsing is synchronous. Run it off the event loop and cap the
    # parsing time so a malformed document can never leave the UI spinning forever.
    try:
        text = await asyncio.wait_for(
            asyncio.to_thread(extract_text, file.filename or "resume", data),
            timeout=20,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=422,
            detail="Resume parsing timed out. Try another PDF or DOCX file.",
        ) from exc
    except UnsupportedResume as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Could not read resume file") from exc

    if not text.strip():
        raise HTTPException(status_code=422, detail="No readable text found in resume")

    extracted = infer_profile(text)

    upload_dir = Path(settings.upload_dir) / str(user.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid4()}_{Path(file.filename or 'resume').name}"
    path = upload_dir / safe_name
    path.write_bytes(data)

    resume = Resume(
        user_id=user.id,
        filename=file.filename or "resume",
        content_type=file.content_type or "application/octet-stream",
        storage_path=str(path),
        extracted_text=text,
        extracted_profile=extracted,
    )
    db.add(resume)

    profile = await db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if profile:
        if extracted.get("skills"):
            profile.skills = sorted(set((profile.skills or []) + extracted["skills"]))
        if extracted.get("target_roles") and not profile.target_roles:
            profile.target_roles = extracted["target_roles"]
        if extracted.get("years_experience", 0) > profile.years_experience:
            profile.years_experience = extracted["years_experience"]
        if not profile.summary and extracted.get("summary"):
            profile.summary = extracted["summary"]
        profile.ai_profile = {**extracted, "ai_enriched": False}

    await db.commit()
    await db.refresh(resume)

    # Important: FastAPI sends the ResumeRead response first. Only then do we
    # contact Celery/Redis, so a slow/unavailable worker cannot block the preview.
    if profile:
        background_tasks.add_task(
            _queue_resume_enrichment,
            str(user.id),
            str(resume.id),
        )

    return resume


@router.get("", response_model=list[ResumeRead])
async def list_resumes(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Resume]:
    result = await db.execute(
        select(Resume).where(Resume.user_id == user.id).order_by(Resume.created_at.desc())
    )
    return list(result.scalars().all())
