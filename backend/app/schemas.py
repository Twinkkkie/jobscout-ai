from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(default="", max_length=120)
    locale: str = Field(default="en", pattern="^(en|ru)$")


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    display_name: str
    locale: str


class ProfileUpdate(BaseModel):
    headline: str = ""
    summary: str = ""
    years_experience: int = Field(default=0, ge=0, le=60)
    english_level: str = ""
    skills: list[str] = []
    target_roles: list[str] = []
    seniority_levels: list[str] = []
    preferred_regions: list[str] = []
    min_salary_usd: int | None = Field(default=None, ge=0)
    remote_only: bool = True
    exclude_keywords: list[str] = []


class ProfileRead(ProfileUpdate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    ai_profile: dict = {}
    ai_profile_updated_at: datetime | None = None


class ResumeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    filename: str
    content_type: str
    extracted_profile: dict
    created_at: datetime


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source: str
    title: str
    company: str
    location: str
    remote_region: str
    tags: list
    salary_min: int | None
    salary_max: int | None
    currency: str
    url: str
    published_at: datetime | None
    collected_at: datetime
    last_checked_at: datetime | None
    is_active: bool
    closed_at: datetime | None
    ai_analysis: dict = {}
    ai_analyzed_at: datetime | None = None


class MatchRead(BaseModel):
    id: UUID
    score: float
    matching_skills: list[str]
    skill_gaps: list[str]
    reasons: list[str]
    verdict: str
    ai_explanation: dict = {}
    job: JobRead


class ApplicationUpsert(BaseModel):
    status: str = Field(pattern="^(saved|applied|interview|offer|rejected|withdrawn)$")
    notes: str = ""


class ApplicationRead(BaseModel):
    id: UUID
    status: str
    notes: str
    tailored_summary: str
    cover_letter: str
    recruiter_message: str = ""
    interview_points: list[str] = []
    caution_notes: list[str] = []
    agent_trace: list[str] = []
    job: JobRead


class DashboardStats(BaseModel):
    jobs_total: int
    strong_matches: int
    saved: int
    applied: int
    interviews: int
    offers: int


class CareerInsightRead(BaseModel):
    summary: str
    recurring_gaps: list[str]
    strongest_skills: list[str]
    target_role_observations: list[str]
    recommended_actions: list[str]
    ai_enriched: bool = False


class MatchAnalysisRead(BaseModel):
    match: MatchRead
    explanation: dict
