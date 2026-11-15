import pytest
from sqlalchemy import func, select

from app.models import Comment, Role, VideoStatus, Visibility


async def post_comment(client, video_id, text="hello", parent_id=None):
    payload = {"text": text}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    return await client.post(f"/api/videos/{video_id}/comments", json=payload)


def ids(response):
    return [c["id"] for c in response.json()["items"]]


async def test_create_and_list(make_client, client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")

    r = await post_comment(bob, video.id, "  first  ")
    assert r.status_code == 201
    body = r.json()
    assert body["text"] == "first"
    assert body["parent_id"] is None
    assert body["reply_count"] == 0
    assert body["author"]["handle"] == "bob"

    page = (await client.get(f"/api/videos/{video.id}/comments")).json()  # аноним читает публичное
    assert [c["id"] for c in page["items"]] == [body["id"]]
    assert page["next_cursor"] is None


async def test_comment_text_is_stored_as_is(make_client, make_video):
    """Экранирует фронт ({{ }}), API хранит и отдаёт текст как есть."""
    alice = await make_client("alice")
    video = await make_video("alice")
    r = await post_comment(alice, video.id, "<script>alert(1)</script>")
    assert r.json()["text"] == "<script>alert(1)</script>"


async def test_create_requires_auth(make_client, client, make_video):
    await make_client("alice")
    video = await make_video("alice")
    assert (await post_comment(client, video.id)).status_code == 401


@pytest.mark.parametrize("text", ["", "   ", "x" * 2001, "a\x00b"])
async def test_text_validation(make_client, make_video, text):
    alice = await make_client("alice")
    video = await make_video("alice")
    assert (await post_comment(alice, video.id, text)).status_code == 422


@pytest.mark.parametrize("parent_id", [0, -1, 99999999999])
async def test_parent_id_validation(make_client, make_video, parent_id):
    alice = await make_client("alice")
    video = await make_video("alice")
    assert (await post_comment(alice, video.id, parent_id=parent_id)).status_code == 422


async def test_cursor_pagination_newest_first(make_client, client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")
    created = []
    for i in range(5):
        created.append((await post_comment(bob, video.id, f"c{i}")).json()["id"])
    url = f"/api/videos/{video.id}/comments"

    seen, cursor = [], None
    for expected_len in (2, 2, 1):
        params = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        page = (await client.get(url, params=params)).json()
        assert len(page["items"]) == expected_len
        seen += [c["id"] for c in page["items"]]
        cursor = page["next_cursor"]
    assert cursor is None
    assert seen == created[::-1]


async def test_sort_old_first(make_client, client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")
    created = []
    for i in range(3):
        created.append((await post_comment(bob, video.id, f"c{i}")).json()["id"])

    r = await client.get(f"/api/videos/{video.id}/comments", params={"sort": "old"})
    assert ids(r) == created
    r = await client.get(f"/api/videos/{video.id}/comments", params={"sort": "oldest"})
    assert r.status_code == 422


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 51}, {"cursor": 0}, {"cursor": 99999999999}])
async def test_pagination_params_validation(make_client, client, make_video, params):
    await make_client("alice")
    video = await make_video("alice")
    assert (await client.get(f"/api/videos/{video.id}/comments", params=params)).status_code == 422


async def test_replies_are_flattened_to_thread_root(make_client, client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")

    top = (await post_comment(bob, video.id, "top")).json()
    r1 = (await post_comment(bob, video.id, "r1", parent_id=top["id"])).json()
    r2 = (await post_comment(bob, video.id, "r2", parent_id=r1["id"])).json()  # ответ на ответ
    assert r1["parent_id"] == top["id"]
    assert r2["parent_id"] == top["id"]

    listing = (await client.get(f"/api/videos/{video.id}/comments")).json()
    assert [c["id"] for c in listing["items"]] == [top["id"]]  # ответы в корневой список не попадают
    assert listing["items"][0]["reply_count"] == 2

    replies = await client.get(f"/api/comments/{top['id']}/replies")
    assert ids(replies) == [r1["id"], r2["id"]]  # по возрастанию


async def test_replies_pagination(make_client, client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")
    top = (await post_comment(bob, video.id, "top")).json()
    created = []
    for i in range(3):
        created.append((await post_comment(bob, video.id, f"r{i}", parent_id=top["id"])).json()["id"])

    url = f"/api/comments/{top['id']}/replies"
    first = (await client.get(url, params={"limit": 2})).json()
    assert [c["id"] for c in first["items"]] == created[:2]
    second = (await client.get(url, params={"limit": 2, "cursor": first["next_cursor"]})).json()
    assert [c["id"] for c in second["items"]] == created[2:]
    assert second["next_cursor"] is None


async def test_replies_of_a_reply_not_found(make_client, client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")
    top = (await post_comment(bob, video.id)).json()
    reply = (await post_comment(bob, video.id, parent_id=top["id"])).json()
    assert (await client.get(f"/api/comments/{reply['id']}/replies")).status_code == 404
    assert (await client.get("/api/comments/99999/replies")).status_code == 404


async def test_cannot_reply_into_comment_of_another_video(make_client, make_video):
    """IDOR: parent_id из чужого видео не должен давать писать в чужой тред."""
    await make_client("alice")
    bob = await make_client("bob")
    video1, video2 = await make_video("alice"), await make_video("alice")
    foreign = (await post_comment(bob, video1.id, "on video 1")).json()

    assert (await post_comment(bob, video2.id, "sneaky", parent_id=foreign["id"])).status_code == 404
    assert (await post_comment(bob, video2.id, "ghost", parent_id=99999)).status_code == 404


async def test_private_video_comments_follow_view_rules(make_client, client, make_video):
    alice, bob, carol = await make_client("alice"), await make_client("bob"), await make_client("carol")
    video = await make_video("alice", visibility=Visibility.private)
    top = (await post_comment(alice, video.id, "top")).json()  # владелец может писать
    await post_comment(alice, video.id, "reply", parent_id=top["id"])
    await alice.post(f"/api/videos/{video.id}/shares", json={"username": "bob"})

    list_url = f"/api/videos/{video.id}/comments"
    replies_url = f"/api/comments/{top['id']}/replies"

    for allowed in (alice, bob):
        assert (await allowed.get(list_url)).status_code == 200
        assert (await allowed.get(replies_url)).status_code == 200
    assert (await post_comment(bob, video.id, "from bob")).status_code == 201

    for denied in (carol, client):
        assert (await denied.get(list_url)).status_code == 404
        assert (await denied.get(replies_url)).status_code == 404
    assert (await post_comment(carol, video.id, "no")).status_code == 404
    assert (await post_comment(carol, video.id, "no", parent_id=top["id"])).status_code == 404


async def test_hidden_video_comments(make_client, client, make_video, set_role):
    alice, bob, mod = await make_client("alice"), await make_client("bob"), await make_client("mod")
    await set_role("mod", Role.moderator)
    video = await make_video("alice", hidden=True)
    url = f"/api/videos/{video.id}/comments"

    assert (await alice.get(url)).status_code == 200
    assert (await mod.get(url)).status_code == 200
    assert (await bob.get(url)).status_code == 404
    assert (await post_comment(bob, video.id)).status_code == 404


async def test_unfinished_video(make_client, make_video):
    alice = await make_client("alice")
    video = await make_video("alice", status=VideoStatus.uploaded)
    assert (await post_comment(alice, video.id)).status_code == 409
    r = await alice.get(f"/api/videos/{video.id}/comments")
    assert r.status_code == 200 and r.json()["items"] == []


async def test_delete_own_comment(make_client, client, make_video):
    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")
    comment = (await post_comment(bob, video.id)).json()

    assert (await bob.delete(f"/api/comments/{comment['id']}")).status_code == 204
    assert (await client.get(f"/api/videos/{video.id}/comments")).json()["items"] == []
    assert (await bob.delete(f"/api/comments/{comment['id']}")).status_code == 404


async def test_delete_foreign_comment_denied(make_client, client, make_video):
    alice, bob = await make_client("alice"), await make_client("bob")
    video = await make_video("alice")
    comment = (await post_comment(bob, video.id)).json()

    # даже владелец видео чужой комментарий удалить не может: по заданию это только админ
    assert (await alice.delete(f"/api/comments/{comment['id']}")).status_code == 404
    assert (await client.delete(f"/api/comments/{comment['id']}")).status_code == 401
    assert len((await client.get(f"/api/videos/{video.id}/comments")).json()["items"]) == 1


async def test_admin_can_delete_any_comment(make_client, make_video, set_role):
    await make_client("alice")
    bob, root = await make_client("bob"), await make_client("root")
    await set_role("root", Role.admin)
    video = await make_video("alice")
    comment = (await post_comment(bob, video.id)).json()
    assert (await root.delete(f"/api/comments/{comment['id']}")).status_code == 204


async def test_moderator_cannot_delete_comments(make_client, make_video, set_role):
    await make_client("alice")
    bob, mod = await make_client("bob"), await make_client("mod")
    await set_role("mod", Role.moderator)
    video = await make_video("alice")
    comment = (await post_comment(bob, video.id)).json()
    assert (await mod.delete(f"/api/comments/{comment['id']}")).status_code == 404


async def test_deleting_top_comment_removes_replies(make_client, make_video, db):
    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")
    top = (await post_comment(bob, video.id)).json()
    await post_comment(bob, video.id, parent_id=top["id"])
    await post_comment(bob, video.id, parent_id=top["id"])

    assert (await bob.delete(f"/api/comments/{top['id']}")).status_code == 204
    assert (await db.execute(select(func.count()).select_from(Comment))).scalar_one() == 0


async def test_delete_huge_id_is_422(make_client):
    alice = await make_client("alice")
    assert (await alice.delete("/api/comments/99999999999")).status_code == 422