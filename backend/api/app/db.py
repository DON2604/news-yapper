from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def normalize_database_url(url: str) -> str:
    """Neon/Heroku style URLs -> SQLAlchemy psycopg3 driver URL."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _connect_args(url: str) -> dict[str, Any]:
    host = urlsplit(url).hostname or ""
    # Neon's pooled endpoint runs PgBouncer in transaction mode, where
    # server-side prepared statements are not guaranteed to survive.
    if "-pooler" in host:
        return {"prepare_threshold": None}
    return {}


@lru_cache(maxsize=4)
def get_engine(url: str | None = None) -> Engine:
    raw = url or get_settings().database_url
    if not raw:
        raise RuntimeError(
            "DATABASE_URL is not configured. Set your Neon URL in .env or in the host's environment."
        )
    normalized = normalize_database_url(raw)
    return create_engine(
        normalized,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args=_connect_args(normalized),
    )


@lru_cache(maxsize=4)
def _session_factory(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(url), autoflush=False, expire_on_commit=False)


def SessionLocal() -> Session:  # noqa: N802 - mirrors the conventional factory name
    return _session_factory()()


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
