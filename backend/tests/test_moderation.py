import pytest
from sqlalchemy import select

from app.models import AuditLog, Role, Visibility


async def report_video(client, video_id, reason="spam", details=""):
    return await client.post(
        f"/api/videos/{video_id}/report", json={"reason": reason, "details": details}
    )


async def report_comment(client, comment_id, reason="abuse"):
    return await client.post(f"/api/comments/{comment_id}/report", json={"reason": reason})


async def send_comment(client, video_id, text="hello", parent_id=None):
    payload = {"text": text}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    return await client.post(f"/api/videos/{video_id}/comments", json=payload)


async def post_comment(client, video_id, text="hello", parent_id=None):
    r = await send_comment(client, video_id, text, parent_id)
    assert r.status_code == 201, r.text
    return r.json()


async def make_staff(make_client, set_role, username="mod", role=Role.moderator):
    client = await make_client(username)
    await set_role(username, role)
    return client


async def queue(client, status="open", **params):
    r = await client.get("/api/moderation/reports", params={"status": status, **params})
    assert r.status_code == 200, r.text
    return r.json()


async def audit_actions(db):
    return list((await db.execute(select(AuditLog.action).order_by(AuditLog.id))).scalars())


# --- жалобы от пользователей ---


async def test_report_video_appears_in_queue(make_client, make_video, set_role):
    await make_client("alice")
    bob = await make_client("bob")
    mod = await make_staff(make_client, set_role)
    video = await make_video("alice")

    r = await report_video(bob, video.id, "spam", "buy my stuff")
    assert r.status_code == 201
    report_id = r.json()["id"]

    page = await queue(mod)
    assert page["next_cursor"] is None
    [item] = page["items"]
    assert item["id"] == report_id
    assert (item["status"], item["reason"], item["details"]) == ("open", "spam", "buy my stuff")
    assert item["reporter"]["handle"] == "bob"
    assert item["video"]["id"] == video.id
    assert item["video"]["title"] == "Test video"
    assert item["video"]["owner"]["handle"] == "alice"
    assert item["video"]["hidden"] is False
    assert item["comment"] is None
    assert item["handled_by"] is None


async def test_duplicate_open_report_is_conflict(make_client, make_video, set_role):
    await make_client("alice")
    bob = await make_client("bob")
    mod = await make_staff(make_client, set_role)
    video = await make_video("alice")

    assert (await report_video(bob, video.id)).status_code == 201
    assert (await report_video(bob, video.id)).status_code == 409

    [item] = (await queue(mod))["items"]
    assert (await mod.post(f"/api/moderation/reports/{item['id']}/dismiss")).status_code == 204
    assert (await report_video(bob, video.id)).status_code == 201  # после закрытия можно снова


@pytest.mark.parametrize(
    "payload",
    [
        {"reason": "nonsense"},
        {},
        {"reason": "spam", "details": "x" * 1001},
        {"reason": "spam", "details": "a\x00b"},
    ],
)
async def test_report_validation(make_client, make_video, payload):
    await make_client("alice")
    bob = await make_client("bob")
    video = await make_video("alice")
    assert (await bob.post(f"/api/videos/{video.id}/report", json=payload)).status_code == 422


async def test_cannot_report_own_content(make_client, make_video):
    alice = await make_client("alice")
    video = await make_video("alice")
    comment = await post_comment(alice, video.id)
    assert (await report_video(alice, video.id)).status_code == 400
    assert (await report_comment(alice, comment["id"])).status_code == 400


async def test_cannot_report_what_you_cannot_see(make_client, client, make_video):
    await make_client("alice")
    carol = await make_client("carol")
    private = await make_video("alice", visibility=Visibility.private)
    hidden = await make_video("alice", hidden=True)

    for video_id in (private.id, hidden.id, 99999):
        assert (await report_video(carol, video_id)).status_code == 404
    assert (await report_video(client, private.id)).status_code == 401
    assert (await report_comment(carol, 99999)).status_code == 404
    assert (await report_comment(client, 1)).status_code == 401


async def test_report_comment_on_private_video_follows_view_rules(make_client, make_video):
    alice = await make_client("alice")
    bob, carol = await make_client("bob"), await make_client("carol")
    video = await make_video("alice", visibility=Visibility.private)
    comment = await post_comment(alice, video.id)
    await alice.post(f"/api/videos/{video.id}/shares", json={"username": "bob"})

    assert (await report_comment(carol, comment["id"])).status_code == 404
    assert (await report_comment(bob, comment["id"])).status_code == 201


# --- очередь модератора ---


async def test_moderation_endpoints_require_staff(make_client, client, make_video, set_role):
    await make_client("alice")
    bob = await make_client("bob")
    mod = await make_staff(make_client, set_role)
    root = await make_staff(make_client, set_role, "root", Role.admin)
    video = await make_video("alice")
    endpoints = [
        ("GET", "/api/moderation/reports"),
        ("POST", "/api/moderation/reports/1/dismiss"),
        ("POST", f"/api/moderation/videos/{video.id}/hide"),
        ("POST", f"/api/moderation/videos/{video.id}/unhide"),
        ("POST", "/api/moderation/comments/1/hide"),
        ("POST", "/api/moderation/comments/1/unhide"),
    ]
    for method, url in endpoints:
        assert (await client.request(method, url)).status_code == 401
        assert (await bob.request(method, url)).status_code == 403
    assert (await mod.get("/api/moderation/reports")).status_code == 200
    assert (await root.get("/api/moderation/reports")).status_code == 200


async def test_queue_is_fifo_with_cursor_and_status_filter(make_client, make_video, set_role):
    await make_client("alice")
    bob = await make_client("bob")
    mod = await make_staff(make_client, set_role)
    videos = [await make_video("alice") for _ in range(3)]
    ids = [(await report_video(bob, v.id)).json()["id"] for v in videos]

    first = await queue(mod, limit=2)
    assert [i["id"] for i in first["items"]] == ids[:2]
    second = await queue(mod, limit=2, cursor=first["next_cursor"])
    assert [i["id"] for i in second["items"]] == ids[2:]
    assert second["next_cursor"] is None

    assert (await mod.post(f"/api/moderation/reports/{ids[0]}/dismiss")).status_code == 204
    assert [i["id"] for i in (await queue(mod, "dismissed"))["items"]] == [ids[0]]
    assert [i["id"] for i in (await queue(mod))["items"]] == ids[1:]
    assert (await mod.get("/api/moderation/reports", params={"status": "bogus"})).status_code == 422


async def test_dismiss_report(make_client, make_video, set_role, db):
    await make_client("alice")
    bob = await make_client("bob")
    mod = await make_staff(make_client, set_role)
    video = await make_video("alice")
    report_id = (await report_video(bob, video.id)).json()["id"]
    url = f"/api/moderation/reports/{report_id}/dismiss"

    assert (await mod.post(url)).status_code == 204
    assert (await mod.post(url)).status_code == 409
    assert (await mod.post("/api/moderation/reports/99999/dismiss")).status_code == 404

    [item] = (await queue(mod, "dismissed"))["items"]
    assert item["status"] == "dismissed"
    assert item["handled_by"]["handle"] == "mod"
    assert item["handled_at"] is not None
    assert await audit_actions(db) == ["report.dismiss"]


async def test_deleting_target_removes_its_reports(make_client, make_video, set_role):
    alice = await make_client("alice")
    bob = await make_client("bob")
    mod = await make_staff(make_client, set_role)
    video = await make_video("alice")
    await report_video(bob, video.id)

    assert (await alice.delete(f"/api/videos/{video.id}")).status_code == 204
    assert (await queue(mod))["items"] == []


# --- скрытие видео ---


async def test_hide_video_resolves_reports(make_client, client, make_video, set_role, db):
    alice = await make_client("alice")
    bob, carol = await make_client("bob"), await make_client("carol")
    mod = await make_staff(make_client, set_role)
    video = await make_video("alice")
    await report_video(bob, video.id)
    await report_video(carol, video.id, "violence")
    url = f"/api/videos/{video.id}"

    r = await mod.post(f"/api/moderation/videos/{video.id}/hide")
    assert (r.status_code, r.json()) == (200, {"hidden": True})

    assert (await queue(mod))["items"] == []
    resolved = (await queue(mod, "resolved"))["items"]
    assert len(resolved) == 2
    assert {i["handled_by"]["handle"] for i in resolved} == {"mod"}
    assert all(i["video"]["hidden"] is True for i in resolved)

    for denied in (bob, client):
        assert (await denied.get(url)).status_code == 404
    assert (await alice.get(url)).json()["hidden_by_moderation"] is True
    assert (await mod.get(url)).status_code == 200
    assert (await client.get("/api/videos")).json()["items"] == []

    assert (await mod.post(f"/api/moderation/videos/{video.id}/hide")).status_code == 200  # идемпотентно
    assert (await mod.post(f"/api/moderation/videos/{video.id}/unhide")).json() == {"hidden": False}
    assert (await client.get(url)).status_code == 200
    assert await audit_actions(db) == ["video.hide", "video.unhide"]  # повтор не пишется


async def test_hiding_does_not_give_moderator_access_to_private_video(
    make_client, make_video, set_role
):
    await make_client("alice")
    mod = await make_staff(make_client, set_role)
    video = await make_video("alice", visibility=Visibility.private)

    assert (await mod.post(f"/api/moderation/videos/{video.id}/hide")).status_code == 200
    for suffix in ("", "/stream", "/thumbnail"):
        assert (await mod.get(f"/api/videos/{video.id}{suffix}")).status_code == 404


async def test_hide_unknown_targets(make_client, set_role):
    mod = await make_staff(make_client, set_role)
    assert (await mod.post("/api/moderation/videos/99999/hide")).status_code == 404
    assert (await mod.post("/api/moderation/comments/99999/hide")).status_code == 404
    assert (await mod.post("/api/moderation/videos/99999999999/hide")).status_code == 422


# --- скрытие комментариев ---


async def test_hidden_comment_visibility(make_client, client, make_video, set_role):
    await make_client("alice")
    bob, carol = await make_client("bob"), await make_client("carol")
    mod = await make_staff(make_client, set_role)
    video = await make_video("alice")
    top = await post_comment(bob, video.id, "bad words")
    await post_comment(carol, video.id, "reply", parent_id=top["id"])
    list_url = f"/api/videos/{video.id}/comments"
    replies_url = f"/api/comments/{top['id']}/replies"

    assert (await mod.post(f"/api/moderation/comments/{top['id']}/hide")).json() == {"hidden": True}

    for outsider in (carol, client):
        assert (await outsider.get(list_url)).json()["items"] == []
        assert (await outsider.get(replies_url)).status_code == 404
    assert (await send_comment(carol, video.id, "sneaky", parent_id=top["id"])).status_code == 404

    for allowed in (bob, mod):  # автор и модератор видят с пометкой
        items = (await allowed.get(list_url)).json()["items"]
        assert [(c["id"], c["hidden_by_moderation"]) for c in items] == [(top["id"], True)]
        assert (await allowed.get(replies_url)).status_code == 200

    assert (await mod.post(f"/api/moderation/comments/{top['id']}/unhide")).json() == {"hidden": False}
    items = (await carol.get(list_url)).json()["items"]
    assert [c["id"] for c in items] == [top["id"]]
    assert items[0]["hidden_by_moderation"] is False


async def test_hidden_reply_is_not_counted_for_others(make_client, client, make_video, set_role):
    await make_client("alice")
    bob, carol = await make_client("bob"), await make_client("carol")
    mod = await make_staff(make_client, set_role)
    video = await make_video("alice")
    top = await post_comment(bob, video.id)
    reply = await post_comment(carol, video.id, "rude", parent_id=top["id"])
    await mod.post(f"/api/moderation/comments/{reply['id']}/hide")
    list_url = f"/api/videos/{video.id}/comments"
    replies_url = f"/api/comments/{top['id']}/replies"

    counts = {
        name: (await who.get(list_url)).json()["items"][0]["reply_count"]
        for name, who in (("anon", client), ("bob", bob), ("carol", carol), ("mod", mod))
    }
    assert counts == {"anon": 0, "bob": 0, "carol": 1, "mod": 1}  # автор и модератор видят
    assert (await client.get(replies_url)).json()["items"] == []
    assert [c["id"] for c in (await carol.get(replies_url)).json()["items"]] == [reply["id"]]
    assert [c["id"] for c in (await mod.get(replies_url)).json()["items"]] == [reply["id"]]


async def test_hiding_comment_resolves_its_reports(make_client, make_video, set_role, db):
    await make_client("alice")
    bob, carol = await make_client("bob"), await make_client("carol")
    mod = await make_staff(make_client, set_role)
    video = await make_video("alice")
    comment = await post_comment(bob, video.id, "spam spam")
    await report_comment(carol, comment["id"])

    [item] = (await queue(mod))["items"]
    assert item["video"] is None
    assert item["comment"]["text"] == "spam spam"
    assert item["comment"]["author"]["handle"] == "bob"
    assert item["comment"]["video_id"] == video.id

    assert (await mod.post(f"/api/moderation/comments/{comment['id']}/hide")).status_code == 200
    assert (await queue(mod))["items"] == []
    [resolved] = (await queue(mod, "resolved"))["items"]
    assert resolved["comment"]["hidden"] is True

    # на скрытый комментарий посторонний пожаловаться уже не может: он его не видит
    assert (await report_comment(carol, comment["id"])).status_code == 404
    assert await audit_actions(db) == ["comment.hide"]