from app.models import Visibility


async def test_subscription_list_sorted_by_name(make_client, client):
    bob = await make_client("bob")
    await make_client("alice")
    await make_client("carol")
    for handle in ("carol", "alice"):
        assert (await bob.put(f"/api/channels/{handle}/subscription")).status_code == 200

    r = await bob.get("/api/subscriptions")
    assert [c["handle"] for c in r.json()] == ["alice", "carol"]
    assert (await client.get("/api/subscriptions")).status_code == 401

    await bob.delete("/api/channels/alice/subscription")
    assert [c["handle"] for c in (await bob.get("/api/subscriptions")).json()] == ["carol"]


async def test_subscription_feed(make_client, client, make_video):
    bob = await make_client("bob")
    await make_client("alice")
    await make_client("carol")
    followed = [(await make_video("alice")).id for _ in range(3)]
    await make_video("alice", visibility=Visibility.private)
    await make_video("alice", visibility=Visibility.unlisted)
    await make_video("alice", hidden=True)
    await make_video("carol")  # не подписан
    await bob.put("/api/channels/alice/subscription")

    first = (await bob.get("/api/subscriptions/feed", params={"limit": 2})).json()
    assert [v["id"] for v in first["items"]] == followed[::-1][:2]
    second = (
        await bob.get(
            "/api/subscriptions/feed", params={"limit": 2, "cursor": first["next_cursor"]}
        )
    ).json()
    assert [v["id"] for v in second["items"]] == followed[::-1][2:]
    assert second["next_cursor"] is None
    assert (await client.get("/api/subscriptions/feed")).status_code == 401


async def test_subscription_feed_empty(make_client):
    bob = await make_client("bob")
    assert (await bob.get("/api/subscriptions/feed")).json() == {"items": [], "next_cursor": None}