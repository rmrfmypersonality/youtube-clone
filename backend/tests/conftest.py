import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path



from sqlalchemy.engine import make_url

# Это должно выполниться ДО импорта приложения: engine и настройки создаются при импорте.
# Тесты всегда идут в отдельную БД <имя>_test и во временную папку для файлов.
_base_url = make_url(os.environ["DATABASE_URL"])
_test_db_name = f"{_base_url.database}_test"
_media_root = tempfile.mkdtemp(prefix="yt-media-test-")
os.environ["DATABASE_URL"] = _base_url.set(database=_test_db_name).render_as_string(hide_password=False)
os.environ["MEDIA_ROOT"] = _media_root
os.environ["APP_ENV"] = "test"
os.environ["COOKIE_SECURE"] = "false"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select, text, update  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Category, Role, User, Video, VideoStatus, Visibility  # noqa: E402
from app.core.time import utcnow  # noqa: E402


BACKEND_DIR = Path(__file__).resolve().parent.parent
PASSWORD = "correct-horse-battery"


async def _recreate_test_db() -> None:
    admin = create_async_engine(_base_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{_test_db_name}" WITH (FORCE)'))
        await conn.execute(text(f'CREATE DATABASE "{_test_db_name}"'))
    await admin.dispose()


def pytest_configure(config):
    """Каждый прогон: чистая БД + миграции с нуля (заодно проверяем, что миграции рабочие)."""
    asyncio.run(_recreate_test_db())
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
async def clean_db():
    yield
    tables = ", ".join(
        f'"{t.name}"' for t in Base.metadata.sorted_tables if t.name != "categories"
    )  # categories наполняет миграция, стирать её нельзя
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    for child in Path(_media_root).iterdir():
        shutil.rmtree(child, ignore_errors=True)


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def make_client():
    """Фабрика независимых клиентов (у каждого свои куки). С username сразу регистрирует юзера."""
    clients: list[AsyncClient] = []

    async def factory(username: str | None = None) -> AsyncClient:
        c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        clients.append(c)
        if username:
            r = await c.post(
                "/api/auth/register",
                json={"email": f"{username}@example.com", "username": username, "password": PASSWORD},
            )
            assert r.status_code == 201, r.text
        return c

    yield factory
    for c in clients:
        await c.aclose()


@pytest.fixture
async def db():
    async with SessionLocal() as session:
        yield session


@pytest.fixture(scope="session")
def sample_video(tmp_path_factory) -> bytes:
    """Настоящее 2-секундное видео 640x360 со звуком, сгенерированное ffmpeg."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg не установлен")
    path = tmp_path_factory.mktemp("sample") / "sample.mp4"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=640x360:rate=24",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path),
        ],
        check=True,
    )
    return path.read_bytes()

@pytest.fixture
async def set_role(db):
    async def _set(username: str, role: Role) -> None:
        await db.execute(update(User).where(User.username == username).values(role=role))
        await db.commit()

    return _set


@pytest.fixture
async def make_video(db):
    """Создаёт видео напрямую в БД (минуя загрузку и воркер). Файлы на диске не нужны."""

    async def factory(
        owner: str,
        *,
        title: str = "Test video",
        visibility: Visibility = Visibility.public,
        status: VideoStatus = VideoStatus.ready,
        hidden: bool = False,
        category: str = "other"
    ) -> Video:
        owner_id = (await db.execute(select(User.id).where(User.username == owner))).scalar_one()
        category_id = (
            await db.execute(select(Category.id).where(Category.slug == category))
        ).scalar_one()
        video = Video(
            owner_id=owner_id,
            title=title,
            visibility=visibility,
            status=status,
            hidden_by_moderation=hidden,
            category_id=category_id,
        )
        db.add(video)
        await db.flush()
        if status == VideoStatus.ready:
            base = f"videos/{video.id}"
            video.path_720, video.path_360 = f"{base}/720.mp4", f"{base}/360.mp4"
            video.thumbnail_path, video.duration_seconds = f"{base}/thumb.jpg", 10.0
            video.published_at = utcnow()
        await db.commit()
        return video

    return factory