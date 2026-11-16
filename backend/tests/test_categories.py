import pytest
from sqlalchemy import select

from app.models import AuditLog, Role


async def category_ids(client) -> dict[str, int]:
    return {c["slug"]: c["id"] for c in (await client.get("/api/categories")).json()}


def feed_ids(response):
    return [v["id"] for v in response.json()["items"]]


async def test_list_categories(client):
    r = await client.get("/api/categories")  # публичный, и справочник пережил очистку между тестами
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 10
    assert set(items[0]) == {"id", "slug", "name"}
    assert items[-1]["slug"] == "other"  # «Другое» всегда последняя
    assert len({c["slug"] for c in items}) == 10


async def test_create_with_category(make_client, client):
    alice = await make_client("alice")
    cats = await category_ids(client)

    r = await alice.post("/api/videos", json={"title": "x"})
    assert r.json()["category_id"] == cats["other"]  # по умолчанию
    r = await alice.post("/api/videos", json={"title": "x", "category_id": cats["music"]})
    assert (r.status_code, r.json()["category_id"]) == (201, cats["music"])


@pytest.mark.parametrize("value,status", [(99999, 400), (0, 422), (-1, 422), (99999999999, 422), ("x", 422)])
async def test_create_rejects_bad_category(make_client, value, status):
    alice = await make_client("alice")
    r = await alice.post("/api/videos", json={"title": "x", "category_id": value})
    assert r.status_code == status


async def test_update_category(make_client, client, make_video):
    alice = await make_client("alice")
    cats = await category_ids(client)
    video = await make_video("alice")
    url = f"/api/videos/{video.id}"

    r = await alice.patch(url, json={"category_id": cats["gaming"]})
    assert (r.status_code, r.json()["category_id"]) == (200, cats["gaming"])
    assert (await alice.patch(url, json={"title": "new"})).json()["category_id"] == cats["gaming"]
    assert (await alice.patch(url, json={"category_id": 99999})).status_code == 400
    assert (await alice.patch(url, json={"category_id": 0})).status_code == 422
    assert (await alice.get(f"/api/videos/mine")).json()["items"][0]["category_id"] == cats["gaming"]


async def test_category_change_by_admin_is_audited(make_client, client, make_video, set_role, db):
    await make_client("alice")
    root = await make_client("root")
    await set_role("root", Role.admin)
    cats = await category_ids(client)
    video = await make_video("alice")

    assert (await root.patch(f"/api/videos/{video.id}", json={"category_id": cats["news"]})).status_code == 200
    entry = (await db.execute(select(AuditLog))).scalar_one()
    assert entry.action == "video.update"
    assert entry.details["changed"] == ["category_id"]


async def test_feed_category_filter(make_client, client, make_video):
    await make_client("alice")
    music = await make_video("alice", category="music")
    other = await make_video("alice")

    assert feed_ids(await client.get("/api/videos", params={"category": "music"})) == [music.id]
    assert feed_ids(await client.get("/api/videos", params={"category": "other"})) == [other.id]
    assert set(feed_ids(await client.get("/api/videos"))) == {music.id, other.id}
    assert feed_ids(await client.get("/api/videos", params={"category": "nope"})) == []
    assert (await client.get("/api/videos", params={"category": "Bad Slug!"})).status_code == 422


async def test_feed_category_filter_pagination(make_client, client, make_video):
    await make_client("alice")
    created = [(await make_video("alice", category="sports")).id for _ in range(3)]
    await make_video("alice")

    first = (await client.get("/api/videos", params={"category": "sports", "limit": 2})).json()
    assert [v["id"] for v in first["items"]] == created[::-1][:2]
    second = (
        await client.get(
            "/api/videos",
            params={"category": "sports", "limit": 2, "cursor": first["next_cursor"]},
        )
    ).json()
    assert [v["id"] for v in second["items"]] == created[::-1][2:]
    assert second["next_cursor"] is None