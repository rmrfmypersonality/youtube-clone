from app.models import Visibility
from app.services import notifications as notifications_service


async def count(client) -> int:
    r = await client.get("/api/notifications/count")
    assert r.status_code == 200, r.text
    return r.json()["count"]


async def feed(client, **params):
    r = await client.get("/api/notifications", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def ids(page):
    return [v["id"] for v in page["items"]]


async def subscribe(client, handle):
    assert (await client.put(f"/api/channels/{handle}/subscription")).status_code == 200


async def test_new_video_of_subscribed_channel(make_client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    await subscribe(bob, "alice")
    assert await count(bob) == 0

    video = await make_video("alice")
    assert await count(bob) == 1
    page = await feed(bob)
    assert ids(page) == [video.id]
    assert page["items"][0]["published_at"]
    assert page["items"][0]["channel"]["handle"] == "alice"


async def test_only_subscribed_channels(make_client, make_video):
    await make_client("alice")
    await make_client("carol")
    bob = await make_client("bob")
    await subscribe(bob, "alice")
    await make_video("carol")
    assert await count(bob) == 0
    assert ids(await feed(bob)) == []


async def test_video_published_before_subscription_is_not_news(make_client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    await make_video("alice")
    await subscribe(bob, "alice")
    assert await count(bob) == 0
    assert ids(await feed(bob)) == []


async def test_unsubscribe_removes_notifications(make_client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    await subscribe(bob, "alice")
    await make_video("alice")
    assert await count(bob) == 1
    await bob.delete("/api/channels/alice/subscription")
    assert (await count(bob), ids(await feed(bob))) == (0, [])


async def test_only_public_visible_videos_count(make_client, make_video):
    alice = await make_client("alice")
    bob = await make_client("bob")
    await subscribe(bob, "alice")
    await make_video("alice", visibility=Visibility.unlisted)
    await make_video("alice", visibility=Visibility.private)
    await make_video("alice", hidden=True)
    shown = await make_video("alice")
    assert ids(await feed(bob)) == [shown.id]
    assert await count(bob) == 1

    await alice.patch("/api/channels/me", json={"is_hidden": True})
    assert (await count(bob), ids(await feed(bob))) == (0, [])
    await alice.patch("/api/channels/me", json={"is_hidden": False})
    assert await count(bob) == 1


async def test_seen_resets_counter_and_keeps_list(make_client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    await subscribe(bob, "alice")
    first = await make_video("alice")
    before = await feed(bob)

    assert (await bob.post("/api/notifications/seen")).status_code == 204
    assert await count(bob) == 0
    after = await feed(bob)
    assert ids(after) == [first.id]  # список остаётся
    assert after["seen_at"] > before["seen_at"]
    assert after["items"][0]["published_at"] <= after["seen_at"]  # фронт по этому поймёт, что оно не новое

    second = await make_video("alice")
    assert await count(bob) == 1
    assert ids(await feed(bob)) == [second.id, first.id]


async def test_seen_is_per_user(make_client, make_video):
    await make_client("alice")
    bob, carol = await make_client("bob"), await make_client("carol")
    await subscribe(bob, "alice")
    await subscribe(carol, "alice")
    await make_video("alice")
    await bob.post("/api/notifications/seen")
    assert (await count(bob), await count(carol)) == (0, 1)


async def test_pagination(make_client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    await subscribe(bob, "alice")
    created = [(await make_video("alice")).id for _ in range(5)]

    seen, cursor = [], None
    for expected_len in (2, 2, 1):
        params = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        page = await feed(bob, **params)
        assert len(page["items"]) == expected_len
        seen += ids(page)
        cursor = page["next_cursor"]
    assert cursor is None
    assert seen == created[::-1]


async def test_count_is_capped(make_client, make_video, monkeypatch):
    await make_client("alice")
    bob = await make_client("bob")
    await subscribe(bob, "alice")
    monkeypatch.setattr(notifications_service, "COUNT_CAP", 2)
    for _ in range(3):
        await make_video("alice")
    assert await count(bob) == 2


async def test_requires_auth_and_validates_params(make_client, client):
    alice = await make_client("alice")
    for method, url in [
        ("GET", "/api/notifications"),
        ("GET", "/api/notifications/count"),
        ("POST", "/api/notifications/seen"),
    ]:
        assert (await client.request(method, url)).status_code == 401
    assert (await alice.get("/api/notifications", params={"limit": 0})).status_code == 422
    assert (await alice.get("/api/notifications", params={"cursor": 0})).status_code == 422