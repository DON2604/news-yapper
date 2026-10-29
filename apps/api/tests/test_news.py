from __future__ import annotations


def test_today_edition_serves_demo_content(client, seeded):
    body = client.get("/api/v1/editions/today").json()
    assert body["is_demo"] is True
    assert len(body["items"]) == seeded["demo_articles"]
    first = body["items"][0]
    assert first["ai_status"] == "ready"
    assert first["is_demo"] is True
    assert first["primary_source"]["url"].startswith("https://")
    assert "not today's news" in body["title"]


def test_news_filters_and_pagination(client, seeded):
    page = client.get("/api/v1/news", params={"limit": 5}).json()
    assert len(page["items"]) == 5 and page["next_cursor"]
    second = client.get("/api/v1/news", params={"limit": 5, "cursor": page["next_cursor"]}).json()
    assert {i["slug"] for i in page["items"]}.isdisjoint({i["slug"] for i in second["items"]})
    science = client.get("/api/v1/news", params={"category": "science"}).json()
    assert science["items"] and all(i["category"] == "science" for i in science["items"])
    banking = client.get("/api/v1/news", params={"exam": "BANKING"}).json()
    assert banking["items"] and all("BANKING" in i["exam_tags"] for i in banking["items"])
    search = client.get("/api/v1/news", params={"q": "Chandrayaan"}).json()
    assert any("chandrayaan" in i["slug"] for i in search["items"])


def test_article_detail_has_facts_sources_and_practice(client, seeded):
    detail = client.get("/api/v1/news/demo-chandrayaan-3-south-pole-landing").json()
    assert detail["ai_status"] == "ready"
    assert len(detail["key_facts"]) >= 3
    source_ids = {s["id"] for s in detail["sources"]}
    assert all(set(f["source_item_ids"]) <= source_ids for f in detail["key_facts"])
    assert detail["practice_question_count"] == 2
    assert detail["verification"]["method"] == "demo_manual"
    assert client.get("/api/v1/news/does-not-exist").status_code == 404


def test_unpublished_ai_drafts_are_never_exposed(client, make_event):
    draft = make_event(title="Source headline only", status="needs_review")
    pending = make_event(title="Fresh discovery", status="discovered")
    rejected = make_event(title="Rejected story", status="rejected")
    detail = client.get(f"/api/v1/news/{draft.slug}").json()
    assert detail["ai_status"] == "in_review"
    assert detail["headline"] == "Source headline only"
    assert detail["neutral_summary"] is None and detail["key_facts"] == []
    listing = client.get("/api/v1/news", params={"demo": "false"}).json()
    slugs = {i["slug"]: i for i in listing["items"]}
    assert slugs[pending.slug]["ai_status"] == "pending"
    assert rejected.slug not in slugs
    assert client.get(f"/api/v1/news/{rejected.slug}").status_code == 404
