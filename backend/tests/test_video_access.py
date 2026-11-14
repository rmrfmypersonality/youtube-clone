import pytest

from app.models import Role, VideoStatus, Visibility

# Все эндпоинты, которые читают видео. Правила доступа у них должны быть одинаковые.
READ_ENDPOINTS = [
    ("GET", "/api/videos/{id}"),
    ("GET", "/api/videos/{id}/stream"),
    ("GET", "/api/videos/{id}/thumbnail"),
    ("POST", "/api/videos/{id}/view"),
]


async def call(client, method, template, video_id):
    return await client.request(method, template.format(id=video_id))


async def share(owner, video_id, username):
    return await owner.post(f"/api/videos/{video_id}/shares", json={"username": username})


async def test_public_video_for_anonymous(make_client, client, make_video):
    await make_client("alice")
    video = await make_video("alice", visibility=Visibility.public)

    r = await client.get(f"/api/videos/{video.id}")
    assert r.status_code == 200
    assert r.json()["channel"]["handle"] == "alice"

    r = await client.get(f"/api/videos/{video.id}/stream")
    assert r.status_code == 200
    assert r.headers["x-accel-redirect"] == f"/media/videos/{video.id}/720.mp4"
    assert "private" in r.headers["cache-control"]
    assert r.content == b""

    r = await client.get(f"/api/videos/{video.id}/thumbnail")
    assert r.headers["x-accel-redirect"] == f"/media/videos/{video.id}/thumb.jpg"


async def test_stream_quality(make_client, client, make_video):
    await make_client("alice")
    video = await make_video("alice")
    r = await client.get(f"/api/videos/{video.id}/stream?quality=360")
    assert r.headers["x-accel-redirect"] == f"/media/videos/{video.id}/360.mp4"
    assert (await client.get(f"/api/videos/{video.id}/stream?quality=1080")).status_code == 422


async def test_unlisted_video_available_by_link(make_client, client, make_video):
    await make_client("alice")
    video = await make_video("alice", visibility=Visibility.unlisted)
    assert (await client.get(f"/api/videos/{video.id}")).status_code == 200
    assert (await client.get(f"/api/videos/{video.id}/stream")).status_code == 200


@pytest.mark.parametrize("method,template", READ_ENDPOINTS)
async def test_private_video_only_for_owner_and_shared(
    make_client, client, make_video, method, template
):
    alice = await make_client("alice")
    bob = await make_client("bob")
    carol = await make_client("carol")
    video = await make_video("alice", visibility=Visibility.private)
    assert (await share(alice, video.id, "bob")).status_code == 201

    assert (await call(alice, method, template, video.id)).status_code == 200
    assert (await call(bob, method, template, video.id)).status_code == 200
    for denied in (carol, client):
        r = await call(denied, method, template, video.id)
        assert r.status_code == 404
        assert "x-accel-redirect" not in r.headers


async def test_revoked_share_closes_access(make_client, make_video):
    alice, bob = await make_client("alice"), await make_client("bob")
    video = await make_video("alice", visibility=Visibility.private)
    bob_id = (await bob.get("/api/auth/me")).json()["id"]

    await share(alice, video.id, "bob")
    assert (await bob.get(f"/api/videos/{video.id}/stream")).status_code == 200

    assert (await alice.delete(f"/api/videos/{video.id}/shares/{bob_id}")).status_code == 204
    assert (await bob.get(f"/api/videos/{video.id}/stream")).status_code == 404


async def test_denied_looks_like_missing(make_client, client, make_video):
    await make_client("alice")
    video = await make_video("alice", visibility=Visibility.private)
    denied = await client.get(f"/api/videos/{video.id}/stream")
    missing = await client.get("/api/videos/99999/stream")
    assert denied.status_code == missing.status_code == 404
    assert denied.json() == missing.json()


@pytest.mark.parametrize("role", [Role.moderator, Role.admin])
async def test_staff_cannot_see_private_videos(make_client, make_video, set_role, role):
    await make_client("alice")
    staff = await make_client("staff")
    await set_role("staff", role)
    video = await make_video("alice", visibility=Visibility.private)
    assert (await staff.get(f"/api/videos/{video.id}")).status_code == 404
    assert (await staff.get(f"/api/videos/{video.id}/stream")).status_code == 404


async def test_hidden_video(make_client, client, make_video, set_role):
    alice, bob, mod = await make_client("alice"), await make_client("bob"), await make_client("mod")
    await set_role("mod", Role.moderator)
    video = await make_video("alice", visibility=Visibility.public, hidden=True)
    url = f"/api/videos/{video.id}"

    assert (await alice.get(url)).json()["hidden_by_moderation"] is True
    assert (await mod.get(url)).status_code == 200
    assert (await mod.get(url + "/stream")).status_code == 200
    for denied in (bob, client):
        assert (await denied.get(url)).status_code == 404
        assert (await denied.get(url + "/stream")).status_code == 404
        assert (await denied.get(url + "/thumbnail")).status_code == 404


async def test_unfinished_video_only_for_owner(make_client, client, make_video):
    alice, bob = await make_client("alice"), await make_client("bob")
    video = await make_video("alice", visibility=Visibility.public, status=VideoStatus.uploaded)
    url = f"/api/videos/{video.id}"

    assert (await alice.get(url)).status_code == 200
    assert (await bob.get(url)).status_code == 404
    assert (await client.get(url)).status_code == 404
    # у владельца метаданные есть, но играть пока нечего
    assert (await alice.get(url + "/stream")).status_code == 404
    assert (await alice.get(url + "/thumbnail")).status_code == 404
    assert (await alice.post(url + "/view")).status_code == 409


async def test_view_counter(make_client, client, make_video):
    await make_client("alice")
    video = await make_video("alice")
    assert (await client.post(f"/api/videos/{video.id}/view")).json() == {"views_count": 1}
    assert (await client.post(f"/api/videos/{video.id}/view")).json() == {"views_count": 2}
    assert (await client.get(f"/api/videos/{video.id}")).json()["views_count"] == 2


async def test_huge_id_is_422_not_500(client):
    assert (await client.get("/api/videos/99999999999")).status_code == 422
    assert (await client.get("/api/videos/0")).status_code == 422


async def test_share_management(make_client, make_video):
    alice, bob = await make_client("alice"), await make_client("bob")
    bob_id = (await bob.get("/api/auth/me")).json()["id"]
    video = await make_video("alice", visibility=Visibility.private)
    base = f"/api/videos/{video.id}/shares"

    r = await alice.post(base, json={"username": "BOB"})  # регистр не важен
    assert r.status_code == 201
    assert r.json() == {"id": bob_id, "username": "bob"}
    assert (await alice.post(base, json={"username": "bob"})).status_code == 201  # повтор безопасен
    assert [u["username"] for u in (await alice.get(base)).json()] == ["bob"]

    assert (await alice.delete(f"{base}/{bob_id}")).status_code == 204
    assert (await alice.delete(f"{base}/{bob_id}")).status_code == 204  # идемпотентно
    assert (await alice.get(base)).json() == []


async def test_share_errors(make_client, make_video):
    alice = await make_client("alice")
    video = await make_video("alice", visibility=Visibility.private)
    base = f"/api/videos/{video.id}/shares"

    assert (await alice.post(base, json={"username": "ghost"})).status_code == 404
    assert (await alice.post(base, json={"username": "alice"})).status_code == 400
    assert (await alice.post(base, json={"username": "bad name!"})).status_code == 422


async def test_shares_are_owner_only(make_client, client, make_video, set_role):
    alice, bob, root = await make_client("alice"), await make_client("bob"), await make_client("root")
    await set_role("root", Role.admin)
    video = await make_video("alice", visibility=Visibility.public)
    base = f"/api/videos/{video.id}/shares"

    for outsider in (bob, root):
        assert (await outsider.get(base)).status_code == 404
        assert (await outsider.post(base, json={"username": "bob"})).status_code == 404
        assert (await outsider.delete(f"{base}/1")).status_code == 404

    assert (await alice.get(base)).json() == []  # ничего не создалось
    assert (await client.get(base)).status_code == 401