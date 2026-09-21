from app.services.resume_parser import infer_profile


def test_infer_profile_extracts_skills_and_role() -> None:
    text = """
    Python Developer with 3 years of experience.
    Built FastAPI services with PostgreSQL, Docker, Redis and Git.
    """
    profile = infer_profile(text)

    assert "Python" in profile["skills"]
    assert "FastAPI" in profile["skills"]
    assert "PostgreSQL" in profile["skills"]
    assert "Python Developer" in profile["target_roles"]
    assert profile["years_experience"] == 3
