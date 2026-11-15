import pytest

from app.models import Role, VideoStatus, Visibility

PASSWORD = "correct-horse-battery"  # из conftest не импортируем: повторный импорт перезапустит его настройку


async def test_channel_page(make_client, client, make_video):
    alice = await make_client("alice")
    await make_video("alice")
    await make_video("alice", visibility=Visibility.private)
    await make_video("alice", status=VideoStatus.uploaded)
    await make_video("alice", hidden=True)

    body = (await client.get("/api/channels/ALICE")).json()  # регистр не важен
    assert body["handle"] == "alice"
    assert body["videos_count"] == 1  # считаются только публичные готовые
    assert body["subscribers_count"] == 0
    assert body["is_subscribed"] is False
    assert body["is_owner"] is False
    assert (await alice.get("/api/channels/alice")).json()["is_owner"] is True


async def test_channel_not_found_and_bad_handle(client):
    assert (await client.get("/api/channels/nobody")).status_code == 404
    assert (await client.get("/api/channels/ab")).status_code == 422
    assert (await client.get("/api/channels/bad!name")).status_code == 422


async def test_channel_videos(make_client, client, make_video):
    await make_client("alice")
    await make_client("bob")
    created = [(await make_video("alice")).id for _ in range(3)]
    await make_video("alice", visibility=Visibility.unlisted)
    await make_video("alice", hidden=True)
    await make_video("bob")

    first = (await client.get("/api/channels/alice/videos", params={"limit": 2})).json()
    assert [v["id"] for v in first["items"]] == created[::-1][:2]
    second = (
        await client.get(
            "/api/channels/alice/videos", params={"limit": 2, "cursor": first["next_cursor"]}
        )
    ).json()
    assert [v["id"] for v in second["items"]] == created[::-1][2:]
    assert second["next_cursor"] is None
    assert (await client.get("/api/channels/nobody/videos")).status_code == 404


async def test_update_channel(make_client, client):
    alice = await make_client("alice")
    r = await alice.patch(
        "/api/channels/me",
        json={"name": "  Alice Channel ", "description": "about me", "handle": "alice_new"},
    )
    assert r.status_code == 200
    body = r.json()
    assert (body["name"], body["description"], body["handle"]) == ("Alice Channel", "about me", "alice_new")

    me = (await alice.get("/api/auth/me")).json()
    assert me["channel"]["handle"] == "alice_new"
    assert me["username"] == "alice"  # username не меняется
    assert (await client.get("/api/channels/alice")).status_code == 404
    assert (await client.get("/api/channels/alice_new")).status_code == 200

    # частичное обновление не трогает остальное
    r = await alice.patch("/api/channels/me", json={"name": "Renamed"})
    assert r.json()["handle"] == "alice_new"
    assert r.json()["description"] == "about me"


async def test_handle_conflicts(make_client, client):
    alice, bob = await make_client("alice"), await make_client("bob")

    assert (await bob.patch("/api/channels/me", json={"handle": "alice"})).status_code == 409
    assert (await bob.patch("/api/channels/me", json={"handle": "ALICE"})).status_code == 409
    # смена регистра своего handle разрешена
    assert (await alice.patch("/api/channels/me", json={"handle": "Alice"})).status_code == 200

    # alice освободила handle, но username "alice" всё ещё её: занять его нельзя
    await alice.patch("/api/channels/me", json={"handle": "alice_new"})
    assert (await bob.patch("/api/channels/me", json={"handle": "alice"})).status_code == 409
    # и наоборот: чужой handle нельзя взять username'ом при регистрации
    r = await client.post(
        "/api/auth/register",
        json={"email": "x@example.com", "username": "alice_new", "password": PASSWORD},
    )
    assert r.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [{"handle": "a b"}, {"handle": "ab"}, {"name": ""}, {"name": "x" * 101}, {"description": "x" * 5001}],
)
async def test_update_channel_validation(make_client, payload):
    alice = await make_client("alice")
    assert (await alice.patch("/api/channels/me", json=payload)).status_code == 422


async def test_update_channel_requires_auth(client):
    assert (await client.patch("/api/channels/me", json={"name": "x"})).status_code == 401


async def test_subscribe_flow(make_client, client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    url = "/api/channels/alice/subscription"

    assert (await bob.put(url)).json() == {"subscribed": True, "subscribers_count": 1}
    assert (await bob.put(url)).json() == {"subscribed": True, "subscribers_count": 1}  # идемпотентно

    assert (await bob.get("/api/channels/alice")).json()["is_subscribed"] is True
    assert (await client.get("/api/channels/alice")).json()["is_subscribed"] is False
    assert (await client.get("/api/channels/alice")).json()["subscribers_count"] == 1

    video = await make_video("alice")
    detail = (await bob.get(f"/api/videos/{video.id}")).json()
    assert detail["subscribers_count"] == 1
    assert detail["is_subscribed"] is True

    assert (await bob.delete(url)).json() == {"subscribed": False, "subscribers_count": 0}
    assert (await bob.delete(url)).json() == {"subscribed": False, "subscribers_count": 0}


async def test_subscribe_errors(make_client, client):
    alice = await make_client("alice")
    assert (await alice.put("/api/channels/alice/subscription")).status_code == 400  # на себя
    assert (await alice.put("/api/channels/nobody/subscription")).status_code == 404
    assert (await client.put("/api/channels/alice/subscription")).status_code == 401
    assert (await client.delete("/api/channels/alice/subscription")).status_code == 401


# --- управление видео ---


async def test_my_videos(make_client, client, make_video):
    alice = await make_client("alice")
    await make_client("bob")
    created = [
        (await make_video("alice", status=VideoStatus.pending)).id,
        (await make_video("alice", visibility=Visibility.private)).id,
        (await make_video("alice", hidden=True)).id,
    ]
    await make_video("bob")

    first = (await alice.get("/api/videos/mine", params={"limit": 2})).json()
    assert [v["id"] for v in first["items"]] == created[::-1][:2]
    second = (await alice.get("/api/videos/mine", params={"limit": 2, "cursor": first["next_cursor"]})).json()
    assert [v["id"] for v in second["items"]] == created[::-1][2:]
    assert second["next_cursor"] is None
    assert (await client.get("/api/videos/mine")).status_code == 401


async def test_update_video(make_client, make_video):
    alice = await make_client("alice")
    video = await make_video("alice", visibility=Visibility.public)

    r = await alice.patch(
        f"/api/videos/{video.id}",
        json={"title": "  New title ", "description": "d", "visibility": "unlisted"},
    )
    assert r.status_code == 200
    body = r.json()
    assert (body["title"], body["description"], body["visibility"]) == ("New title", "d", "unlisted")

    assert (await alice.patch(f"/api/videos/{video.id}", json={})).json()["title"] == "New title"


@pytest.mark.parametrize(
    "payload",
    [{"title": ""}, {"title": "x" * 101}, {"visibility": "secret"}, {"description": "x" * 5001}],
)
async def test_update_video_validation(make_client, make_video, payload):
    alice = await make_client("alice")
    video = await make_video("alice")
    assert (await alice.patch(f"/api/videos/{video.id}", json=payload)).status_code == 422


async def test_update_video_permissions(make_client, client, make_video, set_role):
    alice, bob = await make_client("alice"), await make_client("bob")
    mod, root = await make_client("mod"), await make_client("root")
    await set_role("mod", Role.moderator)
    await set_role("root", Role.admin)
    video = await make_video("alice")
    url = f"/api/videos/{video.id}"

    for denied in (bob, mod):
        assert (await denied.patch(url, json={"title": "hacked"})).status_code == 404
    assert (await client.patch(url, json={"title": "hacked"})).status_code == 401
    assert (await alice.get(url)).json()["title"] == "Test video"
    assert (await root.patch(url, json={"title": "by admin"})).status_code == 200


async def test_delete_video_removes_everything(make_client, make_video, db):
    from sqlalchemy import func, select, update

    from app.models import Comment, Video
    from app.storage import get_storage

    alice = await make_client("alice")
    video = await make_video("alice")
    storage = get_storage()
    for key in (f"videos/{video.id}/720.mp4", f"videos/{video.id}/thumb.jpg", "originals/abc"):
        storage.local_path(key, for_write=True).write_bytes(b"x")
    await db.execute(update(Video).where(Video.id == video.id).values(original_path="originals/abc"))
    await db.commit()
    await alice.post(f"/api/videos/{video.id}/comments", json={"text": "hi"})

    assert (await alice.delete(f"/api/videos/{video.id}")).status_code == 204

    assert (await alice.get(f"/api/videos/{video.id}")).status_code == 404
    assert not storage.local_path("originals/abc").exists()
    assert not storage.local_path(f"videos/{video.id}").exists()
    assert (await db.execute(select(func.count()).select_from(Comment))).scalar_one() == 0
    assert (await alice.delete(f"/api/videos/{video.id}")).status_code == 404


async def test_delete_pending_video(make_client, make_video):
    alice = await make_client("alice")
    video = await make_video("alice", status=VideoStatus.pending)
    assert (await alice.delete(f"/api/videos/{video.id}")).status_code == 204


async def test_delete_video_permissions(make_client, client, make_video, set_role):
    alice, bob = await make_client("alice"), await make_client("bob")
    mod, root = await make_client("mod"), await make_client("root")
    await set_role("mod", Role.moderator)
    await set_role("root", Role.admin)
    video = await make_video("alice")
    url = f"/api/videos/{video.id}"

    for denied in (bob, mod):
        assert (await denied.delete(url)).status_code == 404
    assert (await client.delete(url)).status_code == 401
    assert (await alice.get(url)).status_code == 200  # ничего не удалилось
    assert (await root.delete(url)).status_code == 204
    assert (await client.delete("/api/videos/99999999999")).status_code in (401, 422)