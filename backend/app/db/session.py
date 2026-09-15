from __future__ import annotations

from collections.abc import AsyncIterator, Generator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base


def sync_database_url(url: str | None = None) -> str:
    raw = (url or settings.database_url).strip()
    if raw.startswith("sqlite+aiosqlite://"):
        return "sqlite://" + raw[len("sqlite+aiosqlite://") :]
    return raw


def _ensure_sqlite_parent(url: str) -> None:
    if not url.startswith("sqlite"):
        return
    path = url.split("///", 1)[-1]
    if path in {":memory:", ""} or path.startswith(":memory:"):
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _apply_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


_sync_url = sync_database_url()
_ensure_sqlite_parent(_sync_url)

engine = create_async_engine(settings.database_url, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

sync_engine = create_engine(
    _sync_url,
    future=True,
    connect_args={"check_same_thread": False} if _sync_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False, autoflush=False)

if _sync_url.startswith("sqlite"):
    event.listen(sync_engine, "connect", _apply_sqlite_pragmas)


def get_sync_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def session_scope() -> Session:
    return SessionLocal()


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


def init_database() -> None:
    from app.db import models  # noqa: F401

    _ensure_sqlite_parent(sync_database_url())
    Base.metadata.create_all(bind=sync_engine)
    with sync_engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()
