from sqlalchemy import func, select

from app.models import Role, Visibility, WatchHistory


async def view(client, video_id):
    r = await client.post(f"/api/videos/{video_id}/view")
    assert r.status_code == 200, r.text


async def history(client, **params):
    r = await client.get("/api/history", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def ids(page):
    return [v["id"] for v in page["items"]]


async def test_view_records_history(make_client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")

    assert ids(await history(bob)) == []
    await view(bob, video.id)
    page = await history(bob)
    assert ids(page) == [video.id]
    assert (page["items"][0]["channel"]["handle"], page["next_cursor"]) == ("alice", None)


async def test_anonymous_view_is_not_recorded(make_client, client, make_video, db):
    await make_client("alice")
    video = await make_video("alice")
    await view(client, video.id)
    assert (await db.execute(select(func.count()).select_from(WatchHistory))).scalar_one() == 0


async def test_order_and_rewatch_moves_to_top(make_client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    v1, v2, v3 = (
        await make_video("alice"),
        await make_video("alice"),
        await make_video("alice"),
    )

    for video in (v1, v2, v3):
        await view(bob, video.id)
    assert ids(await history(bob)) == [v3.id, v2.id, v1.id]

    await view(bob, v1.id)  # повторный просмотр: наверх, без дубля
    assert ids(await history(bob)) == [v1.id, v3.id, v2.id]


async def test_pagination(make_client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    created = []
    for _ in range(5):
        created.append((await make_video("alice")).id)
        await view(bob, created[-1])

    seen, cursor = [], None
    for expected_len in (2, 2, 1):
        params = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        page = await history(bob, **params)
        assert len(page["items"]) == expected_len
        seen += ids(page)
        cursor = page["next_cursor"]
    assert cursor is None
    assert seen == created[::-1]


async def test_requires_auth_and_validates_ids(make_client, client):
    alice = await make_client("alice")
    for method, url in [
        ("GET", "/api/history"),
        ("DELETE", "/api/history"),
        ("DELETE", "/api/history/1"),
    ]:
        assert (await client.request(method, url)).status_code == 401
    assert (await alice.delete("/api/history/99999999999")).status_code == 422
    assert (await alice.get("/api/history", params={"limit": 0})).status_code == 422
    assert (await alice.get("/api/history", params={"cursor": 0})).status_code == 422


async def test_remove_one_and_clear(make_client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    v1, v2 = await make_video("alice"), await make_video("alice")
    await view(bob, v1.id)
    await view(bob, v2.id)

    assert (await bob.delete(f"/api/history/{v1.id}")).status_code == 204
    assert (await bob.delete(f"/api/history/{v1.id}")).status_code == 204  # идемпотентно
    assert (await bob.delete("/api/history/99999")).status_code == 204
    assert ids(await history(bob)) == [v2.id]

    assert (await bob.delete("/api/history")).status_code == 204
    assert ids(await history(bob)) == []


async def test_history_is_per_user(make_client, make_video):
    alice, bob = await make_client("alice"), await make_client("bob")
    video = await make_video("alice")
    await view(alice, video.id)
    await view(bob, video.id)

    assert (await bob.delete("/api/history")).status_code == 204
    assert ids(await history(bob)) == []
    assert ids(await history(alice)) == [video.id]  # чужая очистка не задела


async def test_video_closed_by_owner_disappears(make_client, make_video):
    alice, bob = await make_client("alice"), await make_client("bob")
    video = await make_video("alice")
    url = f"/api/videos/{video.id}"
    await view(bob, video.id)

    assert (await alice.patch(url, json={"visibility": "private"})).status_code == 200
    assert ids(await history(bob)) == []
    assert (await alice.patch(url, json={"visibility": "unlisted"})).status_code == 200
    assert ids(await history(bob)) == [video.id]  # строка не терялась: видео снова доступно


async def test_private_video_follows_shares(make_client, make_video):
    alice, bob = await make_client("alice"), await make_client("bob")
    bob_id = (await bob.get("/api/auth/me")).json()["id"]
    video = await make_video("alice", visibility=Visibility.private)
    await alice.post(f"/api/videos/{video.id}/shares", json={"username": "bob"})
    await view(bob, video.id)
    assert ids(await history(bob)) == [video.id]

    await alice.delete(f"/api/videos/{video.id}/shares/{bob_id}")
    assert ids(await history(bob)) == []


async def test_owner_keeps_own_private_video(make_client, make_video):
    alice = await make_client("alice")
    video = await make_video("alice", visibility=Visibility.private)
    await view(alice, video.id)
    assert ids(await history(alice)) == [video.id]


async def test_moderation_hidden_video_disappears(make_client, make_video, set_role):
    await make_client("alice")
    bob, mod = await make_client("bob"), await make_client("mod")
    await set_role("mod", Role.moderator)
    video = await make_video("alice")
    await view(bob, video.id)

    await mod.post(f"/api/moderation/videos/{video.id}/hide")
    assert ids(await history(bob)) == []
    await mod.post(f"/api/moderation/videos/{video.id}/unhide")
    assert ids(await history(bob)) == [video.id]


async def test_hidden_channel_video_disappears(make_client, make_video):
    alice, bob = await make_client("alice"), await make_client("bob")
    video = await make_video("alice")
    await view(bob, video.id)

    assert (await alice.patch("/api/channels/me", json={"is_hidden": True})).status_code == 200
    assert ids(await history(bob)) == []
    await alice.patch("/api/channels/me", json={"is_hidden": False})
    assert ids(await history(bob)) == [video.id]


async def test_deleting_video_removes_it_from_history(make_client, make_video, db):
    alice, bob = await make_client("alice"), await make_client("bob")
    video = await make_video("alice")
    await view(bob, video.id)

    assert (await alice.delete(f"/api/videos/{video.id}")).status_code == 204
    assert ids(await history(bob)) == []
    assert (await db.execute(select(func.count()).select_from(WatchHistory))).scalar_one() == 0