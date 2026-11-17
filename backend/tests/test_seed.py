from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import (
    AuditLog,
    Comment,
    Like,
    Playlist,
    PlaylistItem,
    PlaylistKind,
    Report,
    ReportStatus,
    Subscription,
    User,
    Video,
    VideoShare,
    WatchHistory,
)
from scripts import seed

MODELS = [User, Video, Comment, Like, Subscription, VideoShare, Playlist, PlaylistItem, WatchHistory, Report, AuditLog]


@pytest.fixture
def assets(tmp_path, sample_video) -> Path:
    (tmp_path / "demo.mp4").write_bytes(sample_video)
    (tmp_path / ".gitkeep").write_text("")
    (tmp_path / "notes.txt").write_text("не видео")
    return tmp_path


async def counts(db) -> dict[str, int]:
    return {m.__name__: (await db.execute(select(func.count()).select_from(m))).scalar_one() for m in MODELS}


async def test_seed_creates_demo_data(assets, db, client):
    await seed.run(assets)
    c = await counts(db)

    assert c["User"] == len(seed.USERS)
    assert c["Video"] == len(seed.VIDEOS)
    assert c["Comment"] == len(seed.COMMENTS)
    assert c["Like"] == sum(len(v) for v in seed.LIKES.values())
    assert c["Subscription"] == len(seed.SUBSCRIPTIONS)
    assert c["VideoShare"] == len(seed.SHARES)
    assert c["WatchHistory"] == sum(len(v) for v in seed.HISTORY.values())
    assert c["PlaylistItem"] == sum(len(p[3]) for p in seed.PLAYLISTS) + sum(len(w[1]) for w in seed.WATCH_LATER)
    assert c["AuditLog"] == 1

    regular = select(func.count()).select_from(Playlist).where(Playlist.kind == PlaylistKind.regular)
    watch_later = select(func.count()).select_from(Playlist).where(Playlist.kind == PlaylistKind.watch_later)
    assert (await db.execute(regular)).scalar_one() == len(seed.PLAYLISTS)
    assert (await db.execute(watch_later)).scalar_one() == len(seed.WATCH_LATER)

    open_reports = select(func.count()).select_from(Report).where(Report.status == ReportStatus.open)
    assert c["Report"] == 3
    assert (await db.execute(open_reports)).scalar_one() == 2

    # сценарий глазами пользователя: вход, лента, уведомления, раздача файла
    login = {"email": "bob@example.com", "password": seed.DEMO_PASSWORD}
    assert (await client.post("/api/auth/login", json=login)).status_code == 200

    feed = (await client.get("/api/videos", params={"limit": 50})).json()["items"]
    public = [v for v in seed.VIDEOS if v.visibility.value == "public" and not v.hidden]
    assert len(feed) == len(public)

    r = await client.get(f"/api/videos/{feed[0]['id']}/stream")
    assert r.status_code == 200 and r.headers["x-accel-redirect"].endswith("/720.mp4")

    # alice (5 ч), alice (30 ч), carol (20 ч): публичные видео подписок за последние 48 часов
    assert (await client.get("/api/notifications/count")).json() == {"count": 3}


async def test_seed_is_idempotent(assets, db):
    await seed.run(assets)
    first = await counts(db)
    ids = set((await db.execute(select(Video.id))).scalars())

    await seed.run(assets)
    assert await counts(db) == first
    assert set((await db.execute(select(Video.id))).scalars()) == ids


async def test_seed_without_assets_fails_clearly(tmp_path):
    with pytest.raises(SystemExit):
        await seed.run(tmp_path)