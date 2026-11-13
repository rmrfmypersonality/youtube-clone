from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import update

from app.core.config import get_settings
from app.models import User

CREDS = {"email": "alice@example.com", "username": "alice", "password": "correct-horse-battery"}


async def register(client, **overrides):
    return await client.post("/api/auth/register", json={**CREDS, **overrides})


async def test_register_creates_user_and_channel(client):
    r = await register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == CREDS["email"]
    assert body["role"] == "user"
    assert body["channel"]["handle"] == "alice"
    assert "password" not in r.text


async def test_register_sets_httponly_cookies(client):
    r = await register(client)
    cookies = r.headers.get_list("set-cookie")
    assert len(cookies) == 2
    for c in cookies:
        assert "httponly" in c.lower()
        assert "samesite=lax" in c.lower()


async def test_register_logs_user_in(client):
    await register(client)
    r = await client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


async def test_register_duplicate_email_conflict(client):
    await register(client)
    r = await register(client, username="alice2", email="ALICE@example.com")
    assert r.status_code == 409


async def test_register_duplicate_username_is_case_insensitive(client):
    await register(client)
    r = await register(client, email="other@example.com", username="ALICE")
    assert r.status_code == 409


@pytest.mark.parametrize(
    "overrides",
    [
        {"password": "short"},
        {"username": "a b"},
        {"username": "ab"},
        {"email": "not-an-email"},
    ],
)
async def test_register_validation(client, overrides):
    r = await register(client, **overrides)
    assert r.status_code == 422


async def test_login_success(client):
    await register(client)
    await client.post("/api/auth/logout")
    r = await client.post("/api/auth/login", json={"email": CREDS["email"], "password": CREDS["password"]})
    assert r.status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 200


async def test_login_errors_do_not_reveal_which_part_is_wrong(client):
    await register(client)
    wrong_pass = await client.post("/api/auth/login", json={"email": CREDS["email"], "password": "wrong-password"})
    wrong_email = await client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"})
    assert wrong_pass.status_code == wrong_email.status_code == 401
    assert wrong_pass.json() == wrong_email.json()


async def test_me_requires_auth(client):
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_logout_clears_cookies_and_revokes_refresh_token(client):
    await register(client)
    old_refresh = client.cookies.get("refresh_token")
    assert (await client.post("/api/auth/logout")).status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 401
    r = await client.post("/api/auth/refresh", headers={"Cookie": f"refresh_token={old_refresh}"})
    assert r.status_code == 401


async def test_refresh_rotates_token(client):
    await register(client)
    old = client.cookies.get("refresh_token")
    r = await client.post("/api/auth/refresh")
    assert r.status_code == 200
    new = client.cookies.get("refresh_token")
    assert new and new != old
    assert (await client.get("/api/auth/me")).status_code == 200


async def test_refresh_without_cookie(client):
    assert (await client.post("/api/auth/refresh")).status_code == 401


async def test_refresh_token_reuse_revokes_whole_family(client):
    await register(client)
    stolen = client.cookies.get("refresh_token")
    assert (await client.post("/api/auth/refresh")).status_code == 200  # легитимная ротация

    # Атакующий предъявляет уже использованный токен
    r = await client.post("/api/auth/refresh", headers={"Cookie": f"refresh_token={stolen}"})
    assert r.status_code == 401

    # Новый токен легитимного пользователя тоже отозван
    assert (await client.post("/api/auth/refresh")).status_code == 401


@pytest.mark.parametrize(
    "secret,delta",
    [
        (get_settings().secret_key, timedelta(hours=-1)),  # просрочен
        ("some-other-secret-some-other-secret-1234", timedelta(hours=1)),  # чужая подпись
    ],
    ids=["expired", "wrong-signature"],
)
async def test_invalid_access_token_rejected(client, secret, delta):
    r = await register(client)
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(r.json()["id"]), "type": "access", "iat": now - timedelta(hours=2), "exp": now + delta},
        secret,
        algorithm="HS256",
    )
    r = await client.get("/api/auth/me", headers={"Cookie": f"access_token={token}"})
    assert r.status_code == 401


async def test_blocked_user_cannot_login(client, db):
    await register(client)
    await client.post("/api/auth/logout")
    await db.execute(update(User).where(User.username == "alice").values(is_active=False))
    await db.commit()
    r = await client.post("/api/auth/login", json={"email": CREDS["email"], "password": CREDS["password"]})
    assert r.status_code == 403


async def test_blocked_user_loses_access_immediately(client, db):
    await register(client)
    await db.execute(update(User).where(User.username == "alice").values(is_active=False))
    await db.commit()
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.post("/api/auth/refresh")).status_code == 401