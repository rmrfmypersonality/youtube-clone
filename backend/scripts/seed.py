"""Идемпотентный сид демо-данных.

Запуск: docker compose exec api python -m scripts.seed
Нужны применённые миграции и видеофайлы в seed_assets/ (в контейнере это /seed_assets).
"""

import asyncio
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.core.time import utcnow
from app.models import (
    AuditLog,
    Category,
    Channel,
    Comment,
    Like,
    Playlist,
    PlaylistKind,
    Report,
    ReportReason,
    ReportStatus,
    Role,
    Subscription,
    User,
    Video,
    VideoStatus,
    Visibility,
    WatchHistory,
)
from app.repositories.playlists import PlaylistRepository
from app.repositories.video_shares import ShareRepository
from app.storage import get_storage
from worker import ffmpeg

DEMO_PASSWORD = "DemoPass123"
ASSET_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv"}
FFMPEG_TIMEOUT = 600.0

# username, название канала, роль, описание канала
USERS = [
    ("moderator", "Модератор", Role.moderator, "Модератор демо-стенда."),
    ("alice", "Алиса: музыка и заметки", Role.user, "Музыка для работы и новости канала."),
    ("bob", "Боб в пути", Role.user, "Наука и путешествия."),
    ("carol", "Кэрол учит", Role.user, "Уроки и игровые стримы."),
    ("dave", "Дейв о спорте", Role.user, "Спорт, кино и всё остальное."),
]


@dataclass(frozen=True)
class VideoSpec:
    owner: str
    title: str
    description: str
    category: str  # slug из справочника категорий
    visibility: Visibility = Visibility.public
    hours_ago: int = 100
    views: int = 0
    hidden: bool = False  # скрыто модерацией


V = Visibility
# Индекс в этом списке используется во всех структурах ниже
VIDEOS = [
    VideoSpec("alice", "Знакомство с каналом", "Коротко о том, что здесь будет.", "other", hours_ago=5, views=1250),
    VideoSpec("alice", "Музыка для работы", "Спокойная подборка для концентрации.", "music", hours_ago=30, views=48200),
    VideoSpec("alice", "Закрытый показ для друзей", "Смотреть могут только приглашённые.", "other", V.private, 60, 12),
    VideoSpec("bob", "Что нового в науке", "Обзор интересных открытий месяца.", "science", hours_ago=72, views=15300),
    VideoSpec("bob", "Путешествие по северу", "Две недели дороги в одном видео.", "travel", hours_ago=120, views=923000),
    VideoSpec("bob", "Доступно только по ссылке", "Это видео не видно в ленте и поиске.", "entertainment", V.unlisted, 150, 310),
    VideoSpec("carol", "Основы видеомонтажа", "Первые шаги: нарезка, переходы, звук.", "education", hours_ago=20, views=5400),
    VideoSpec("carol", "Игровой стрим: лучшие моменты", "Нарезка самого интересного.", "gaming", hours_ago=260, views=2300000),
    VideoSpec("carol", "Личный черновик", "Пока не для публики.", "other", V.private, 300, 0),
    VideoSpec("dave", "Спортивный итог недели", "Главные матчи и сенсации.", "sports", hours_ago=400, views=870),
    VideoSpec("dave", "Видео с нарушением правил", "Скрыто модератором после жалобы.", "entertainment", hours_ago=500, views=66, hidden=True),
    VideoSpec("dave", "Разбор сцены из фильма", "Покадровый разбор любимой сцены.", "film", hours_ago=600, views=3100),
]

# индекс видео -> {пользователь: 1 (лайк) | -1 (дизлайк)}
LIKES = {
    0: {"bob": 1, "carol": 1, "dave": 1, "moderator": 1},
    1: {"bob": 1, "carol": 1, "dave": -1},
    3: {"alice": 1, "carol": 1},
    4: {"alice": 1, "carol": 1, "dave": 1},
    6: {"alice": 1, "bob": 1},
    7: {"alice": 1, "bob": 1, "dave": 1},
    9: {"bob": 1},
    11: {"alice": 1, "carol": -1},
}

SPAM_TEXT = "Купите подписчиков на нашем сайте, дёшево!"

# индекс видео, автор, текст, текст родительского комментария (для ответа); родитель идёт раньше ответа
COMMENTS = [
    (0, "bob", "Отличное начало, подписался!", None),
    (0, "carol", "Жду новых выпусков.", None),
    (0, "alice", "Спасибо! Новые видео уже в работе.", "Отличное начало, подписался!"),
    (1, "dave", "Идеально под работу.", None),
    (1, "bob", "Добавил в плейлист.", None),
    (3, "alice", "Интересный разбор, спасибо.", None),
    (3, "dave", SPAM_TEXT, None),
    (4, "carol", "Какие места понравились больше всего?", None),
    (4, "bob", "Про север будет отдельное видео.", "Какие места понравились больше всего?"),
    (7, "alice", "Момент на второй минуте просто огонь.", None),
    (9, "bob", "Хороший итог недели.", None),
]

SUBSCRIPTIONS = [  # подписчик, канал (по username владельца)
    ("bob", "alice"),
    ("bob", "carol"),
    ("carol", "alice"),
    ("dave", "alice"),
    ("dave", "bob"),
    ("alice", "bob"),
    ("moderator", "alice"),
]
SHARES = [(2, "bob")]  # приватное видео 2 открыто для bob
PLAYLISTS = [  # владелец, название, доступ, индексы видео
    ("alice", "Любимая музыка", V.public, [1, 4]),
    ("bob", "Наука и путешествия", V.public, [3, 4, 6]),
    ("bob", "Только по ссылке", V.unlisted, [0, 3]),
    ("carol", "Для себя", V.private, [7, 8]),
]
WATCH_LATER = [("bob", [0, 1, 7]), ("alice", [3])]
HISTORY = {"bob": [3, 0, 1], "alice": [7], "carol": [0]}  # от старых просмотров к новым


@dataclass
class Prepared:
    dir: Path
    duration: float


def log(message: str) -> None:
    print(message, flush=True)


async def usable_assets(assets_dir: Path) -> list[Path]:
    if not assets_dir.is_dir():
        return []
    result = []
    for path in sorted(assets_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in ASSET_SUFFIXES:
            continue
        try:
            await ffmpeg.probe(path, FFMPEG_TIMEOUT)
        except (ffmpeg.PermanentError, ffmpeg.ProcessingError) as exc:
            log(f"  ! {path.name}: пропущен ({exc})")
            continue
        result.append(path)
    return result


async def prepare(asset: Path, workdir: Path) -> Prepared:
    """Один раз кодирует исходник в 720p, 360p и превью, дальше файлы только копируются."""
    info = await ffmpeg.probe(asset, FFMPEG_TIMEOUT)
    out = workdir / asset.stem
    out.mkdir(parents=True, exist_ok=True)
    await ffmpeg.transcode(asset, out / "720.mp4", 720, FFMPEG_TIMEOUT)
    await ffmpeg.transcode(asset, out / "360.mp4", 360, FFMPEG_TIMEOUT)
    await ffmpeg.thumbnail(asset, out / "thumb.jpg", min(info.duration * 0.25, 5.0), FFMPEG_TIMEOUT)
    return Prepared(dir=out, duration=info.duration)


async def ensure_users(session: AsyncSession) -> dict[str, User]:
    names = [u[0] for u in USERS]
    existing = {
        u.username.lower()
        for u in (await session.execute(select(User).where(User.username.in_(names)))).scalars().unique()
    }
    password_hash = None
    seen_at = utcnow() - timedelta(hours=48)  # от этого момента считаются «новые» уведомления
    for username, name, role, about in USERS:
        if username in existing:
            continue
        password_hash = password_hash or hash_password(DEMO_PASSWORD)
        session.add(
            User(
                email=f"{username}@example.com",
                username=username,
                password_hash=password_hash,
                role=role,
                notifications_seen_at=seen_at,
                channel=Channel(handle=username, name=name, description=about),
            )
        )
        log(f"  + пользователь {username} ({role.value})")
    await session.commit()
    rows = (await session.execute(select(User).where(User.username.in_(names)))).scalars().unique()
    return {u.username.lower(): u for u in rows}


async def ensure_videos(
    session: AsyncSession, users: dict[str, User], assets_dir: Path
) -> dict[int, Video]:
    categories = {c.slug: c.id for c in (await session.execute(select(Category))).scalars()}
    storage = get_storage()
    videos: dict[int, Video] = {}
    assets: list[Path] | None = None
    prepared: dict[Path, Prepared] = {}

    with tempfile.TemporaryDirectory(prefix="seed-") as tmp:
        for index, spec in enumerate(VIDEOS):
            owner = users[spec.owner]
            found = await session.execute(
                select(Video).where(Video.owner_id == owner.id, Video.title == spec.title)
            )
            existing = found.scalar_one_or_none()
            if existing is not None:
                videos[index] = existing
                continue

            if assets is None:  # файлы нужны, только если есть что создавать
                assets = await usable_assets(assets_dir)
                if not assets:
                    raise SystemExit(
                        "В seed_assets/ нет подходящих видео (mp4, mov, webm, mkv). "
                        "Положите туда файлы и запустите сид снова."
                    )
            asset = assets[index % len(assets)]
            if asset not in prepared:
                log(f"  … кодирую {asset.name}")
                prepared[asset] = await prepare(asset, Path(tmp))
            files = prepared[asset]

            published = utcnow() - timedelta(hours=spec.hours_ago)
            video = Video(
                owner_id=owner.id,
                category_id=categories[spec.category],
                title=spec.title,
                description=spec.description,
                status=VideoStatus.ready,
                visibility=spec.visibility,
                hidden_by_moderation=spec.hidden,
                duration_seconds=files.duration,
                views_count=spec.views,
                created_at=published,
                published_at=published,
            )
            session.add(video)
            await session.flush()  # нужен id для путей в хранилище
            base = f"videos/{video.id}"
            video.path_720, video.path_360 = f"{base}/720.mp4", f"{base}/360.mp4"
            video.thumbnail_path = f"{base}/thumb.jpg"
            try:
                for name in ("720.mp4", "360.mp4", "thumb.jpg"):
                    shutil.copyfile(files.dir / name, storage.local_path(f"{base}/{name}", for_write=True))
                await session.commit()
            except BaseException:
                await session.rollback()
                await storage.delete_prefix(base)
                raise
            videos[index] = video
            log(f"  + видео «{spec.title}» ({spec.visibility.value})")
    return videos


async def ensure_social(
    session: AsyncSession, users: dict[str, User], videos: dict[int, Video]
) -> None:
    long_ago = utcnow() - timedelta(days=30)
    for subscriber, target in SUBSCRIPTIONS:
        await session.execute(
            insert(Subscription)
            .values(
                subscriber_id=users[subscriber].id,
                channel_id=users[target].channel.id,
                created_at=long_ago,
            )
            .on_conflict_do_nothing()
        )

    shares = ShareRepository(session)
    for index, username in SHARES:
        await shares.add(videos[index].id, users[username].id)

    for index, votes in LIKES.items():
        for username, value in votes.items():
            await session.execute(
                insert(Like)
                .values(user_id=users[username].id, video_id=videos[index].id, value=value)
                .on_conflict_do_nothing()
            )
    await session.commit()
    log("  + подписки, доступы, лайки")


async def ensure_comments(
    session: AsyncSession, users: dict[str, User], videos: dict[int, Video]
) -> None:
    for index, author, text, parent_text in COMMENTS:
        video, user = videos[index], users[author]
        parent_id = None
        if parent_text is not None:
            found = await session.execute(
                select(Comment.id).where(
                    Comment.video_id == video.id,
                    Comment.parent_id.is_(None),
                    Comment.text == parent_text,
                )
            )
            parent_id = found.scalars().first()
            if parent_id is None:
                raise RuntimeError(f"Не найден родительский комментарий: {parent_text!r}")
        same_parent = Comment.parent_id.is_(None) if parent_id is None else Comment.parent_id == parent_id
        exists = await session.execute(
            select(Comment.id).where(
                Comment.video_id == video.id, Comment.user_id == user.id, Comment.text == text, same_parent
            )
        )
        if exists.first() is not None:
            continue
        session.add(Comment(video_id=video.id, user_id=user.id, parent_id=parent_id, text=text))
        await session.flush()  # порядок id совпадает с порядком в списке: родитель раньше ответа
    await session.commit()
    log("  + комментарии")


async def ensure_playlists(
    session: AsyncSession, users: dict[str, User], videos: dict[int, Video]
) -> None:
    repo = PlaylistRepository(session)
    for owner, title, visibility, indexes in PLAYLISTS:
        user = users[owner]
        found = await session.execute(
            select(Playlist).where(
                Playlist.owner_id == user.id,
                Playlist.title == title,
                Playlist.kind == PlaylistKind.regular,
            )
        )
        playlist = found.scalar_one_or_none()
        if playlist is None:
            playlist = Playlist(owner_id=user.id, title=title, visibility=visibility)
            session.add(playlist)
            await session.flush()
        for index in indexes:
            await repo.add_item(playlist.id, videos[index].id)

    for owner, indexes in WATCH_LATER:
        playlist = await repo.ensure_watch_later(users[owner].id)
        for index in indexes:
            await repo.add_item(playlist.id, videos[index].id)

    for username, indexes in HISTORY.items():
        for index in indexes:
            await session.execute(
                insert(WatchHistory)
                .values(user_id=users[username].id, video_id=videos[index].id)
                .on_conflict_do_nothing()
            )
    await session.commit()
    log("  + плейлисты, «Смотреть позже», история")


async def ensure_reports(
    session: AsyncSession, users: dict[str, User], videos: dict[int, Video]
) -> None:
    moderator = users["moderator"]

    async def add_report(
        reporter: str,
        reason: ReportReason,
        details: str,
        *,
        video: Video | None = None,
        comment: Comment | None = None,
        resolved: bool = False,
    ) -> bool:
        target = Report.video_id == video.id if video is not None else Report.comment_id == comment.id
        found = await session.execute(
            select(Report.id).where(Report.reporter_id == users[reporter].id, target)
        )
        if found.first() is not None:
            return False
        session.add(
            Report(
                reporter_id=users[reporter].id,
                video_id=video.id if video is not None else None,
                comment_id=comment.id if comment is not None else None,
                reason=reason,
                details=details,
                status=ReportStatus.resolved if resolved else ReportStatus.open,
                handled_by_id=moderator.id if resolved else None,
                handled_at=utcnow() if resolved else None,
            )
        )
        return True

    spam = (await session.execute(select(Comment).where(Comment.text == SPAM_TEXT))).scalars().first()
    await add_report("carol", ReportReason.copyright, "Использована музыка без лицензии.", video=videos[9])
    await add_report("bob", ReportReason.spam, "Реклама в комментариях.", comment=spam)

    hidden = videos[10]
    created = await add_report(
        "alice", ReportReason.abuse, "Оскорбления в видео.", video=hidden, resolved=True
    )
    if created:  # запись в журнале только вместе с самой жалобой, чтобы повторный запуск не дублировал её
        session.add(
            AuditLog(
                actor_id=moderator.id,
                action="video.hide",
                target_type="video",
                target_id=hidden.id,
                details={"title": hidden.title, "owner_id": hidden.owner_id},
            )
        )
    await session.commit()
    log("  + жалобы и журнал модерации")


async def run(assets_dir: Path) -> None:
    async with SessionLocal() as session:
        log("Пользователи")
        users = await ensure_users(session)
        log("Видео")
        videos = await ensure_videos(session, users, assets_dir)
        log("Взаимодействие")
        await ensure_social(session, users, videos)
        await ensure_comments(session, users, videos)
        await ensure_playlists(session, users, videos)
        await ensure_reports(session, users, videos)

    log(f"\nГотово. Демо-пользователи (пароль у всех: {DEMO_PASSWORD}):")
    for username, _, role, _ in USERS:
        log(f"  {username}@example.com  ({role.value})")


def main() -> None:
    assets_dir = Path(os.environ.get("SEED_ASSETS_DIR", "/seed_assets"))

    async def go() -> None:
        try:
            await run(assets_dir)
        finally:
            await engine.dispose()

    asyncio.run(go())


if __name__ == "__main__":
    main()