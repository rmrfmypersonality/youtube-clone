from sqlalchemy import func, select

from app.models import AuditLog, Role

PASSWORD = "correct-horse-battery"  # из conftest не импортируем: повторный импорт перезапустит его настройку


async def make_admin(make_client, set_role, username="root"):
    client = await make_client(username)
    await set_role(username, Role.admin)
    return client


async def user_id(client) -> int:
    return (await client.get("/api/auth/me")).json()["id"]


async def test_admin_endpoints_require_admin(make_client, client, set_role):
    bob = await make_client("bob")
    mod = await make_client("mod")
    await set_role("mod", Role.moderator)
    root = await make_admin(make_client, set_role)

    for method, url in [
        ("GET", "/api/admin/users"),
        ("GET", "/api/admin/audit"),
        ("PATCH", "/api/admin/users/1"),
    ]:
        assert (await client.request(method, url)).status_code == 401
        assert (await bob.request(method, url)).status_code == 403
        assert (await mod.request(method, url)).status_code == 403
    assert (await root.get("/api/admin/users")).status_code == 200
    assert (await root.get("/api/admin/audit")).status_code == 200


async def test_list_users_search_and_pagination(make_client, set_role):
    for name in ("alice", "bob", "carol"):
        await make_client(name)
    root = await make_admin(make_client, set_role)

    page = (await root.get("/api/admin/users")).json()
    assert [u["username"] for u in page["items"]] == ["root", "carol", "bob", "alice"]
    alice = page["items"][-1]
    assert alice["email"] == "alice@example.com"
    assert (alice["role"], alice["is_active"], alice["channel_handle"]) == ("user", True, "alice")

    async def search(q):
        r = await root.get("/api/admin/users", params={"q": q})
        return [u["username"] for u in r.json()["items"]]

    assert await search("ALI") == ["alice"]
    assert await search("bob@example") == ["bob"]
    assert await search("%") == []  # wildcard экранируется
    assert await search("_") == []
    assert await search("nobody") == []

    first = (await root.get("/api/admin/users", params={"limit": 2})).json()
    assert [u["username"] for u in first["items"]] == ["root", "carol"]
    second = (
        await root.get("/api/admin/users", params={"limit": 2, "cursor": first["next_cursor"]})
    ).json()
    assert [u["username"] for u in second["items"]] == ["bob", "alice"]
    assert second["next_cursor"] is None


async def test_change_role(make_client, set_role, db):
    bob = await make_client("bob")
    root = await make_admin(make_client, set_role)
    bob_id = await user_id(bob)
    url = f"/api/admin/users/{bob_id}"

    assert (await bob.get("/api/moderation/reports")).status_code == 403
    r = await root.patch(url, json={"role": "moderator"})
    assert r.status_code == 200
    assert r.json()["role"] == "moderator"
    # роль читается из БД на каждом запросе: действует сразу
    assert (await bob.get("/api/moderation/reports")).status_code == 200
    assert (await bob.get("/api/auth/me")).json()["role"] == "moderator"

    assert (await root.patch(url, json={"role": "user"})).json()["role"] == "user"
    assert (await bob.get("/api/moderation/reports")).status_code == 403
    assert (await root.patch(url, json={"role": "superuser"})).status_code == 422

    rows = (await db.execute(select(AuditLog).order_by(AuditLog.id))).scalars().all()
    assert [(a.action, a.target_id, a.details["from"], a.details["to"]) for a in rows] == [
        ("user.role_change", bob_id, "user", "moderator"),
        ("user.role_change", bob_id, "moderator", "user"),
    ]


async def test_block_and_unblock(make_client, client, set_role, db):
    bob = await make_client("bob")
    root = await make_admin(make_client, set_role)
    bob_id = await user_id(bob)
    url = f"/api/admin/users/{bob_id}"
    login = {"email": "bob@example.com", "password": PASSWORD}

    r = await root.patch(url, json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    assert (await bob.get("/api/auth/me")).status_code == 401  # доступ обрывается сразу
    assert (await client.post("/api/auth/login", json=login)).status_code == 403

    assert (await root.patch(url, json={"is_active": True})).json()["is_active"] is True
    # блокировка отозвала refresh-токены: после разблокировки старая сессия не оживает
    assert (await bob.post("/api/auth/refresh")).status_code == 401
    assert (await client.post("/api/auth/login", json=login)).status_code == 200

    actions = (await db.execute(select(AuditLog.action).order_by(AuditLog.id))).scalars().all()
    assert list(actions) == ["user.block", "user.unblock"]


async def test_admin_cannot_change_own_account(make_client, set_role):
    root = await make_admin(make_client, set_role)
    root_id = await user_id(root)
    for payload in ({"role": "user"}, {"is_active": False}, {}):
        assert (await root.patch(f"/api/admin/users/{root_id}", json=payload)).status_code == 400
    assert (await root.get("/api/auth/me")).json()["role"] == "admin"


async def test_noop_update_writes_no_audit(make_client, set_role, db):
    bob = await make_client("bob")
    root = await make_admin(make_client, set_role)
    url = f"/api/admin/users/{await user_id(bob)}"

    assert (await root.patch(url, json={"role": "user", "is_active": True})).status_code == 200
    assert (await root.patch(url, json={})).status_code == 200
    assert (await db.execute(select(func.count()).select_from(AuditLog))).scalar_one() == 0


async def test_update_unknown_user(make_client, set_role):
    root = await make_admin(make_client, set_role)
    assert (await root.patch("/api/admin/users/99999", json={"role": "user"})).status_code == 404
    assert (await root.patch("/api/admin/users/99999999999", json={"role": "user"})).status_code == 422


async def test_audit_listing(make_client, set_role):
    bob = await make_client("bob")
    root = await make_admin(make_client, set_role)
    bob_id = await user_id(bob)
    url = f"/api/admin/users/{bob_id}"
    await root.patch(url, json={"role": "moderator"})
    await root.patch(url, json={"role": "user"})
    await root.patch(url, json={"is_active": False})

    page = (await root.get("/api/admin/audit", params={"limit": 2})).json()
    assert [a["action"] for a in page["items"]] == ["user.block", "user.role_change"]
    top = page["items"][0]
    assert top["actor"]["handle"] == "root"
    assert (top["target_type"], top["target_id"]) == ("user", bob_id)
    assert top["details"] == {"username": "bob"}

    rest = (
        await root.get("/api/admin/audit", params={"limit": 2, "cursor": page["next_cursor"]})
    ).json()
    assert [a["action"] for a in rest["items"]] == ["user.role_change"]
    assert rest["next_cursor"] is None