import pytest

from app.models import Role, Visibility


async def post(client, video_id, text="hello"):
    r = await client.post(f"/api/videos/{video_id}/comments", json={"text": text})
    assert r.status_code == 201, r.text
    return r.json()


async def react(client, comment_id, value):
    return await client.put(f"/api/comments/{comment_id}/reaction", json={"value": value})


async def listing(client, video_id, **params):
    r = await client.get(f"/api/videos/{video_id}/comments", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def ids(page):
    return [c["id"] for c in page["items"]]


async def test_like_dislike_and_toggle(make_client, client, make_video):
    await make_client("alice")
    bob, carol = await make_client("bob"), await make_client("carol")
    video = await make_video("alice")
    comment = await post(bob, video.id)
    assert (comment["likes_count"], comment["my_reaction"]) == (0, 0)

    assert (await react(carol, comment["id"], 1)).json() == {"likes_count": 1, "my_reaction": 1}
    assert (await react(carol, comment["id"], 1)).json() == {"likes_count": 1, "my_reaction": 1}  # повтор
    assert (await react(bob, comment["id"], 1)).json() == {"likes_count": 2, "my_reaction": 1}  # свой можно
    assert (await react(carol, comment["id"], -1)).json() == {"likes_count": 1, "my_reaction": -1}
    assert (await react(carol, comment["id"], 0)).json() == {"likes_count": 1, "my_reaction": 0}

    mine = (await listing(bob, video.id))["items"][0]
    assert (mine["likes_count"], mine["my_reaction"]) == (1, 1)
    other = (await listing(carol, video.id))["items"][0]
    assert (other["likes_count"], other["my_reaction"]) == (1, 0)
    anon = (await listing(client, video.id))["items"][0]
    assert (anon["likes_count"], anon["my_reaction"]) == (1, 0)


async def test_replies_carry_reactions(make_client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")
    top = await post(bob, video.id)
    reply = (
        await bob.post(
            f"/api/videos/{video.id}/comments", json={"text": "r", "parent_id": top["id"]}
        )
    ).json()
    await react(bob, reply["id"], 1)

    item = (await bob.get(f"/api/comments/{top['id']}/replies")).json()["items"][0]
    assert (item["likes_count"], item["my_reaction"]) == (1, 1)


async def test_popular_sort_and_composite_cursor(make_client, make_video):
    alice, bob, carol = await make_client("alice"), await make_client("bob"), await make_client("carol")
    video = await make_video("alice")
    c1 = await post(bob, video.id, "c1")
    c2 = await post(bob, video.id, "c2")
    c3 = await post(bob, video.id, "c3")
    c4 = await post(bob, video.id, "c4")
    for liker in (alice, bob):
        await react(liker, c1["id"], 1)  # 2 лайка
    await react(carol, c3["id"], 1)  # 1 лайк
    await react(carol, c4["id"], 1)  # 1 лайк
    await react(alice, c2["id"], -1)  # дизлайк лайком не считается

    # лайки по убыванию, при равенстве новые выше: c1 (2), c4 (1), c3 (1), c2 (0)
    full = await listing(bob, video.id, sort="popular", limit=50)
    assert ids(full) == [c1["id"], c4["id"], c3["id"], c2["id"]]

    first = await listing(bob, video.id, sort="popular", limit=2)
    assert ids(first) == [c1["id"], c4["id"]]
    assert first["next_cursor"] == f"1_{c4['id']}"
    second = await listing(bob, video.id, sort="popular", limit=2, cursor=first["next_cursor"])
    assert ids(second) == [c3["id"], c2["id"]]
    assert second["next_cursor"] is None

    # сортировка new по-прежнему по id
    assert ids(await listing(bob, video.id, sort="new")) == [c4["id"], c3["id"], c2["id"], c1["id"]]


@pytest.mark.parametrize(
    "sort,cursor",
    [
        ("popular", "5"),  # курсор от new
        ("new", "5_6"),  # курсор от popular
        ("popular", "5_6_7"),
        ("popular", "a_b"),
        ("popular", "5_0"),
        ("new", "0"),
        ("popular", "9999999999_1"),  # вне диапазона int32
        ("new", "9999999999"),
    ],
)
async def test_bad_cursor_is_422(make_client, client, make_video, sort, cursor):
    await make_client("alice")
    video = await make_video("alice")
    r = await client.get(
        f"/api/videos/{video.id}/comments", params={"sort": sort, "cursor": cursor}
    )
    assert r.status_code == 422


async def test_reaction_requires_auth_and_valid_value(make_client, client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")
    comment = await post(bob, video.id)

    assert (await react(client, comment["id"], 1)).status_code == 401
    for value in (2, -2, "up", None):
        assert (await react(bob, comment["id"], value)).status_code == 422
    assert (await react(bob, 99999, 1)).status_code == 404
    assert (await react(bob, 99999999999, 1)).status_code == 422


async def test_reaction_follows_video_access(make_client, make_video):
    alice, bob, carol = await make_client("alice"), await make_client("bob"), await make_client("carol")
    video = await make_video("alice", visibility=Visibility.private)
    comment = await post(alice, video.id)
    await alice.post(f"/api/videos/{video.id}/shares", json={"username": "bob"})

    assert (await react(bob, comment["id"], 1)).status_code == 200
    assert (await react(carol, comment["id"], 1)).status_code == 404
    assert (await listing(alice, video.id))["items"][0]["likes_count"] == 1  # лайк carol не прошёл


async def test_hidden_comment_only_for_author_and_staff(make_client, make_video, set_role):
    await make_client("alice")
    bob, carol, mod = await make_client("bob"), await make_client("carol"), await make_client("mod")
    await set_role("mod", Role.moderator)
    video = await make_video("alice")
    comment = await post(bob, video.id)
    await mod.post(f"/api/moderation/comments/{comment['id']}/hide")

    assert (await react(carol, comment["id"], 1)).status_code == 404
    assert (await react(bob, comment["id"], 1)).status_code == 200
    assert (await react(mod, comment["id"], 1)).status_code == 200


async def test_deleting_comment_removes_reactions(make_client, make_video, db):
    from sqlalchemy import func, select

    from app.models import CommentLike

    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")
    comment = await post(bob, video.id)
    await react(bob, comment["id"], 1)

    assert (await bob.delete(f"/api/comments/{comment['id']}")).status_code == 204
    assert (await db.execute(select(func.count()).select_from(CommentLike))).scalar_one() == 0