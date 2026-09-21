from app.models import CandidateProfile, Job
from app.services.matching import score_job


def test_matching_rewards_role_and_skills() -> None:
    profile = CandidateProfile(
        skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
        target_roles=["Python Developer"],
        preferred_regions=["Europe", "Worldwide"],
        remote_only=True,
        exclude_keywords=["onsite only"],
        min_salary_usd=50000,
    )
    job = Job(
        source="test",
        external_id="1",
        title="Python Developer",
        company="Example",
        location="Remote Europe",
        remote_region="Europe",
        description="Build remote APIs with Python, FastAPI, PostgreSQL and Docker.",
        tags=["python", "backend", "remote"],
        salary_min=70000,
        salary_max=90000,
        currency="USD",
        url="https://example.com/job",
    )

    scored = score_job(profile, job)

    assert scored["score"] >= 75
    assert scored["verdict"] == "apply"
    assert "Python" in scored["matching_skills"]
