from sqlalchemy import func, select, update

from app.models import Channel, Comment, Like, Playlist, Role, Subscription, User, Video
from app.storage import get_storage

PASSWORD = "correct-horse-battery"  # из conftest не импортируем: повторный импорт перезапустит его настройку


async def hide(client, hidden=True):
    r = await client.patch("/api/channels/me", json={"is_hidden": hidden})
    assert r.status_code == 200, r.text
    return r.json()


async def delete_account(client, password=PASSWORD):
    return await client.post("/api/account/delete", json={"password": password})


async def count(db, model) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


# --- скрытие канала ---


async def test_hide_and_show_channel(make_client, client):
    alice, bob = await make_client("alice"), await make_client("bob")
    assert (await alice.get("/api/channels/alice")).json()["is_hidden"] is False

    assert (await hide(alice))["is_hidden"] is True
    assert (await alice.get("/api/channels/alice")).json()["is_hidden"] is True  # владелец видит
    for viewer in (bob, client):
        assert (await viewer.get("/api/channels/alice")).status_code == 404

    assert (await hide(alice, False))["is_hidden"] is False
    assert (await client.get("/api/channels/alice")).status_code == 200


async def test_hidden_flag_does_not_touch_other_fields(make_client):
    alice = await make_client("alice")
    await alice.patch("/api/channels/me", json={"name": "Alice Channel"})
    body = await hide(alice)
    assert (body["name"], body["handle"]) == ("Alice Channel", "alice")


async def test_hidden_channel_content_disappears(make_client, client, make_video):
    alice, bob, carol = await make_client("alice"), await make_client("bob"), await make_client("carol")
    video = await make_video("alice")
    playlist = (await alice.post("/api/playlists", json={"title": "Mix"})).json()
    assert (await alice.put(f"/api/playlists/{playlist['id']}/items/{video.id}")).status_code == 204
    assert (await bob.put("/api/channels/alice/subscription")).status_code == 200
    url = f"/api/videos/{video.id}"

    await hide(alice)

    for viewer in (bob, client):
        for suffix in ("", "/stream", "/thumbnail"):
            assert (await viewer.get(url + suffix)).status_code == 404
        assert (await viewer.get("/api/channels/alice/videos")).status_code == 404
        assert (await viewer.get("/api/channels/alice/playlists")).status_code == 404
        assert (await viewer.get(f"/api/playlists/{playlist['id']}")).status_code == 404
        assert (await viewer.get("/api/videos")).json()["items"] == []
        assert (await viewer.get("/api/search", params={"q": "Test"})).json()["items"] == []
    assert (await bob.post(url + "/view")).status_code == 404
    assert (await bob.post(url + "/comments", json={"text": "hi"})).status_code == 404
    assert (await bob.put(url + "/reaction", json={"value": 1})).status_code == 404
    assert (await bob.post(url + "/report", json={"reason": "spam"})).status_code == 404
    assert (await bob.get("/api/subscriptions/feed")).json()["items"] == []
    assert (await bob.get("/api/subscriptions")).json() == []
    assert (await carol.put("/api/channels/alice/subscription")).status_code == 404

    # владелец ничего не теряет
    assert (await alice.get(url)).status_code == 200
    assert [v["id"] for v in (await alice.get("/api/videos/mine")).json()["items"]] == [video.id]
    own_playlist = (await alice.get(f"/api/playlists/{playlist['id']}")).json()
    assert [v["id"] for v in own_playlist["items"]] == [video.id]
    assert (await alice.get("/api/channels/alice")).json()["videos_count"] == 0

    await hide(alice, False)
    assert (await client.get(url)).status_code == 200
    assert [v["id"] for v in (await client.get("/api/videos")).json()["items"]] == [video.id]
    assert [c["handle"] for c in (await bob.get("/api/subscriptions")).json()] == ["alice"]  # подписка жива


async def test_can_unsubscribe_from_hidden_channel(make_client):
    alice, bob = await make_client("alice"), await make_client("bob")
    await bob.put("/api/channels/alice/subscription")
    await hide(alice)
    r = await bob.delete("/api/channels/alice/subscription")
    assert (r.status_code, r.json()["subscribed"]) == (200, False)


async def test_staff_cannot_view_hidden_channel_video(make_client, make_video, set_role):
    alice = await make_client("alice")
    mod = await make_client("mod")
    await set_role("mod", Role.moderator)
    video = await make_video("alice")
    await hide(alice)
    assert (await mod.get(f"/api/videos/{video.id}")).status_code == 404
    assert (await mod.get(f"/api/videos/{video.id}/stream")).status_code == 404


async def test_foreign_playlist_loses_video_of_hidden_channel(make_client, make_video):
    alice, bob = await make_client("alice"), await make_client("bob")
    video = await make_video("alice")
    playlist = (await bob.post("/api/playlists", json={"title": "Mine"})).json()
    await bob.put(f"/api/playlists/{playlist['id']}/items/{video.id}")
    url = f"/api/playlists/{playlist['id']}"
    assert (await bob.get(url)).json()["items_count"] == 1

    await hide(alice)
    detail = (await bob.get(url)).json()
    assert (detail["items"], detail["items_count"], detail["cover_video_id"]) == ([], 0, None)

    await hide(alice, False)
    assert [v["id"] for v in (await bob.get(url)).json()["items"]] == [video.id]


# --- удаление аккаунта ---


async def test_delete_account_requires_password(make_client, client):
    alice = await make_client("alice")
    assert (await delete_account(alice, "wrong-password")).status_code == 403
    assert (await alice.get("/api/auth/me")).status_code == 200  # сессия цела
    assert (await alice.post("/api/account/delete", json={})).status_code == 422
    assert (await alice.post("/api/account/delete", json={"password": ""})).status_code == 422
    assert (await client.post("/api/account/delete", json={"password": PASSWORD})).status_code == 401


async def test_delete_account_removes_everything(make_client, client, make_video, db):
    alice, _ = await make_client("alice"), await make_client("bob")
    video = await make_video("alice")
    storage = get_storage()
    for key in (f"videos/{video.id}/720.mp4", "originals/abc"):
        storage.local_path(key, for_write=True).write_bytes(b"x")
    await db.execute(update(Video).where(Video.id == video.id).values(original_path="originals/abc"))
    await db.commit()

    bob_video = await make_video("bob")
    await alice.post(f"/api/videos/{bob_video.id}/comments", json={"text": "hi"})
    await alice.put(f"/api/videos/{bob_video.id}/reaction", json={"value": 1})
    await alice.put("/api/channels/bob/subscription")
    await alice.post("/api/playlists", json={"title": "Mix"})

    assert (await delete_account(alice)).status_code == 204

    assert (await alice.get("/api/auth/me")).status_code == 401
    login = {"email": "alice@example.com", "password": PASSWORD}
    assert (await client.post("/api/auth/login", json=login)).status_code == 401
    assert (await client.get("/api/channels/alice")).status_code == 404
    assert (await client.get(f"/api/videos/{video.id}")).status_code == 404
    assert not storage.local_path("originals/abc").exists()
    assert not storage.local_path(f"videos/{video.id}").exists()

    for model in (Comment, Like, Playlist, Subscription):
        assert await count(db, model) == 0
    assert (await count(db, User), await count(db, Channel)) == (1, 1)  # остался bob

    # чужое не пострадало, а освободившееся имя можно занять заново
    assert (await client.get(f"/api/videos/{bob_video.id}")).status_code == 200
    assert (await client.get("/api/channels/bob")).json()["subscribers_count"] == 0
    r = await client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "username": "alice", "password": PASSWORD},
    )
    assert r.status_code == 201


async def test_last_admin_cannot_delete_account(make_client, set_role):
    root = await make_client("root")
    await set_role("root", Role.admin)
    assert (await delete_account(root)).status_code == 409

    other = await make_client("other")
    await set_role("other", Role.admin)
    assert (await delete_account(root)).status_code == 204
    assert (await other.get("/api/auth/me")).status_code == 200
    assert (await delete_account(other)).status_code == 409  # теперь он последний