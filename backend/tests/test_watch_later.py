import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Playlist, PlaylistKind, Role, User, VideoStatus, Visibility
from app.services import playlists as playlists_service


async def watch_later(client):
    r = await client.get("/api/playlists/watch-later")
    assert r.status_code == 200, r.text
    return r.json()


async def user_id(db, username) -> int:
    return (await db.execute(select(User.id).where(User.username == username))).scalar_one()


async def test_created_lazily_and_private(make_client, client):
    alice = await make_client("alice")
    body = await watch_later(alice)
    assert (body["kind"], body["title"], body["visibility"]) == ("watch_later", "Смотреть позже", "private")
    assert (body["items"], body["items_count"], body["is_owner"]) == ([], 0, True)
    assert (await client.get("/api/playlists/watch-later")).status_code == 401


async def test_created_only_once(make_client, db):
    alice = await make_client("alice")
    first, second = await watch_later(alice), await watch_later(alice)
    await alice.get("/api/playlists/mine")
    await alice.get("/api/channels/alice/playlists")
    assert first["id"] == second["id"]
    stmt = select(func.count()).select_from(Playlist).where(Playlist.kind == PlaylistKind.watch_later)
    assert (await db.execute(stmt)).scalar_one() == 1


async def test_listed_first_and_hidden_from_others(make_client, client, make_video):
    alice, bob = await make_client("alice"), await make_client("bob")
    video = await make_video("alice")
    mix = (await alice.post("/api/playlists", json={"title": "Mix"})).json()  # создан раньше «Смотреть позже»
    wl = await watch_later(alice)
    assert (await alice.put(f"/api/playlists/{wl['id']}/items/{video.id}")).status_code == 204

    mine = (await alice.get("/api/playlists/mine")).json()
    assert [p["kind"] for p in mine] == ["watch_later", "regular"]
    own = (await alice.get("/api/channels/alice/playlists")).json()
    assert [p["kind"] for p in own] == ["watch_later", "regular"]

    for viewer in (bob, client):
        shown = (await viewer.get("/api/channels/alice/playlists")).json()
        assert [p["id"] for p in shown] == [mix["id"]]


async def test_empty_watch_later_hidden_on_channel_but_present_in_save_dialog(make_client):
    alice = await make_client("alice")
    assert (await alice.get("/api/channels/alice/playlists")).json() == []
    mine = (await alice.get("/api/playlists/mine")).json()
    assert [p["kind"] for p in mine] == ["watch_later"]  # в окне «Сохранить» есть всегда


async def test_add_and_remove_items(make_client, make_video):
    alice, _ = await make_client("alice"), await make_client("bob")
    own_private = await make_video("alice", visibility=Visibility.private)
    bob_public = await make_video("bob")
    bob_unlisted = await make_video("bob", visibility=Visibility.unlisted)
    url = f"/api/playlists/{(await watch_later(alice))['id']}"

    assert (await alice.put(f"{url}/items/{own_private.id}")).status_code == 204
    assert (await alice.put(f"{url}/items/{bob_public.id}")).status_code == 204
    assert (await alice.put(f"{url}/items/{bob_unlisted.id}")).status_code == 400  # правила как у обычных
    assert [v["id"] for v in (await watch_later(alice))["items"]] == [own_private.id, bob_public.id]

    assert (await alice.delete(f"{url}/items/{own_private.id}")).status_code == 204
    detail = await watch_later(alice)
    assert [v["id"] for v in detail["items"]] == [bob_public.id]
    assert detail["items_count"] == 1

    mine = (await alice.get("/api/playlists/mine", params={"video_id": bob_public.id})).json()
    assert {p["kind"]: p["contains"] for p in mine} == {"watch_later": True}


@pytest.mark.parametrize(
    "payload", [{"title": "Renamed"}, {"visibility": "public"}, {"description": "d"}]
)
async def test_cannot_be_modified_or_deleted(make_client, set_role, payload):
    alice, root = await make_client("alice"), await make_client("root")
    await set_role("root", Role.admin)
    url = f"/api/playlists/{(await watch_later(alice))['id']}"

    for who in (alice, root):  # даже админу нельзя
        assert (await who.patch(url, json=payload)).status_code == 400
        assert (await who.delete(url)).status_code == 400
    after = await watch_later(alice)
    assert (after["title"], after["visibility"]) == ("Смотреть позже", "private")


async def test_invisible_to_others(make_client, client, set_role):
    alice, bob, root = await make_client("alice"), await make_client("bob"), await make_client("root")
    await set_role("root", Role.admin)
    video_url = f"/api/playlists/{(await watch_later(alice))['id']}"

    for viewer in (bob, root, client):
        assert (await viewer.get(video_url)).status_code == 404
    for outsider in (bob, root):
        assert (await outsider.put(f"{video_url}/items/1")).status_code == 404


async def test_not_counted_in_playlist_limit(make_client, monkeypatch):
    alice = await make_client("alice")
    monkeypatch.setattr(playlists_service, "MAX_PLAYLISTS", 1)
    await watch_later(alice)
    assert (await alice.post("/api/playlists", json={"title": "1"})).status_code == 201
    assert (await alice.post("/api/playlists", json={"title": "2"})).status_code == 409


async def test_db_allows_one_watch_later_per_user(make_client, db):
    await make_client("alice")
    alice_id = await user_id(db, "alice")
    db.add(Playlist(owner_id=alice_id, title="a", visibility=Visibility.private, kind=PlaylistKind.watch_later))
    await db.commit()

    db.add(Playlist(owner_id=alice_id, title="b", visibility=Visibility.private, kind=PlaylistKind.watch_later))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_db_forbids_public_watch_later(make_client, db):
    await make_client("alice")
    db.add(
        Playlist(
            owner_id=await user_id(db, "alice"),
            title="a",
            visibility=Visibility.public,
            kind=PlaylistKind.watch_later,
        )
    )
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_quick_add_to_watch_later(make_client, client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")
    url = f"/api/playlists/watch-later/items/{video.id}"

    assert (await bob.put(url)).status_code == 204  # плейлист создаётся сам
    assert (await bob.put(url)).status_code == 204  # идемпотентно
    detail = await watch_later(bob)
    assert [v["id"] for v in detail["items"]] == [video.id]
    assert detail["items_count"] == 1
    assert (await client.put(url)).status_code == 401


async def test_quick_add_follows_playlist_rules(make_client, make_video):
    alice, bob = await make_client("alice"), await make_client("bob")
    own_private = await make_video("alice", visibility=Visibility.private)
    unlisted = await make_video("alice", visibility=Visibility.unlisted)
    unfinished = await make_video("bob", status=VideoStatus.uploaded)

    assert (await alice.put(f"/api/playlists/watch-later/items/{own_private.id}")).status_code == 204
    assert (await bob.put(f"/api/playlists/watch-later/items/{own_private.id}")).status_code == 404
    assert (await bob.put(f"/api/playlists/watch-later/items/{unlisted.id}")).status_code == 400
    assert (await bob.put(f"/api/playlists/watch-later/items/{unfinished.id}")).status_code == 409
    assert (await bob.put("/api/playlists/watch-later/items/99999")).status_code == 404
    assert (await bob.put("/api/playlists/watch-later/items/99999999999")).status_code == 422
    assert (await watch_later(bob))["items"] == []  # отказы ничего не добавили