from sqlalchemy import select

from app.models import AuditLog, Role


async def audit_rows(db):
    rows = (await db.execute(select(AuditLog).order_by(AuditLog.id))).scalars().all()
    return [(a.action, a.target_type, a.target_id) for a in rows]


async def test_admin_actions_on_foreign_content_are_audited(make_client, make_video, set_role, db):
    alice, bob = await make_client("alice"), await make_client("bob")
    root = await make_client("root")
    await set_role("root", Role.admin)
    video = await make_video("alice")
    comment = (await bob.post(f"/api/videos/{video.id}/comments", json={"text": "hi there"})).json()
    playlist = (await alice.post("/api/playlists", json={"title": "Mix"})).json()

    assert (await root.patch(f"/api/videos/{video.id}", json={"title": "Edited"})).status_code == 200
    assert (await root.patch(f"/api/playlists/{playlist['id']}", json={"title": "Edited"})).status_code == 200
    assert (await root.delete(f"/api/comments/{comment['id']}")).status_code == 204
    assert (await root.delete(f"/api/playlists/{playlist['id']}")).status_code == 204
    assert (await root.delete(f"/api/videos/{video.id}")).status_code == 204

    assert await audit_rows(db) == [
        ("video.update", "video", video.id),
        ("playlist.update", "playlist", playlist["id"]),
        ("comment.delete", "comment", comment["id"]),
        ("playlist.delete", "playlist", playlist["id"]),
        ("video.delete", "video", video.id),
    ]
    by_action = {
        a.action: a.details for a in (await db.execute(select(AuditLog))).scalars().all()
    }
    assert by_action["video.update"] == {"owner_id": video.owner_id, "changed": ["title"]}
    assert by_action["video.delete"] == {"title": "Edited", "owner_id": video.owner_id}
    assert by_action["comment.delete"]["text"] == "hi there"


async def test_own_actions_and_noops_are_not_audited(make_client, make_video, set_role, db):
    alice = await make_client("alice")
    root = await make_client("root")
    await set_role("root", Role.admin)
    video = await make_video("alice")
    comment = (await alice.post(f"/api/videos/{video.id}/comments", json={"text": "mine"})).json()
    playlist = (await alice.post("/api/playlists", json={"title": "Mix"})).json()

    assert (await alice.patch(f"/api/videos/{video.id}", json={"title": "New"})).status_code == 200
    assert (await alice.patch(f"/api/playlists/{playlist['id']}", json={"title": "New"})).status_code == 200
    assert (await alice.delete(f"/api/comments/{comment['id']}")).status_code == 204
    assert (await alice.delete(f"/api/playlists/{playlist['id']}")).status_code == 204
    # админ без реальных изменений тоже ничего не оставляет в журнале
    assert (await root.patch(f"/api/videos/{video.id}", json={"title": "New"})).status_code == 200
    assert (await alice.delete(f"/api/videos/{video.id}")).status_code == 204

    assert await audit_rows(db) == []


async def test_denied_actions_leave_no_audit(make_client, make_video, set_role, db):
    await make_client("alice")
    mod = await make_client("mod")
    await set_role("mod", Role.moderator)
    video = await make_video("alice")

    assert (await mod.patch(f"/api/videos/{video.id}", json={"title": "x"})).status_code == 404
    assert (await mod.delete(f"/api/videos/{video.id}")).status_code == 404
    assert await audit_rows(db) == []