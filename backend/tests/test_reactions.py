import pytest

from app.models import VideoStatus, Visibility


async def react(client, video_id, value):
    return await client.put(f"/api/videos/{video_id}/reaction", json={"value": value})


async def test_like_dislike_and_toggle(make_client, client, make_video):
    alice, bob = await make_client("alice"), await make_client("bob")
    video = await make_video("alice")

    assert (await react(bob, video.id, 1)).json() == {"likes_count": 1, "my_reaction": 1}
    assert (await react(bob, video.id, 1)).json() == {"likes_count": 1, "my_reaction": 1}  # повтор не дублирует
    assert (await react(alice, video.id, 1)).json() == {"likes_count": 2, "my_reaction": 1}
    assert (await react(bob, video.id, -1)).json() == {"likes_count": 1, "my_reaction": -1}
    assert (await react(bob, video.id, 0)).json() == {"likes_count": 1, "my_reaction": 0}

    url = f"/api/videos/{video.id}"
    assert (await alice.get(url)).json()["my_reaction"] == 1
    assert (await bob.get(url)).json()["my_reaction"] == 0
    anon = (await client.get(url)).json()
    assert anon["likes_count"] == 1
    assert anon["my_reaction"] == 0


async def test_reaction_requires_auth(make_client, client, make_video):
    await make_client("alice")
    video = await make_video("alice")
    assert (await react(client, video.id, 1)).status_code == 401


@pytest.mark.parametrize("value", [2, -2, "up", None])
async def test_invalid_reaction_value(make_client, make_video, value):
    alice = await make_client("alice")
    video = await make_video("alice")
    assert (await react(alice, video.id, value)).status_code == 422


async def test_reaction_follows_view_rules(make_client, make_video):
    alice, bob, carol = await make_client("alice"), await make_client("bob"), await make_client("carol")
    video = await make_video("alice", visibility=Visibility.private)
    await alice.post(f"/api/videos/{video.id}/shares", json={"username": "bob"})

    assert (await react(bob, video.id, 1)).status_code == 200
    assert (await react(carol, video.id, 1)).status_code == 404  # не 403
    assert (await alice.get(f"/api/videos/{video.id}")).json()["likes_count"] == 1  # лайк carol не прошёл


async def test_reaction_on_unfinished_video(make_client, make_video):
    alice = await make_client("alice")
    video = await make_video("alice", status=VideoStatus.uploaded)
    assert (await react(alice, video.id, 1)).status_code == 409


async def test_reaction_missing_video(make_client):
    alice = await make_client("alice")
    assert (await react(alice, 99999, 1)).status_code == 404
    assert (await react(alice, 99999999999, 1)).status_code == 422