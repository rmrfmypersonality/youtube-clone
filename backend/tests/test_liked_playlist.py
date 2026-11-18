import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Playlist, PlaylistKind, Role, User, Visibility


async def like(client, video_id, value=1):
    r = await client.put(f"/api/videos/{video_id}/reaction", json={"value": value})
    assert r.status_code == 200, r.text


async def liked(client):
    r = await client.get("/api/playlists/liked")
    assert r.status_code == 200, r.text
    return r.json()


async def liked_page(client, **params):
    r = await client.get("/api/playlists/liked/videos", params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def liked_ids(client):
    return [v["id"] for v in (await liked_page(client, limit=50))["items"]]


async def test_created_lazily_once_and_private(make_client, client, db):
    alice = await make_client("alice")
    body = await liked(alice)
    assert (body["kind"], body["title"], body["visibility"]) == ("liked", "Понравившиеся", "private")
    assert (body["items_count"], body["cover_video_id"]) == (0, None)
    assert (await liked(alice))["id"] == body["id"]
    stmt = select(func.count()).select_from(Playlist).where(Playlist.kind == PlaylistKind.liked)
    assert (await db.execute(stmt)).scalar_one() == 1
    assert (await client.get("/api/playlists/liked")).status_code == 401
    assert (await client.get("/api/playlists/liked/videos")).status_code == 401


async def test_order_cover_and_relike(make_client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    v1, v2, v3 = (
        await make_video("alice"),
        await make_video("alice"),
        await make_video("alice"),
    )
    for video in (v1, v2, v3):
        await like(bob, video.id)

    assert await liked_ids(bob) == [v3.id, v2.id, v1.id]
    body = await liked(bob)
    assert (body["items_count"], body["cover_video_id"]) == (3, v3.id)

    await like(bob, v3.id)  # повтор того же лайка не двигает видео
    assert await liked_ids(bob) == [v3.id, v2.id, v1.id]

    await like(bob, v1.id, -1)
    await like(bob, v1.id)  # лайк после дизлайка поднимает видео наверх
    assert await liked_ids(bob) == [v1.id, v3.id, v2.id]
    assert (await liked(bob))["cover_video_id"] == v1.id


async def test_only_likes_count(make_client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    kept, disliked, removed = (
        await make_video("alice"),
        await make_video("alice"),
        await make_video("alice"),
    )
    await like(bob, kept.id)
    await like(bob, disliked.id, -1)
    await like(bob, removed.id)
    await like(bob, removed.id, 0)

    assert await liked_ids(bob) == [kept.id]
    assert (await liked(bob))["items_count"] == 1


async def test_pagination(make_client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    created = []
    for _ in range(5):
        created.append((await make_video("alice")).id)
        await like(bob, created[-1])

    seen, cursor = [], None
    for expected_len in (2, 2, 1):
        params = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        page = await liked_page(bob, **params)
        assert len(page["items"]) == expected_len
        seen += [v["id"] for v in page["items"]]
        cursor = page["next_cursor"]
    assert cursor is None
    assert seen == created[::-1]
    assert (await bob.get("/api/playlists/liked/videos", params={"cursor": 0})).status_code == 422


async def test_closed_videos_disappear_and_return(make_client, make_video, set_role):
    alice, bob, mod = await make_client("alice"), await make_client("bob"), await make_client("mod")
    await set_role("mod", Role.moderator)
    video = await make_video("alice")
    await like(bob, video.id)
    url = f"/api/videos/{video.id}"

    async def state():
        body = await liked(bob)
        return await liked_ids(bob), body["items_count"], body["cover_video_id"]

    assert await state() == ([video.id], 1, video.id)

    await alice.patch(url, json={"visibility": "private"})
    assert await state() == ([], 0, None)
    await alice.patch(url, json={"visibility": "unlisted"})
    assert await state() == ([video.id], 1, video.id)

    await mod.post(f"/api/moderation/videos/{video.id}/hide")
    assert await state() == ([], 0, None)
    await mod.post(f"/api/moderation/videos/{video.id}/unhide")
    assert await state() == ([video.id], 1, video.id)

    await alice.patch("/api/channels/me", json={"is_hidden": True})
    assert await state() == ([], 0, None)
    await alice.patch("/api/channels/me", json={"is_hidden": False})
    assert await state() == ([video.id], 1, video.id)


async def test_owner_keeps_own_private_video(make_client, make_video):
    alice = await make_client("alice")
    video = await make_video("alice", visibility=Visibility.private)
    await like(alice, video.id)
    assert await liked_ids(alice) == [video.id]


async def test_channel_tab_and_save_dialog(make_client, client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")

    def kinds(response):
        return [p["kind"] for p in response.json()]

    assert kinds(await bob.get("/api/channels/bob/playlists")) == []  # пустые встроенные скрыты
    await like(bob, video.id)
    assert kinds(await bob.get("/api/channels/bob/playlists")) == ["liked"]

    wl = (await bob.get("/api/playlists/watch-later")).json()
    await bob.put(f"/api/playlists/{wl['id']}/items/{video.id}")
    await bob.post("/api/playlists", json={"title": "Mix", "visibility": "private"})
    assert kinds(await bob.get("/api/channels/bob/playlists")) == ["watch_later", "liked", "regular"]

    assert kinds(await bob.get("/api/playlists/mine")) == ["watch_later", "regular"]  # liked в окне нет
    assert (await client.get("/api/channels/bob/playlists")).json() == []  # чужим системные не видны


async def test_cannot_be_modified_deleted_or_filled_by_hand(make_client, make_video, set_role):
    await make_client("alice")
    bob, root = await make_client("bob"), await make_client("root")
    await set_role("root", Role.admin)
    video = await make_video("alice")
    url = f"/api/playlists/{(await liked(bob))['id']}"

    for payload in ({"title": "Renamed"}, {"visibility": "public"}, {"description": "d"}):
        for who in (bob, root):  # даже админу нельзя
            assert (await who.patch(url, json=payload)).status_code == 400
    for who in (bob, root):
        assert (await who.delete(url)).status_code == 400
    assert (await bob.put(f"{url}/items/{video.id}")).status_code == 400
    assert (await bob.delete(f"{url}/items/{video.id}")).status_code == 400

    after = await liked(bob)
    assert (after["title"], after["visibility"]) == ("Понравившиеся", "private")


async def test_invisible_to_others(make_client, client, set_role):
    alice, bob, root = await make_client("alice"), await make_client("bob"), await make_client("root")
    await set_role("root", Role.admin)
    url = f"/api/playlists/{(await liked(bob))['id']}"
    for viewer in (alice, root, client):
        assert (await viewer.get(url)).status_code == 404
        assert (await viewer.get(url + "/random")).status_code == 404
    assert (await liked(alice))["id"] != (await liked(bob))["id"]  # у каждого свой


async def test_playlist_detail_reads_likes(make_client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    v1, v2 = await make_video("alice"), await make_video("alice")
    await like(bob, v1.id)
    await like(bob, v2.id)

    detail = (await bob.get(f"/api/playlists/{(await liked(bob))['id']}")).json()
    assert [v["id"] for v in detail["items"]] == [v2.id, v1.id]
    assert (detail["items_count"], detail["is_owner"]) == (2, True)


async def test_random_video(make_client, client, make_video):
    alice, bob = await make_client("alice"), await make_client("bob")
    pl_url = f"/api/playlists/{(await liked(bob))['id']}/random"
    assert (await bob.get(pl_url)).json() == {"video_id": None}  # пусто

    videos = [await make_video("alice") for _ in range(3)]
    for video in videos:
        await like(bob, video.id)
    seen = {(await bob.get(pl_url)).json()["video_id"] for _ in range(15)}
    assert seen and seen <= {v.id for v in videos}

    # обычный плейлист: случайное из доступных, аноним тоже может, если плейлист открыт
    pl = (await alice.post("/api/playlists", json={"title": "Mix", "visibility": "public"})).json()
    await alice.put(f"/api/playlists/{pl['id']}/items/{videos[0].id}")
    assert (await client.get(f"/api/playlists/{pl['id']}/random")).json() == {"video_id": videos[0].id}
    assert (await client.get("/api/playlists/99999/random")).status_code == 404
    assert (await client.get("/api/playlists/99999999999/random")).status_code == 422


async def test_random_respects_visibility(make_client, make_video):
    alice, bob = await make_client("alice"), await make_client("bob")
    video = await make_video("alice")
    await like(bob, video.id)
    url = f"/api/playlists/{(await liked(bob))['id']}/random"
    assert (await bob.get(url)).json() == {"video_id": video.id}
    await alice.patch(f"/api/videos/{video.id}", json={"visibility": "private"})
    assert (await bob.get(url)).json() == {"video_id": None}


async def _user_id(db, username) -> int:
    return (await db.execute(select(User.id).where(User.username == username))).scalar_one()


async def test_db_allows_one_liked_per_user(make_client, db):
    await make_client("alice")
    uid = await _user_id(db, "alice")
    db.add(Playlist(owner_id=uid, title="a", visibility=Visibility.private, kind=PlaylistKind.liked))
    await db.commit()
    db.add(Playlist(owner_id=uid, title="b", visibility=Visibility.private, kind=PlaylistKind.liked))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_db_forbids_public_liked(make_client, db):
    await make_client("alice")
    db.add(
        Playlist(
            owner_id=await _user_id(db, "alice"),
            title="a",
            visibility=Visibility.public,
            kind=PlaylistKind.liked,
        )
    )
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()