from app.models import Role, Visibility


async def post(client, video_id, text="hello", parent_id=None):
    payload = {"text": text}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    r = await client.post(f"/api/videos/{video_id}/comments", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def count(client, video_id) -> int:
    r = await client.get(f"/api/videos/{video_id}/comments/count")
    assert r.status_code == 200, r.text
    return r.json()["count"]


async def test_count_includes_replies(make_client, client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")
    assert await count(client, video.id) == 0

    top = await post(bob, video.id)
    reply = await post(bob, video.id, parent_id=top["id"])
    await post(bob, video.id, parent_id=reply["id"])  # ответ на ответ тоже считается
    await post(bob, video.id)
    assert await count(client, video.id) == 4  # аноним видит то же самое
    assert await count(bob, video.id) == 4


async def test_count_follows_deletes(make_client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")
    top = await post(bob, video.id)
    await post(bob, video.id, parent_id=top["id"])
    await post(bob, video.id, parent_id=top["id"])
    other = await post(bob, video.id)
    assert await count(bob, video.id) == 4

    assert (await bob.delete(f"/api/comments/{top['id']}")).status_code == 204  # с ответами
    assert await count(bob, video.id) == 1
    assert (await bob.delete(f"/api/comments/{other['id']}")).status_code == 204
    assert await count(bob, video.id) == 0


async def test_count_per_video(make_client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    v1, v2 = await make_video("alice"), await make_video("alice")
    await post(bob, v1.id)
    await post(bob, v1.id)
    await post(bob, v2.id)
    assert (await count(bob, v1.id), await count(bob, v2.id)) == (2, 1)


async def test_hidden_comments_counted_only_for_author_and_staff(
    make_client, client, make_video, set_role
):
    await make_client("alice")
    bob, carol, mod = await make_client("bob"), await make_client("carol"), await make_client("mod")
    await set_role("mod", Role.moderator)
    video = await make_video("alice")
    bad = await post(bob, video.id, "bad words")
    await post(carol, video.id, "fine")
    await mod.post(f"/api/moderation/comments/{bad['id']}/hide")

    assert await count(client, video.id) == 1
    assert await count(carol, video.id) == 1
    assert await count(bob, video.id) == 2  # автор видит своё скрытое
    assert await count(mod, video.id) == 2

    await mod.post(f"/api/moderation/comments/{bad['id']}/unhide")
    assert await count(client, video.id) == 2


async def test_count_follows_video_access(make_client, client, make_video):
    alice, bob, carol = await make_client("alice"), await make_client("bob"), await make_client("carol")
    video = await make_video("alice", visibility=Visibility.private)
    await post(alice, video.id)
    await alice.post(f"/api/videos/{video.id}/shares", json={"username": "bob"})
    url = f"/api/videos/{video.id}/comments/count"

    assert (await alice.get(url)).json() == {"count": 1}
    assert (await bob.get(url)).json() == {"count": 1}
    for denied in (carol, client):
        assert (await denied.get(url)).status_code == 404
    assert (await client.get("/api/videos/99999/comments/count")).status_code == 404
    assert (await client.get("/api/videos/99999999999/comments/count")).status_code == 422