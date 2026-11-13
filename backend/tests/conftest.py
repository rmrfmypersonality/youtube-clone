import asyncio
import os
from pathlib import Path

from sqlalchemy.engine import make_url

# Это должно выполниться ДО импорта приложения: engine создаётся при импорте.
# Тесты всегда идут в отдельную БД <имя>_test, рабочая БД не затрагивается.
_base_url = make_url(os.environ["DATABASE_URL"])
_test_db_name = f"{_base_url.database}_test"
os.environ["DATABASE_URL"] = _base_url.set(database=_test_db_name).render_as_string(hide_password=False)
os.environ["APP_ENV"] = "test"
os.environ["COOKIE_SECURE"] = "false"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent


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
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def db():
    async with SessionLocal() as session:
        yield session