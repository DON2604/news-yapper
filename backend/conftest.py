"""Shared pytest setup: real Postgres (TEST_DATABASE_URL), schema built by the Alembic migration."""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import jwt
import psycopg
import pytest

from app.config import Settings

_TEST_URL = os.environ.get("TEST_DATABASE_URL") or Settings().test_database_url
if not _TEST_URL:
    raise RuntimeError("TEST_DATABASE_URL is not set. Run `npm run setup` and `npm run db:start` first.")
TEST_SECRET = "test-secret-0123456789-abcdefghijklmnop"
os.environ.update(
    {
        "DATABASE_URL": _TEST_URL,
        "DIRECT_URL": _TEST_URL,
        "API_JWT_SECRET": TEST_SECRET,
        "DEMO_MODE": "true",
        "ENABLE_GEMINI": "false",
        "ENABLE_GROQ": "false",
        "ENABLE_LIVE_INGESTION": "false",
        "ADMIN_EMAILS": "boss@example.com",
        "CRUNCH_COOLDOWN_SECONDS": "0",
    }
)

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.db import SessionLocal, get_engine  # noqa: E402
from app.models import (  # noqa: E402
    Article,
    Base,
    Event,
    EventSource,
    Source,
    SourceItem,
    User,
    UserPreferences,
)


def _plain_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


def _ensure_database(url: str) -> None:
    plain = _plain_url(url)
    db_name = plain.rsplit("/", 1)[1].split("?")[0]
    admin_url = plain.rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(admin_url, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{db_name}"')


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    from alembic import command
    from alembic.config import Config

    _ensure_database(_TEST_URL)
    with psycopg.connect(_plain_url(_TEST_URL), autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    root = os.path.dirname(os.path.abspath(__file__))
    cfg = Config(os.path.join(root, "api", "alembic.ini"))
    command.upgrade(cfg, "head")
    yield
    get_engine().dispose()


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    yield
    from app.security.rate_limit import limiter

    limiter.reset()
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with get_engine().begin() as conn:
        conn.exec_driver_sql(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE")


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def db() -> Iterator[Any]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Iterator[Any]:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def make_token(
    sub: str, *, scope: str = "user", ttl: int = 300, secret: str = TEST_SECRET, **extra: Any
) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "iss": "aks-web",
        "aud": "aks-api",
        "iat": now,
        "exp": now + ttl,
        "scope": scope,
        **extra,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def token() -> Callable[..., str]:
    return make_token


@pytest.fixture
def make_user() -> Callable[..., User]:
    def factory(name: str = "Asha", *, admin: bool = False, **prefs: Any) -> User:
        with SessionLocal() as session:
            user = User(auth_provider_id=f"test:{uuid.uuid4().hex}", display_name=name, is_admin=admin)
            session.add(user)
            session.flush()
            session.add(UserPreferences(user_id=user.id, **prefs))
            session.commit()
            session.refresh(user)
            return user

    return factory


@pytest.fixture
def auth() -> Callable[[User], dict[str, str]]:
    def headers(user: User) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(str(user.id))}"}

    return headers


@pytest.fixture
def seeded() -> dict[str, int]:
    from app.seed.demo import seed_demo
    from app.seed.sources import seed_sources

    with SessionLocal() as session:
        seed_sources(session)
        summary = seed_demo(session)
        session.commit()
    return summary


@pytest.fixture
def make_source() -> Callable[..., Source]:
    def factory(
        slug: str = "test-feed",
        *,
        tier: str = "A",
        type_: str = "rss",
        feed_url: str | None = None,
        **kw: Any,
    ) -> Source:
        with SessionLocal() as session:
            source = Source(
                slug=slug,
                name=kw.pop("name", slug.replace("-", " ").title()),
                type=type_,
                tier=tier,
                feed_url=feed_url or f"https://{slug}.example.org/rss.xml",
                home_url=f"https://{slug}.example.org/",
                enabled=kw.pop("enabled", True),
                legal_notes="test fixture",
                authority_weight=kw.pop("authority_weight", 1.0 if tier == "A" else 0.4),
                **kw,
            )
            session.add(source)
            session.commit()
            session.refresh(source)
            return source

    return factory


@pytest.fixture
def make_event(make_source: Callable[..., Source]) -> Callable[..., Event]:
    """An event with one source item. status='published' also creates an article."""

    def factory(
        title: str = "Cabinet approves the National Fixture Mission with an outlay of 1500 crore",
        *,
        excerpt: str = "The Union Cabinet on Monday approved the National Fixture Mission with an outlay of 1500 crore for 2026-27.",
        status: str = "discovered",
        topic: str = "polity",
        relevance: float = 60.0,
        sensitive: bool = False,
        source: Source | None = None,
        day: date | None = None,
    ) -> Event:
        src = source or make_source(f"src-{uuid.uuid4().hex[:6]}")
        with SessionLocal() as session:
            item = SourceItem(
                source_id=src.id,
                canonical_url=f"https://{src.slug}.example.org/item/{uuid.uuid4().hex}",
                original_url=f"https://{src.slug}.example.org/item/{uuid.uuid4().hex[:8]}",
                original_title=title,
                short_excerpt=excerpt,
                publisher=src.name,
                published_at=datetime.now(UTC) - timedelta(hours=2),
                content_hash=uuid.uuid4().hex,
                fetch_status="clustered",
            )
            session.add(item)
            session.flush()
            event = Event(
                topic=topic,
                title=title,
                slug=f"evt-{uuid.uuid4().hex[:10]}",
                status=status,
                date=day or datetime.now(UTC).date(),
                relevance_score=relevance,
                cluster_hash=item.content_hash,
                sensitive=sensitive,
            )
            session.add(event)
            session.flush()
            session.add(EventSource(event_id=event.id, source_item_id=item.id, source_role="primary"))
            if status in ("published", "needs_review", "generated"):
                session.add(
                    Article(
                        event_id=event.id,
                        headline=f"AI headline for {title}",
                        banglish_summary="Bhai, Cabinet notun mission approve korlo.",
                        neutral_summary=excerpt,
                        why_matters="Schemes are asked in exams.",
                        key_facts=[{"claim": excerpt, "source_item_ids": [str(item.id)]}],
                        exam_tags=["SSC"],
                        category=topic,
                        importance_score=70,
                        content_hash=uuid.uuid4().hex,
                        verified_at=datetime.now(UTC) if status == "published" else None,
                        published_at=datetime.now(UTC) if status == "published" else None,
                    )
                )
            session.commit()
            session.refresh(event)
            return event

    return factory
