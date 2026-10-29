from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import func, select

from adapters.base import RawItem, SourceConfig
from adapters.gdelt import GDELTAdapter, parse_gdelt
from adapters.http import FetchError
from adapters.rss import parse_feed
from app.db import SessionLocal
from app.models import Article, Event, EventSource, IngestionRun, Source, SourceItem
from pipeline.deduplicate import is_same_story, slugify
from pipeline.ingest import is_due, run_ingestion
from pipeline.normalize import (
    canonical_url,
    make_excerpt,
    normalize_item,
    split_publisher_suffix,
    strip_html,
    to_utc,
)
from pipeline.relevance import categorize, is_sensitive, score

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
CFG = SourceConfig(
    id=None, slug="pib", name="PIB", type="rss", feed_url=None, home_url=None, country="IN",
    language="en", config={}, last_success_at=None,
)  # fmt: skip


# -- normalisation --------------------------------------------------------------------------------


def test_canonical_url_strips_tracking_and_normalises():
    a = canonical_url("http://WWW.Example.com/news/story/?utm_source=x&id=7&fbclid=abc#frag")
    b = canonical_url("https://example.com/news/story?id=7")
    assert a == b == "https://example.com/news/story?id=7"
    assert canonical_url("https://pib.gov.in/PressReleasePage.aspx?PRID=1&utm_medium=rss") == (
        "https://pib.gov.in/PressReleasePage.aspx?PRID=1"
    )


def test_text_helpers():
    assert strip_html("<p>Hello&nbsp;<b>world</b></p>") == "Hello world"
    long = "word " * 200
    excerpt = make_excerpt(long, 50)
    assert excerpt is not None and len(excerpt) <= 51 and excerpt.endswith("…")
    assert split_publisher_suffix("Big launch today - Example Times") == ("Big launch today", "Example Times")
    assert to_utc(None, NOW) == (None, "missing")
    assert to_utc(datetime(2100, 1, 1, tzinfo=UTC), NOW) == (None, "future")
    naive = to_utc(datetime(2026, 10, 27, 10, 0), NOW)
    assert naive[0] is not None and naive[0].tzinfo is not None


def test_normalize_item_rejects_bad_items():
    assert normalize_item(RawItem(title="", url="https://x.org/a"), CFG, NOW) is None
    assert normalize_item(RawItem(title="T", url="javascript:alert(1)"), CFG, NOW) is None
    item = normalize_item(
        RawItem(
            title="A <b>bold</b> headline", url="https://x.org/a?utm_campaign=z", summary="<p>Short body</p>"
        ),
        CFG,
        NOW,
    )
    assert item is not None
    assert item.title == "A bold headline" and item.excerpt == "Short body"
    assert item.canonical_url == "https://x.org/a" and item.metadata["timestamp_problem"] == "missing"


# -- adapters -----------------------------------------------------------------------------------


def test_parse_pib_fixture(fixture_bytes):
    items = parse_feed(fixture_bytes("pib_rss.xml"), default_publisher="Press Information Bureau")
    assert len(items) == 4  # the untitled item is dropped
    first = items[0]
    assert first.title.startswith("Cabinet approves the National Fixture Mission")
    assert first.published == datetime(2026, 10, 26, 5, 0, tzinfo=UTC)
    assert first.publisher == "Press Information Bureau"


def test_parse_rbi_fixture_strips_html(fixture_bytes):
    items = parse_feed(fixture_bytes("rbi_rss.xml"), default_publisher="Reserve Bank of India")
    normalized = normalize_item(items[0], CFG, NOW)
    assert normalized is not None and "<table" not in (normalized.excerpt or "")
    assert "2.5 lakh" in (normalized.excerpt or "")


def test_parse_google_news_publisher_suffix(fixture_bytes):
    items = parse_feed(fixture_bytes("google_news.xml"), default_publisher=None, publisher_in_title=True)
    assert items[0].title == "Fixture launch succeeds in orbit test"
    assert items[0].publisher == "Example Times"


def test_parse_feed_rejects_garbage():
    with pytest.raises(FetchError):
        parse_feed(b"<html><body>Access Denied</body></html><<<", default_publisher=None)


def test_parse_gdelt(fixture_bytes):
    items = parse_gdelt(fixture_bytes("gdelt.json"))
    assert len(items) == 2
    assert items[0].published == datetime(2026, 10, 26, 6, 15, tzinfo=UTC)
    assert items[0].published_is_discovery_time is True
    with pytest.raises(FetchError):
        parse_gdelt(b"Invalid query: your search contained too short words")


def test_gdelt_adapter_bounds_window_and_spaces_requests(make_fetcher, fixture_bytes):
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        seen.append(request.url)
        return httpx.Response(200, content=fixture_bytes("gdelt.json"))

    sleeps: list[float] = []
    source = SourceConfig(
        id=None, slug="gdelt", name="GDELT", type="gdelt", feed_url="https://api.gdeltproject.org/api/v2/doc/doc",
        home_url=None, country=None, language="en",
        config={"queries": ["india scheme", "rbi policy"], "window_hours": 500, "max_records": 9999},
        last_success_at=None,
    )  # fmt: skip
    fetcher = make_fetcher(handler, {"api.gdeltproject.org"})
    items = GDELTAdapter(sleep=sleeps.append).fetch(source, fetcher, NOW)
    assert len(items) == 2 and len(seen) == 2 and sleeps == [6.0]
    params = dict(seen[0].params)
    assert params["mode"] == "artlist" and params["format"] == "json" and params["maxrecords"] == "250"
    assert params["startdatetime"] == "20261025120000" and params["enddatetime"] == "20261028120000"


# -- SSRF / politeness ----------------------------------------------------------------------------


def _ok(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/robots.txt":
        return httpx.Response(404)
    return httpx.Response(200, content=b"<rss></rss>")


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example.com/feed",
        "file:///etc/passwd",
        "ftp://feeds.example.org/x",
        "https://feeds.example.org:8443/x",
        "https://user:pass@feeds.example.org/x",
    ],
)
def test_fetcher_blocks_unsafe_urls(make_fetcher, url):
    fetcher = make_fetcher(_ok, {"feeds.example.org"})
    with pytest.raises(FetchError) as exc:
        fetcher.get(url)
    assert exc.value.kind == "blocked"


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "::1", "192.168.1.10"])
def test_fetcher_blocks_private_addresses(make_fetcher, address):
    fetcher = make_fetcher(_ok, {"feeds.example.org"}, resolver=lambda host: [address])
    with pytest.raises(FetchError) as exc:
        fetcher.get("https://feeds.example.org/rss")
    assert exc.value.kind == "blocked"


def test_fetcher_redirects_only_within_allowlist(make_fetcher):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path == "/inside":
            return httpx.Response(302, headers={"location": "https://cdn.feeds.example.org/final"})
        if request.url.path == "/outside":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})
        return httpx.Response(200, content=b"ok")

    fetcher = make_fetcher(handler, {"feeds.example.org"})
    assert fetcher.get("https://feeds.example.org/inside").content == b"ok"
    with pytest.raises(FetchError) as exc:
        fetcher.get("https://feeds.example.org/outside")
    assert exc.value.kind == "blocked"


def test_fetcher_size_cap(make_fetcher):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, content=b"x" * 5000)

    with pytest.raises(FetchError) as exc:
        make_fetcher(handler, {"feeds.example.org"}, max_bytes=1000).get("https://feeds.example.org/big")
    assert exc.value.kind == "size"


def test_fetcher_retries_transient_errors_then_succeeds(make_fetcher):
    calls = {"n": 0}
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] == 1 else httpx.Response(200, content=b"fine")

    fetcher = make_fetcher(handler, {"feeds.example.org"}, sleep=sleeps.append)
    assert fetcher.get("https://feeds.example.org/rss").content == b"fine"
    assert calls["n"] == 2 and len(sleeps) == 1


def test_fetcher_timeout_is_bounded(make_fetcher):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        calls["n"] += 1
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(FetchError) as exc:
        make_fetcher(handler, {"feeds.example.org"}, max_retries=2).get("https://feeds.example.org/rss")
    assert exc.value.kind == "timeout" and calls["n"] == 3


def test_fetcher_does_not_retry_403(make_fetcher):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(403)
        calls["n"] += 1
        return httpx.Response(403, content=b"Access Denied")

    with pytest.raises(FetchError) as exc:
        make_fetcher(handler, {"feeds.example.org"}).get("https://feeds.example.org/rss")
    assert exc.value.status == 403 and calls["n"] == 1


def test_robots_rules(make_fetcher):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, content=b"User-agent: AajkeKiSceneBot\nDisallow: /private\n")
        return httpx.Response(200, content=b"ok")

    fetcher = make_fetcher(handler, {"feeds.example.org"})
    assert fetcher.get("https://feeds.example.org/public").content == b"ok"
    with pytest.raises(FetchError) as exc:
        fetcher.get("https://feeds.example.org/private/feed")
    assert exc.value.kind == "robots"

    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with pytest.raises(FetchError) as exc:
        make_fetcher(broken, {"feeds.example.org"}).get("https://feeds.example.org/rss")
    assert exc.value.kind == "robots" and "unreachable" in str(exc.value)


def test_same_source_templated_titles_stay_separate(settings, make_fetcher, make_source):
    """Live RBI feeds publish near-identical titles for distinct notices; they must not merge."""
    feed = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>RBI</title>
      <item><title>Reserve Bank of India imposes monetary penalty on Alpha Co-operative Bank Ltd</title>
        <link>https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=1</link>
        <pubDate>Tue, 27 Oct 2026 10:00:00 GMT</pubDate></item>
      <item><title>Reserve Bank of India imposes monetary penalty on Beta Co-operative Bank Ltd</title>
        <link>https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=2</link>
        <pubDate>Tue, 27 Oct 2026 11:00:00 GMT</pubDate></item>
    </channel></rss>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404) if request.url.path == "/robots.txt" else httpx.Response(200, content=feed)

    make_source("rbi-press", feed_url="https://www.rbi.org.in/pressreleases_rss.xml", country="IN")
    summary = run_ingestion(
        SessionLocal, settings, fetcher_factory=lambda _h: make_fetcher(handler, {"www.rbi.org.in"}), now=NOW
    )
    outcome = summary.outcomes[0]
    assert outcome.inserted == 2 and outcome.new_events == 2 and outcome.attached == 0


# -- dedupe + relevance ---------------------------------------------------------------------------


def test_story_similarity():
    assert is_same_story(
        "Cabinet approves the National Fixture Mission with an outlay of Rs 1500 crore",
        "Cabinet approves National Fixture Mission with Rs 1500 crore outlay",
    )
    assert not is_same_story("RBI keeps repo rate unchanged", "ISRO launches navigation satellite")
    assert slugify("RBI: Repo rate — unchanged!") == "rbi-repo-rate-unchanged"


def test_relevance_is_deterministic_and_labelled():
    category, hits = categorize("RBI keeps repo rate unchanged as inflation eases")
    assert category == "economy" and "repo" in hits
    assert is_sensitive("Earthquake death toll rises") and not is_sensitive("Cabinet approves scheme")
    # Regressions from the live RBI / UN feeds (2026-10-29).
    assert is_sensitive("Record heat-related deaths in 2023, WHO-partnered report finds")
    assert (
        categorize("Premature redemption under Sovereign Gold Bond (SGB) Scheme - Redemption Price")[0]
        == "economy"
    )
    assert categorize("91-Day, 182-Day and 364-Day T-Bill Auction Result: Cut-off")[0] == "economy"
    official = score(
        titles=["Cabinet approves new scheme for farmers"], excerpts=[""], tiers=["A"], authority=[1.0],
        publishers={"pib"}, latest=NOW, now=NOW,
    )  # fmt: skip
    gossip = score(
        titles=["Bollywood actor's viral dating rumours"], excerpts=[""], tiers=["B"], authority=[0.3],
        publishers={"x"}, latest=NOW, now=NOW,
    )  # fmt: skip
    assert official.score > gossip.score
    assert any("not an exam probability" in r for r in official.reasons)
    assert any("gossip penalty" in r for r in gossip.reasons)


# -- end-to-end ingestion -------------------------------------------------------------------------


@pytest.fixture
def feed_handler(fixture_bytes):
    state = {"pib": fixture_bytes("pib_rss.xml")}

    def handler(request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if path == "/robots.txt":
            return httpx.Response(404)
        if host == "pib.gov.in":
            return httpx.Response(200, content=state["pib"])
        if host == "www.rbi.org.in":
            return httpx.Response(200, content=fixture_bytes("rbi_rss.xml"))
        if host == "api.gdeltproject.org":
            return httpx.Response(200, content=fixture_bytes("gdelt.json"))
        return httpx.Response(403, content=b"Access Denied")

    handler.state = state  # type: ignore[attr-defined]
    return handler


@pytest.fixture
def ingestion_sources(make_source):
    make_source(
        "pib",
        feed_url="https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1",
        country="IN",
        default_topic="polity",
    )
    make_source(
        "rbi-press",
        feed_url="https://www.rbi.org.in/pressreleases_rss.xml",
        country="IN",
        default_topic="economy",
    )
    make_source(
        "gdelt", tier="B", type_="gdelt", feed_url="https://api.gdeltproject.org/api/v2/doc/doc",
        config={"queries": ["india scheme"], "window_hours": 24},
    )  # fmt: skip
    make_source("blocked-feed", feed_url="https://blocked.example.org/rss.xml")


def test_run_ingestion_end_to_end(settings, make_fetcher, feed_handler, ingestion_sources):
    hosts = {"pib.gov.in", "www.rbi.org.in", "api.gdeltproject.org", "blocked.example.org"}
    factory = lambda _hosts: make_fetcher(feed_handler, hosts)  # noqa: E731
    summary = run_ingestion(SessionLocal, settings, fetcher_factory=factory, now=NOW)
    by_slug = {o.slug: o for o in summary.outcomes}
    assert by_slug["pib"].inserted == 3 and by_slug["pib"].duplicates == 1
    assert by_slug["rbi-press"].inserted == 2
    assert by_slug["gdelt"].inserted == 2
    assert "HTTP 403" in (by_slug["blocked-feed"].error or "")

    with SessionLocal() as db:
        blocked = db.scalar(select(Source).where(Source.slug == "blocked-feed"))
        assert blocked.consecutive_failures == 1 and blocked.last_error
        mission = db.scalars(select(Event).where(Event.title.ilike("%National Fixture Mission%"))).all()
        assert len(mission) == 1, "PIB + GDELT copies of the same story must cluster into one event"
        sources = db.scalar(
            select(func.count()).select_from(EventSource).where(EventSource.event_id == mission[0].id)
        )
        assert sources == 2
        assert mission[0].relevance_score > 0 and mission[0].relevance_reasons
        future = db.scalar(select(SourceItem).where(SourceItem.original_title.ilike("%far future%")))
        assert future.published_at is None and future.item_metadata["timestamp_problem"] == "future"
        runs = {r.status for r in db.scalars(select(IngestionRun)).all()}
        assert runs == {"succeeded", "failed"}

    again = run_ingestion(SessionLocal, settings, fetcher_factory=factory, now=NOW)
    assert sum(o.inserted for o in again.outcomes) == 0
    assert sum(o.new_events for o in again.outcomes) == 0


def test_publisher_correction_flags_published_event(settings, make_fetcher, feed_handler, ingestion_sources):
    hosts = {"pib.gov.in", "www.rbi.org.in", "api.gdeltproject.org", "blocked.example.org"}
    factory = lambda _hosts: make_fetcher(feed_handler, hosts)  # noqa: E731
    run_ingestion(SessionLocal, settings, source_slugs=["pib"], fetcher_factory=factory, now=NOW)
    with SessionLocal() as db:
        event = db.scalar(select(Event).where(Event.title.ilike("%Test Yojana%")))
        event.status = "published"
        db.add(
            Article(
                event_id=event.id, headline="h", banglish_summary="b", neutral_summary="n", why_matters="w",
                category="polity", content_hash="corr-test",
            )
        )  # fmt: skip
        db.commit()
        event_id = event.id
    feed_handler.state["pib"] = feed_handler.state["pib"].replace(
        b"Ministry launches Test Yojana for coastal fishers",
        b"Ministry launches revised Test Yojana for fishers",
    )
    outcome = run_ingestion(
        SessionLocal, settings, source_slugs=["pib"], fetcher_factory=factory, now=NOW
    ).outcomes[0]
    assert outcome.corrected >= 1
    with SessionLocal() as db:
        event = db.get(Event, event_id)
        assert event.correction_status == "corrected" and event.correction_note


def test_source_backoff_schedule(make_source):
    source = make_source("slow-feed", fetch_interval_minutes=60)
    with SessionLocal() as db:
        src = db.get(Source, source.id)
        assert is_due(src, NOW)
        src.last_fetch_at = NOW
        src.consecutive_failures = 2
        assert not is_due(src, NOW.replace(hour=14))
        assert is_due(src, NOW.replace(hour=16, minute=1))


@pytest.mark.live
def test_live_rbi_and_un_feeds(settings):
    import os

    if os.environ.get("RUN_LIVE_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_TESTS=1 to hit the real RBI and UN News feeds")
    from adapters.http import SafeFetcher

    with SafeFetcher(
        user_agent=settings.ingestion_user_agent, allowed_hosts={"www.rbi.org.in", "news.un.org"}
    ) as f:
        for url in (
            "https://www.rbi.org.in/pressreleases_rss.xml",
            "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
        ):
            assert parse_feed(f.get(url).content, default_publisher="live")
