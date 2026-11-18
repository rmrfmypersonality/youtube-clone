from sqlalchemy import select

from app.main import app
from app.models import Report, ReportStatus, Visibility


def J(**body):
    return {"json": body}


RAW = {"content": b"\x00" * 16, "headers": {"Content-Type": "application/octet-stream"}}

# (метод, шаблон пути, параметры запроса, ответ чужому пользователю, ответ анониму)
# Жертва: alice (приватное видео, комментарий, приватный плейлист) и hank (скрытый канал).
# Атакующий: bob. 404, а не 403: чужое не должно выдавать факт своего существования.
CASES = [
    ("PUT", "/api/videos/{video_id}/file", RAW, 404, 401),
    ("GET", "/api/videos/{video_id}", {}, 404, 404),
    ("GET", "/api/videos/{video_id}/stream", {}, 404, 404),
    ("GET", "/api/videos/{video_id}/thumbnail", {}, 404, 404),
    ("POST", "/api/videos/{video_id}/view", {}, 404, 404),
    ("PATCH", "/api/videos/{video_id}", J(title="hacked", visibility="public"), 404, 401),
    ("DELETE", "/api/videos/{video_id}", {}, 404, 401),
    ("GET", "/api/videos/{video_id}/shares", {}, 404, 401),
    ("POST", "/api/videos/{video_id}/shares", J(username="bob"), 404, 401),  # выдать доступ себе
    ("DELETE", "/api/videos/{video_id}/shares/{user_id}", {}, 404, 401),
    ("PUT", "/api/videos/{video_id}/reaction", J(value=1), 404, 401),
    ("GET", "/api/videos/{video_id}/comments", {}, 404, 404),
    ("POST", "/api/videos/{video_id}/comments", J(text="spam"), 404, 401),
    ("GET", "/api/comments/{comment_id}/replies", {}, 404, 404),
    ("DELETE", "/api/comments/{comment_id}", {}, 404, 401),
    ("POST", "/api/videos/{video_id}/report", J(reason="spam"), 404, 401),
    ("POST", "/api/comments/{comment_id}/report", J(reason="spam"), 404, 401),
    ("GET", "/api/playlists/{playlist_id}", {}, 404, 404),
    ("PATCH", "/api/playlists/{playlist_id}", J(title="hacked"), 404, 401),
    ("DELETE", "/api/playlists/{playlist_id}", {}, 404, 401),
    ("PUT", "/api/playlists/{playlist_id}/items/{video_id}", {}, 404, 401),
    ("DELETE", "/api/playlists/{playlist_id}/items/{video_id}", {}, 404, 401),
    ("GET", "/api/channels/{handle}", {}, 404, 404),
    ("GET", "/api/channels/{handle}/videos", {}, 404, 404),
    ("GET", "/api/channels/{handle}/playlists", {}, 404, 404),
    ("PUT", "/api/channels/{handle}/subscription", {}, 404, 401),
    # только для персонала: обычному пользователю 403
    ("POST", "/api/moderation/reports/{report_id}/dismiss", {}, 403, 401),
    ("POST", "/api/moderation/videos/{video_id}/hide", {}, 403, 401),
    ("POST", "/api/moderation/videos/{video_id}/unhide", {}, 403, 401),
    ("POST", "/api/moderation/comments/{comment_id}/hide", {}, 403, 401),
    ("POST", "/api/moderation/comments/{comment_id}/unhide", {}, 403, 401),
    ("PATCH", "/api/admin/users/{user_id}", J(role="admin"), 403, 401),  # user_id = bob: сам себя в админы
]

# Эндпоинты с id, где проверка чужого не имеет смысла
EXEMPT = {
    ("DELETE", "/api/history/{video_id}"): "затрагивает только историю самого вызывающего",
    ("DELETE", "/api/channels/{handle}/subscription"): "своя подписка; отписаться можно и от скрытого канала",
}



def _discovered() -> set[tuple[str, str]]:
    found = set()
    for path, methods in app.openapi()["paths"].items():
        if "{" not in path:
            continue
        for method in methods:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                found.add((method.upper(), path))
    return found



def test_every_endpoint_with_id_is_classified():
    """Новый эндпоинт с id нельзя добавить, не решив, как он защищён от IDOR."""
    known = {(m, p) for m, p, *_ in CASES} | set(EXEMPT)
    found = _discovered()
    assert not found - known, f"Нет проверки на IDOR: {sorted(found - known)}"
    assert not known - found, f"Эндпоинтов уже нет, уберите из списка: {sorted(known - found)}"


async def test_idor_matrix(make_client, client, make_video, db):
    alice, bob, carol, hank = (
        await make_client("alice"),
        await make_client("bob"),
        await make_client("carol"),
        await make_client("hank"),
    )
    bob_id = (await bob.get("/api/auth/me")).json()["id"]

    private = await make_video("alice", title="Original title", visibility=Visibility.private)
    public = await make_video("alice")
    comment = (await alice.post(f"/api/videos/{private.id}/comments", json={"text": "alice's comment"})).json()
    playlist = (await alice.post("/api/playlists", json={"title": "Secret mix", "visibility": "private"})).json()
    assert (await alice.put(f"/api/playlists/{playlist['id']}/items/{private.id}")).status_code == 204
    report_id = (await carol.post(f"/api/videos/{public.id}/report", json={"reason": "spam"})).json()["id"]
    assert (await hank.patch("/api/channels/me", json={"is_hidden": True})).status_code == 200

    ids = {
        "video_id": private.id,
        "comment_id": comment["id"],
        "playlist_id": playlist["id"],
        "report_id": report_id,
        "user_id": bob_id,
        "handle": "hank",
    }

    failures = []
    for method, template, kwargs, bob_status, anon_status in CASES:
        url = template.format(**ids)
        for who_name, who, expected in (("bob", bob, bob_status), ("аноним", client, anon_status)):
            r = await who.request(method, url, **kwargs)
            if r.status_code != expected:
                failures.append(f"{who_name}: {method} {template} вернул {r.status_code}, ожидали {expected}")
    assert not failures, "\n" + "\n".join(failures)

    # ничего не изменилось
    detail = (await alice.get(f"/api/videos/{private.id}")).json()
    assert (detail["title"], detail["visibility"]) == ("Original title", "private")
    assert (detail["likes_count"], detail["views_count"]) == (0, 0)
    assert (await alice.get(f"/api/videos/{private.id}/shares")).json() == []
    texts = [c["text"] for c in (await alice.get(f"/api/videos/{private.id}/comments")).json()["items"]]
    assert texts == ["alice's comment"]
    saved = (await alice.get(f"/api/playlists/{playlist['id']}")).json()
    assert (saved["title"], saved["items_count"]) == ("Secret mix", 1)
    assert (await bob.get("/api/auth/me")).json()["role"] == "user"
    assert (await hank.get("/api/channels/hank")).json()["subscribers_count"] == 0
    assert (await db.execute(select(Report.status))).scalars().all() == [ReportStatus.open]