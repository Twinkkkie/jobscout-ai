from collections.abc import AsyncGenerator

from sqlalchemy import text

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def create_schema() -> None:
    from app import models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        # MVP-safe additive migrations for existing local PostgreSQL databases.
        # A full Alembic migration setup can replace this before public launch.
        await connection.execute(
            text("ALTER TABLE candidate_profiles ADD COLUMN IF NOT EXISTS seniority_levels JSONB NOT NULL DEFAULT '[]'::jsonb")
        )
        await connection.execute(
            text("ALTER TABLE candidate_profiles ADD COLUMN IF NOT EXISTS ai_profile JSONB NOT NULL DEFAULT '{}'::jsonb")
        )
        await connection.execute(
            text("ALTER TABLE candidate_profiles ADD COLUMN IF NOT EXISTS ai_profile_updated_at TIMESTAMPTZ")
        )
        await connection.execute(
            text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS ai_analysis JSONB NOT NULL DEFAULT '{}'::jsonb")
        )
        await connection.execute(
            text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS ai_analyzed_at TIMESTAMPTZ")
        )
        await connection.execute(
            text("ALTER TABLE job_matches ADD COLUMN IF NOT EXISTS ai_explanation JSONB NOT NULL DEFAULT '{}'::jsonb")
        )
        await connection.execute(
            text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS recruiter_message TEXT NOT NULL DEFAULT ''")
        )
        await connection.execute(
            text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS interview_points JSONB NOT NULL DEFAULT '[]'::jsonb")
        )
        await connection.execute(
            text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS caution_notes JSONB NOT NULL DEFAULT '[]'::jsonb")
        )
        await connection.execute(
            text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS agent_trace JSONB NOT NULL DEFAULT '[]'::jsonb")
        )
        await connection.execute(
            text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ")
        )
        await connection.execute(
            text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMPTZ")
        )
        await connection.execute(
            text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE")
        )
        await connection.execute(
            text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ")
        )
        await connection.execute(
            text("UPDATE jobs SET last_seen_at = COALESCE(last_seen_at, collected_at)")
        )
        await connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_jobs_is_active ON jobs (is_active)")
        )
