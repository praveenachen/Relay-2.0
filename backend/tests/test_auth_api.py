import pytest
from conftest import login, register
from sqlalchemy import select

from app.domain.enums import Provider
from app.infrastructure.credentials import FernetCredentialStore
from app.models.entities import AuditEvent, ConnectedAccount, ProjectWorkspace, User, UserPreference


async def test_signup_login_logout(client, session_factory):
    user = await register(client, "Student@Example.com")
    assert "hashed_password" not in user
    assert "password" not in user
    response = await login(client)
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert "Secure" in cookie
    old_cookie = client.cookies.get("relay_session")
    assert (await client.get("/users/me")).json()["id"] == user["id"]
    assert (await client.get("/preferences")).status_code == 200
    assert (await client.post("/auth/logout")).status_code == 204
    client.cookies.set("relay_session", old_cookie)
    assert (await client.get("/users/me")).status_code == 401
    async with session_factory() as session:
        stored = await session.scalar(select(User))
        assert stored.hashed_password.startswith("$argon2")
        assert (await session.scalar(select(AuditEvent))).event_type == "USER_CREATED"


async def test_duplicate_email_and_privilege_escalation(client):
    await register(client)
    duplicate = await client.post(
        "/auth/register",
        json={
            "email": "STUDENT@example.com",
            "password": "a sufficiently long test password",
            "name": "Other",
        },
    )
    assert duplicate.status_code == 400
    response = await client.post(
        "/auth/register",
        json={
            "email": "other@example.com",
            "password": "a sufficiently long test password",
            "name": "Other",
            "is_superuser": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["is_superuser"] is False


async def test_bad_password_and_failed_login(client):
    response = await client.post(
        "/auth/register",
        json={"email": "student@example.com", "password": "short", "name": "Student"},
    )
    assert response.status_code == 400
    assert "short" not in response.text
    await register(client)
    response = await client.post(
        "/auth/login", data={"username": "student@example.com", "password": "wrong"}
    )
    assert response.status_code == 400
    assert not client.cookies


async def test_csrf_blocks_missing_and_foreign_origin(client):
    client.headers.pop("origin")
    assert (await client.post("/auth/login")).status_code == 403
    client.headers["Origin"] = "https://attacker.example"
    assert (await client.post("/auth/register")).status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/users/me",
        "/preferences",
        "/workflow-runs",
        "/workflow-definitions",
        "/approvals",
        "/connections",
        "/connections/NOTION/authorize",
        "/connections/NOTION/callback",
    ],
)
async def test_unauthenticated_access(client, path):
    assert (await client.get(path)).status_code == 401


async def test_profile_and_onboarding(client, account):
    response = await client.patch("/users/me", json={"name": "Updated"})
    assert response.json()["name"] == "Updated"
    assert (await client.patch("/users/me", json={"name": " "})).status_code == 422
    assert (await client.post("/users/me/onboarding")).status_code == 204
    assert (await client.get("/users/me")).json()["onboarding_completed"] is True


async def test_reset_history_clears_profile_activity_but_keeps_connection(
    client, account, session_factory
):
    key = "Nq0gMu1xFQPTg1D0Yv4qPNXBJYVw-MLEaxCYe4mDTiU="
    store = FernetCredentialStore([key])
    async with session_factory() as session:
        session.add(
            ConnectedAccount(
                user_id=account["id"],
                provider=Provider.NOTION,
                external_account_id="workspace-1",
                display_name="Student Workspace",
                access_token_encrypted=store.encrypt("notion-token"),
                scopes=["read_content"],
                provider_metadata={
                    "workspace_id": "workspace-1",
                    "default_destination_id": "page-1",
                    "default_destination_title": "Notes",
                },
                status="CONNECTED",
            )
        )
        await session.commit()

    created = await client.post("/projects", json={"name": "StudySync"})
    assert created.status_code == 201, created.text
    await client.put(
        "/preferences",
        json={
            "timezone": "America/Toronto",
            "earliest_study_time": "09:00:00",
            "latest_study_time": "21:00:00",
            "preferred_session_minutes": 45,
            "maximum_session_minutes": 75,
            "minimum_break_minutes": 5,
        },
    )
    assert (await client.post("/users/me/onboarding")).status_code == 204

    response = await client.post("/users/me/history/reset")

    assert response.status_code == 204
    assert (await client.get("/projects")).json() == []
    me = (await client.get("/users/me")).json()
    assert me["onboarding_completed"] is False
    prefs = (await client.get("/preferences")).json()
    assert prefs["timezone"] == "UTC"
    assert prefs["preferred_session_minutes"] == 50

    async with session_factory() as session:
        assert await session.get(User, account["id"]) is not None
        connection = await session.scalar(select(ConnectedAccount))
        assert connection is not None
        assert connection.status == "CONNECTED"
        assert "default_destination_id" not in connection.provider_metadata
        assert await session.scalar(select(ProjectWorkspace)) is None
        assert await session.scalar(select(UserPreference)) is not None
