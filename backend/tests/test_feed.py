from app.models import VideoStatus, Visibility


def ids(response):
    return [v["id"] for v in response.json()["items"]]


async def test_feed_shows_only_public_ready_visible(make_client, client, make_video):
    await make_client("alice")
    public = await make_video("alice")
    await make_video("alice", visibility=Visibility.unlisted)
    await make_video("alice", visibility=Visibility.private)
    await make_video("alice", status=VideoStatus.uploaded)
    await make_video("alice", hidden=True)

    r = await client.get("/api/videos")
    assert r.status_code == 200
    assert ids(r) == [public.id]
    card = r.json()["items"][0]
    assert card["channel"]["handle"] == "alice"
    assert card["duration_seconds"] == 10.0


async def test_feed_pagination_newest_first(make_client, client, make_video):
    await make_client("alice")
    created = [(await make_video("alice")).id for _ in range(5)]

    seen, cursor = [], None
    for expected_len in (2, 2, 1):
        params = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        page = (await client.get("/api/videos", params=params)).json()
        assert len(page["items"]) == expected_len
        seen += [v["id"] for v in page["items"]]
        cursor = page["next_cursor"]
    assert cursor is None
    assert seen == created[::-1]


async def test_feed_empty(client):
    assert (await client.get("/api/videos")).json() == {"items": [], "next_cursor": None}


async def test_search_substring_case_insensitive(make_client, client, make_video):
    await make_client("alice")
    py = await make_video("alice", title="Python tutorial")
    await make_video("alice", title="Cooking pasta")

    for q in ("python", "PYTH", "torial"):
        assert ids(await client.get("/api/search", params={"q": q})) == [py.id]
    assert ids(await client.get("/api/search", params={"q": "nothing"})) == []


async def test_search_cyrillic(make_client, client, make_video):
    await make_client("alice")
    video = await make_video("alice", title="Привет, мир")
    for q in ("привет", "ПРИВЕТ", "мир"):
        assert ids(await client.get("/api/search", params={"q": q})) == [video.id]


async def test_search_escapes_like_wildcards(make_client, client, make_video):
    await make_client("alice")
    percent = await make_video("alice", title="100% legit")
    snake = await make_video("alice", title="snake_case")
    await make_video("alice", title="plain")

    assert ids(await client.get("/api/search", params={"q": "%"})) == [percent.id]
    assert ids(await client.get("/api/search", params={"q": "_"})) == [snake.id]


async def test_search_hides_non_public(make_client, client, make_video):
    await make_client("alice")
    visible = await make_video("alice", title="secret public")
    await make_video("alice", title="secret unlisted", visibility=Visibility.unlisted)
    await make_video("alice", title="secret private", visibility=Visibility.private)
    await make_video("alice", title="secret hidden", hidden=True)
    await make_video("alice", title="secret pending", status=VideoStatus.uploaded)

    assert ids(await client.get("/api/search", params={"q": "secret"})) == [visible.id]


async def test_search_pagination(make_client, client, make_video):
    await make_client("alice")
    created = [(await make_video("alice", title=f"clip {i}")).id for i in range(3)]

    first = (await client.get("/api/search", params={"q": "clip", "limit": 2})).json()
    assert [v["id"] for v in first["items"]] == created[::-1][:2]
    second = (
        await client.get("/api/search", params={"q": "clip", "limit": 2, "cursor": first["next_cursor"]})
    ).json()
    assert [v["id"] for v in second["items"]] == created[::-1][2:]
    assert second["next_cursor"] is None


async def test_search_edge_queries(client):
    assert (await client.get("/api/search")).status_code == 422
    assert (await client.get("/api/search", params={"q": ""})).status_code == 422
    assert (await client.get("/api/search", params={"q": "x" * 101})).status_code == 422
    assert (await client.get("/api/search", params={"q": "   "})).json()["items"] == []
    assert (await client.get("/api/search", params={"q": "a\x00b"})).status_code == 200  # не 500