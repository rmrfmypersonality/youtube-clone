import pytest

from app.core.config import get_settings
from app.core.origin import is_allowed_origin

PASSWORD = "correct-horse-battery"  # из conftest не импортируем: повторный импорт перезапустит его настройку
CREDS = {"email": "alice@example.com", "username": "alice", "password": PASSWORD}
EVIL = {"Origin": "https://evil.example"}
PAYLOAD = "<img src=x onerror=alert(1)><script>alert(2)</script>"


@pytest.mark.parametrize(
    "origin,host,extra,expected",
    [
        ("http://test", "test", frozenset(), True),
        ("HTTP://TEST", "test", frozenset(), True),
        ("http://localhost:8080", "localhost:8080", frozenset(), True),
        ("http://localhost", "localhost:8080", frozenset(), False),  # другой порт = другой origin
        ("https://evil.example", "test", frozenset(), False),
        ("http://test.evil.example", "test", frozenset(), False),
        ("http://evil.example@test", "test", frozenset(), False),
        ("null", "test", frozenset(), False),
        ("javascript:alert(1)", "test", frozenset(), False),
        ("", "test", frozenset(), False),
        ("https://app.example.com", "test", frozenset({"https://app.example.com"}), True),
    ],
)
def test_is_allowed_origin(origin, host, extra, expected):
    assert is_allowed_origin(origin, host, extra) is expected


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_foreign_origin_blocked_on_unsafe_methods(client, method):
    r = await client.request(method, "/api/health", headers=EVIL)
    assert r.status_code == 403  # отказ приходит раньше маршрутизации и авторизации
    assert "чужого источника" in r.json()["detail"]


async def test_null_origin_blocked(client):
    r = await client.post("/api/auth/login", json={"email": "a@b.co", "password": "x"}, headers={"Origin": "null"})
    assert r.status_code == 403


async def test_foreign_origin_allowed_on_safe_methods(client):
    assert (await client.get("/api/health", headers=EVIL)).status_code == 200


async def test_same_origin_and_missing_origin_pass(client):
    body = {"email": "nobody@example.com", "password": "wrong-password"}
    same = await client.post("/api/auth/login", json=body, headers={"Origin": "http://test"})
    assert same.status_code == 401  # дошло до логики входа
    assert (await client.post("/api/auth/login", json=body)).status_code == 401


async def test_csrf_cannot_act_as_logged_in_user(make_client):
    alice = await make_client("alice")

    assert (await alice.post("/api/videos", json={"title": "x"}, headers=EVIL)).status_code == 403
    assert (await alice.get("/api/videos/mine")).json()["items"] == []

    assert (await alice.post("/api/auth/logout", headers=EVIL)).status_code == 403
    assert (await alice.get("/api/auth/me")).status_code == 200  # сессия цела

    r = await alice.post("/api/account/delete", json={"password": PASSWORD}, headers=EVIL)
    assert r.status_code == 403
    assert (await alice.get("/api/auth/me")).status_code == 200  # аккаунт не удалён


async def test_no_cors_headers(client):
    r = await client.get("/api/videos", headers=EVIL)
    assert "access-control-allow-origin" not in r.headers
    pre = await client.options(
        "/api/videos", headers={**EVIL, "Access-Control-Request-Method": "POST"}
    )
    assert "access-control-allow-origin" not in pre.headers
    assert pre.status_code in (404, 405)  # preflight не обслуживается: кросс-сайтовые запросы невозможны


async def test_cookie_secure_follows_setting(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "cookie_secure", True)
    cookies = (await client.post("/api/auth/register", json=CREDS)).headers.get_list("set-cookie")
    assert len(cookies) == 2
    assert all("secure" in c.lower() for c in cookies)
    refresh = next(c for c in cookies if c.startswith("refresh_token="))
    assert "path=/api/auth" in refresh.lower()  # refresh-кука не уходит на остальные адреса


async def test_cookies_without_secure_by_default(client):
    cookies = (await client.post("/api/auth/register", json=CREDS)).headers.get_list("set-cookie")
    assert not any("secure" in c.lower() for c in cookies)


async def test_user_text_is_returned_as_json_data(make_client, make_video):
    """Бэкенд хранит текст как есть и отдаёт строго как JSON. Экранирует фронт ({{ }}) и CSP."""
    alice = await make_client("alice")
    video = await make_video("alice")
    await alice.patch(f"/api/videos/{video.id}", json={"description": PAYLOAD})
    await alice.patch("/api/channels/me", json={"name": PAYLOAD, "description": PAYLOAD})
    await alice.post("/api/playlists", json={"title": PAYLOAD})
    await alice.post(f"/api/videos/{video.id}/comments", json={"text": PAYLOAD})

    for url in (
        f"/api/videos/{video.id}",
        "/api/channels/alice",
        f"/api/videos/{video.id}/comments",
        "/api/channels/alice/playlists",
    ):
        r = await alice.get(url)
        assert r.headers["content-type"].startswith("application/json"), url
        assert PAYLOAD in r.text, url