import pytest
from sqlalchemy import func, select, update

from app.models import PlaylistItem, Role, Video, VideoStatus, Visibility
from app.services import playlists as playlists_service


async def create_playlist(client, title="Mix", **extra):
    r = await client.post("/api/playlists", json={"title": title, **extra})
    assert r.status_code == 201, r.text
    return r.json()


async def add(client, playlist_id, video_id):
    return await client.put(f"/api/playlists/{playlist_id}/items/{video_id}")


def item_ids(response):
    return [v["id"] for v in response.json()["items"]]


async def test_create_playlist(make_client, client):
    alice = await make_client("alice")
    body = await create_playlist(alice, description="d")
    assert body["is_public"] is True
    assert body["items_count"] == 0
    assert body["cover_video_id"] is None
    assert body["channel"]["handle"] == "alice"
    assert (await client.post("/api/playlists", json={"title": "x"})).status_code == 401


@pytest.mark.parametrize(
    "payload", [{"title": ""}, {"title": "x" * 101}, {"title": "ok", "description": "x" * 5001}]
)
async def test_create_validation(make_client, payload):
    alice = await make_client("alice")
    assert (await alice.post("/api/playlists", json=payload)).status_code == 422


async def test_items_add_remove_and_order(make_client, client, make_video):
    alice, _ = await make_client("alice"), await make_client("bob")
    v1, v2 = await make_video("alice"), await make_video("bob")
    pl = await create_playlist(alice)

    assert (await add(alice, pl["id"], v1.id)).status_code == 204
    assert (await add(alice, pl["id"], v2.id)).status_code == 204
    assert (await add(alice, pl["id"], v2.id)).status_code == 204  # идемпотентно

    detail = await client.get(f"/api/playlists/{pl['id']}")
    assert item_ids(detail) == [v1.id, v2.id]
    assert detail.json()["items_count"] == 2
    assert detail.json()["cover_video_id"] == v1.id
    assert detail.json()["is_owner"] is False

    assert (await alice.delete(f"/api/playlists/{pl['id']}/items/{v1.id}")).status_code == 204
    assert (await alice.delete(f"/api/playlists/{pl['id']}/items/{v1.id}")).status_code == 204
    assert item_ids(await alice.get(f"/api/playlists/{pl['id']}")) == [v2.id]


async def test_items_are_filtered_by_viewer(make_client, client, make_video):
    alice, _ = await make_client("alice"), await make_client("bob")
    own_private = await make_video("alice", visibility=Visibility.private)
    bob_public = await make_video("bob")
    pl = await create_playlist(alice)
    await add(alice, pl["id"], own_private.id)
    await add(alice, pl["id"], bob_public.id)
    url = f"/api/playlists/{pl['id']}"

    owner_view = (await alice.get(url)).json()
    assert [v["id"] for v in owner_view["items"]] == [own_private.id, bob_public.id]
    assert owner_view["items_count"] == 2
    assert owner_view["is_owner"] is True

    anon_view = (await client.get(url)).json()
    assert [v["id"] for v in anon_view["items"]] == [bob_public.id]
    assert anon_view["items_count"] == 1
    assert anon_view["cover_video_id"] == bob_public.id


@pytest.mark.parametrize(
    "values", [{"visibility": Visibility.private}, {"hidden_by_moderation": True}]
)
async def test_items_vanish_when_video_gets_restricted(make_client, client, make_video, db, values):
    alice, _ = await make_client("alice"), await make_client("bob")
    video = await make_video("bob")
    pl = await create_playlist(alice)
    await add(alice, pl["id"], video.id)
    url = f"/api/playlists/{pl['id']}"
    assert item_ids(await client.get(url)) == [video.id]

    await db.execute(update(Video).where(Video.id == video.id).values(**values))
    await db.commit()

    for viewer in (alice, client):
        detail = await viewer.get(url)
        assert item_ids(detail) == []
        assert detail.json()["items_count"] == 0
        assert detail.json()["cover_video_id"] is None


async def test_add_rules(make_client, make_video):
    alice, bob, _ = await make_client("alice"), await make_client("bob"), await make_client("carol")
    pl = await create_playlist(alice)

    carol_private = await make_video("carol", visibility=Visibility.private)
    assert (await add(alice, pl["id"], carol_private.id)).status_code == 404  # не видит

    bob_unlisted = await make_video("bob", visibility=Visibility.unlisted)
    assert (await add(alice, pl["id"], bob_unlisted.id)).status_code == 400  # видит, но класть нельзя

    own_pending = await make_video("alice", status=VideoStatus.uploaded)
    assert (await add(alice, pl["id"], own_pending.id)).status_code == 409

    assert (await add(alice, pl["id"], 99999)).status_code == 404
    assert (await add(alice, 99999, (await make_video("bob")).id)).status_code == 404

    own_unlisted = await make_video("alice", visibility=Visibility.unlisted)
    assert (await add(alice, pl["id"], own_unlisted.id)).status_code == 204  # свои любые
    assert (await bob.get(f"/api/playlists/{pl['id']}")).json()["items_count"] == 0


async def test_item_changes_are_owner_only(make_client, client, make_video, set_role):
    alice, bob, root = await make_client("alice"), await make_client("bob"), await make_client("root")
    await set_role("root", Role.admin)
    video = await make_video("alice")
    pl = await create_playlist(alice)
    await add(alice, pl["id"], video.id)

    for outsider in (bob, root):
        assert (await add(outsider, pl["id"], video.id)).status_code == 404
        assert (await outsider.delete(f"/api/playlists/{pl['id']}/items/{video.id}")).status_code == 404
    assert (await client.put(f"/api/playlists/{pl['id']}/items/{video.id}")).status_code == 401
    assert item_ids(await alice.get(f"/api/playlists/{pl['id']}")) == [video.id]


async def test_private_playlist(make_client, client, set_role):
    alice, bob, root = await make_client("alice"), await make_client("bob"), await make_client("root")
    await set_role("root", Role.admin)
    pl = await create_playlist(alice, title="secret", is_public=False)
    url = f"/api/playlists/{pl['id']}"

    assert (await alice.get(url)).status_code == 200
    for denied in (bob, root, client):
        assert (await denied.get(url)).status_code == 404

    own_list = (await alice.get("/api/channels/alice/playlists")).json()
    assert [p["id"] for p in own_list if p["kind"] == "regular"] == [pl["id"]]
    for viewer in (bob, client):
        assert (await viewer.get("/api/channels/alice/playlists")).json() == []
    assert (await client.get("/api/channels/nobody/playlists")).status_code == 404


async def test_update_and_delete_playlist(make_client, client, make_video, set_role, db):
    alice, bob = await make_client("alice"), await make_client("bob")
    mod, root = await make_client("mod"), await make_client("root")
    await set_role("mod", Role.moderator)
    await set_role("root", Role.admin)
    video = await make_video("alice")
    pl = await create_playlist(alice)
    await add(alice, pl["id"], video.id)
    url = f"/api/playlists/{pl['id']}"

    r = await alice.patch(url, json={"title": "Renamed", "is_public": False})
    assert r.status_code == 200
    assert (r.json()["title"], r.json()["is_public"]) == ("Renamed", False)

    for denied in (bob, mod):
        assert (await denied.patch(url, json={"title": "x"})).status_code == 404
        assert (await denied.delete(url)).status_code == 404
    assert (await client.delete(url)).status_code == 401
    assert (await root.patch(url, json={"title": "by admin"})).status_code == 200

    assert (await alice.delete(url)).status_code == 204
    assert (await alice.get(url)).status_code == 404
    assert (await db.execute(select(func.count()).select_from(PlaylistItem))).scalar_one() == 0


async def test_my_playlists_with_contains(make_client, client, make_video):
    alice, bob = await make_client("alice"), await make_client("bob")
    video = await make_video("alice")
    with_video = await create_playlist(alice, "with")
    without = await create_playlist(alice, "without")
    await create_playlist(bob, "bobs")
    await add(alice, with_video["id"], video.id)

    r = await alice.get("/api/playlists/mine", params={"video_id": video.id})
    assert r.status_code == 200  # "mine" не уходит в /{playlist_id}
    flags = {p["id"]: p["contains"] for p in r.json() if p["kind"] == "regular"}
    assert flags == {with_video["id"]: True, without["id"]: False}

    assert {p["contains"] for p in (await alice.get("/api/playlists/mine")).json()} == {False}
    assert (await client.get("/api/playlists/mine")).status_code == 401


async def test_limits(make_client, make_video, monkeypatch):
    alice = await make_client("alice")
    monkeypatch.setattr(playlists_service, "MAX_PLAYLISTS", 2)
    monkeypatch.setattr(playlists_service, "MAX_ITEMS", 1)

    first = await create_playlist(alice, "1")
    await create_playlist(alice, "2")
    assert (await alice.post("/api/playlists", json={"title": "3"})).status_code == 409

    v1, v2 = await make_video("alice"), await make_video("alice")
    assert (await add(alice, first["id"], v1.id)).status_code == 204
    assert (await add(alice, first["id"], v2.id)).status_code == 409


async def test_huge_ids_are_422(make_client):
    alice = await make_client("alice")
    assert (await alice.get("/api/playlists/99999999999")).status_code == 422
    assert (await alice.put("/api/playlists/1/items/99999999999")).status_code == 422
    assert (await alice.get("/api/playlists/mine", params={"video_id": 0})).status_code == 422