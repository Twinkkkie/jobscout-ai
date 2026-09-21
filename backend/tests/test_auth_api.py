from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_register_login_and_profile() -> None:
    with TestClient(app) as client:
        email = f"candidate-{uuid4()}@example.com"
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "a-strong-password-123",
                "display_name": "Pinkkkie",
                "locale": "en",
            },
        )
        assert registered.status_code == 201

        logged_in = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "a-strong-password-123"},
        )
        assert logged_in.status_code == 200
        token = logged_in.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        profile = client.put(
            "/api/v1/profile",
            headers=headers,
            json={
                "headline": "Python Developer",
                "summary": "Backend and AI development",
                "years_experience": 3,
                "english_level": "B1",
                "skills": ["Python", "FastAPI", "PostgreSQL"],
                "target_roles": ["Python Developer"],
                "preferred_regions": ["Worldwide"],
                "min_salary_usd": 50000,
                "remote_only": True,
                "exclude_keywords": ["onsite"],
            },
        )
        assert profile.status_code == 200
        assert profile.json()["skills"][0] == "Python"
