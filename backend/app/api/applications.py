from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import Application, CandidateProfile, Job, User
from app.schemas import ApplicationRead, ApplicationUpsert, JobRead
from app.services.application_ai import prepare_application

router = APIRouter(prefix="/applications", tags=["applications"])


def _read(application: Application, job: Job) -> ApplicationRead:
    return ApplicationRead(
        id=application.id,
        status=application.status,
        notes=application.notes,
        tailored_summary=application.tailored_summary,
        cover_letter=application.cover_letter,
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

    summary, letter = await prepare_application(profile, job)
    application.tailored_summary = summary
    application.cover_letter = letter
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
