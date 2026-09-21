from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.application import run_application_agent
from app.db import get_db
from app.deps import get_current_user
from app.models import Application, CandidateProfile, Job, Resume, User
from app.schemas import ApplicationRead, ApplicationUpsert, JobRead

router = APIRouter(prefix="/applications", tags=["applications"])


def _read(application: Application, job: Job) -> ApplicationRead:
    return ApplicationRead(
        id=application.id,
        status=application.status,
        notes=application.notes,
        tailored_summary=application.tailored_summary,
        cover_letter=application.cover_letter,
        recruiter_message=application.recruiter_message,
        interview_points=application.interview_points,
        caution_notes=application.caution_notes,
        agent_trace=application.agent_trace,
        job=JobRead.model_validate(job),
    )


@router.put("/{job_id}", response_model=ApplicationRead)
async def upsert_application(
    job_id: UUID,
    payload: ApplicationUpsert,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationRead:
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    application = await db.scalar(
        select(Application).where(Application.user_id == user.id, Application.job_id == job_id)
    )
    if application is None:
        application = Application(user_id=user.id, job_id=job_id)
        db.add(application)
    application.status = payload.status
    application.notes = payload.notes
    await db.commit()
    await db.refresh(application)
    return _read(application, job)


@router.post("/{job_id}/prepare", response_model=ApplicationRead)
async def prepare(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationRead:
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    profile = await db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(status_code=409, detail="Complete your profile first")

    application = await db.scalar(
        select(Application).where(Application.user_id == user.id, Application.job_id == job_id)
    )
    if application is None:
        application = Application(user_id=user.id, job_id=job_id, status="saved")
        db.add(application)

    latest_resume = await db.scalar(
        select(Resume)
        .where(Resume.user_id == user.id)
        .order_by(Resume.created_at.desc())
    )
    agent_result = await run_application_agent(
        db,
        profile,
        job,
        latest_resume.extracted_text if latest_resume else "",
    )
    pack = agent_result["pack"]
    application.tailored_summary = pack.get("tailored_summary", "")
    application.cover_letter = pack.get("cover_letter", "")
    application.recruiter_message = pack.get("recruiter_message", "")
    application.interview_points = pack.get("interview_points", [])
    application.caution_notes = pack.get("caution_notes", [])
    application.agent_trace = agent_result.get("trace", [])
    await db.commit()
    await db.refresh(application)
    return _read(application, job)


@router.get("", response_model=list[ApplicationRead])
async def list_applications(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ApplicationRead]:
    rows = (
        await db.execute(
            select(Application, Job)
            .join(Job, Job.id == Application.job_id)
            .where(Application.user_id == user.id)
            .order_by(Application.updated_at.desc())
        )
    ).all()
    return [_read(application, job) for application, job in rows]


@router.delete("/{job_id}", status_code=204)
async def delete_application(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    application = await db.scalar(
        select(Application).where(Application.user_id == user.id, Application.job_id == job_id)
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.status != "saved":
        raise HTTPException(
            status_code=409,
            detail="Only saved vacancies can be removed from the saved list",
        )
    await db.delete(application)
    await db.commit()
