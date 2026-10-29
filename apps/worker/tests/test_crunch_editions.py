from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import DailyEdition, EditionEvent
from app.services.crunch import CrunchItem, manifest_digest
from pipeline.crunch import offline_crunch
from pipeline.editions import build_edition
from pipeline.validate import (
    EventEvidence,
    OutputRejected,
    numbers_in,
    overlap_ratio,
    validate_crunch,
    validate_news_batch,
)


def _item(
    ref: str, type_: str, title: str, text: str, *, verified: bool, topic: str | None = None
) -> CrunchItem:
    return CrunchItem(
        ref=ref, type=type_, id=uuid.uuid4(), version="1", title=title, text=text,
        verified=verified, topic=topic, url="https://example.org" if type_ != "note" else None,
    )  # fmt: skip


ITEMS = [
    _item("M1", "mistake", "Who chairs the GST Council?",
          "Correct answer: Union Finance Minister\nI picked: Prime Minister\nWhy: Article 279A council.", verified=True, topic="economy"),
    _item("S1", "snapshot", "Chandrayaan-3 lands",
          "Bhai, chand-e landing!\n- Chandrayaan-3 soft-landed near the lunar south pole on 23 August 2023.\n- The rover is named Pragyan.",
          verified=True, topic="science"),
    _item("N1", "note", "Monetary policy",
          "Repo rate: rate at which RBI lends to banks\nCRR - share of deposits banks keep with RBI\nMPC has six members.",
          verified=False, topic="economy"),
]  # fmt: skip


def test_offline_crunch_is_traceable_and_labelled():
    draft = offline_crunch(
        ITEMS, {"length": "short", "language": "banglish", "flashcards": 6, "include_traps": True}
    )
    refs = {r["ref"] for r in draft.source_refs}
    assert refs == {"M1", "S1", "N1"}
    assert draft.bullets[0]["source_refs"] == ["M1"], "mistakes come first"
    assert all(set(b["source_refs"]) <= refs for b in draft.bullets)
    note_bullets = [b for b in draft.bullets if b["source_refs"] == ["N1"]]
    assert note_bullets and all(b["verified"] is False for b in note_bullets)
    assert draft.traps and "Union Finance Minister" in draft.traps[0]["text"]
    fronts = {c["front"]: c["back"] for c in draft.flashcards}
    assert fronts["Repo rate"] == "rate at which RBI lends to banks"
    assert any(c["back"] == "23 August 2023" and "_____" in c["front"] for c in draft.flashcards)
    assert "revision point" in draft.title
    assert any("no AI provider" in w for w in draft.warnings)
    for hook in draft.mnemonics:
        words = hook.split("(")[1].rstrip(")").split(", ")
        assert len(words) == len({w.lower() for w in words}) >= 3, hook


def test_offline_crunch_respects_length_and_card_count():
    many = [
        _item(
            f"N{i}", "note", f"Note {i}", f"Scheme{i} launched by ministry{i} for sector{i}.", verified=False
        )
        for i in range(30)
    ]
    short = offline_crunch(many, {"length": "short", "flashcards": 5})
    detailed = offline_crunch(many, {"length": "detailed", "flashcards": 5})
    assert len(short.bullets) == 8 and len(detailed.bullets) == 20
    assert len(short.flashcards) <= 5


def test_manifest_digest_is_order_independent_and_version_sensitive():
    a = manifest_digest(ITEMS, {"length": "short"}, "offline")[1]
    b = manifest_digest(list(reversed(ITEMS)), {"length": "short"}, "offline")[1]
    assert a == b
    changed = [*ITEMS[:2], _item("N1", "note", "Monetary policy", "edited", verified=False)]
    changed[2].id = ITEMS[2].id
    changed[2].version = "2"
    assert manifest_digest(changed, {"length": "short"}, "offline")[1] != a
    assert manifest_digest(ITEMS, {"length": "detailed"}, "offline")[1] != a
    assert manifest_digest(ITEMS, {"length": "short"}, "ai")[1] != a


def test_evidence_helpers():
    assert numbers_in("Outlay of Rs 1,500 crore in 2026; 4th country; 7.5%") == {"1500", "2026", "7.5"}
    assert overlap_ratio("Cabinet approved the mission", "The Union Cabinet approved a new mission") == 1.0
    assert overlap_ratio("Aliens landed in Kolkata", "The Union Cabinet approved a new mission") == 0.0


def test_news_validation_rejects_wrong_events_and_flags_sensitive_tone():
    evidence = {
        "e1": EventEvidence("e1", sensitive=True, item_texts={"s1": "Flood toll rises to 12 in district after heavy rain."}, item_urls={"s1": "u"})
    }  # fmt: skip
    base = {
        "event_id": "e1",
        "headline_banglish": "Bonnya-y 12 jon mara gelo 😂",
        "neutral_summary": "A flood in the district has killed 12 people after heavy rain, officials said.",
        "banglish_summary": "Bhai lol, bonnya-y onek khoti.",
        "category": "environment",
        "key_facts": [
            {"claim": "The flood toll rose to 12 after heavy rain.", "source_item_ids": ["s1"]},
            {"claim": "Heavy rain caused the flood in the district.", "source_item_ids": ["s1"]},
        ],
        "why_it_matters": "Disaster management questions.",
        "exam_tags": ["UPSC"],
        "importance_score": 40,
        "quiz": [],
        "uncertainties": [],
        "sensitive_story": True,
    }
    [result] = validate_news_batch({"articles": [base]}, evidence, date(2026, 1, 1))
    assert not result.publishable
    assert (
        "sensitive_story_needs_editor" in result.flags and "tone_violation_on_sensitive_story" in result.flags
    )
    with pytest.raises(OutputRejected):
        validate_news_batch({"articles": [{**base, "event_id": "other"}]}, evidence, date(2026, 1, 1))
    with pytest.raises(OutputRejected):
        validate_news_batch({"articles": [{**base, "category": "gossip"}]}, evidence, date(2026, 1, 1))


def test_crunch_validation_drops_unknown_refs_or_rejects():
    good = {"text": "Repo is RBI's lending rate", "source_refs": ["N1"]}
    unknown = {"text": "Invented point", "source_refs": ["Q7"]}
    out = validate_crunch({"title": "Revision", "concise_bullets": [good, good, good, unknown]}, {"N1"}, 5)
    assert len(out.output.concise_bullets) == 3 and out.warnings
    with pytest.raises(OutputRejected):
        validate_crunch({"title": "Revision", "concise_bullets": [unknown]}, {"N1"}, 5)


def test_edition_prefers_published_then_source_only(make_event, settings):
    published = make_event(title="Published story about a scheme launch", status="published", relevance=50)
    pending = make_event(title="Pending story about a bill", status="discovered", relevance=80)
    low = make_event(title="Low relevance gossip", status="discovered", relevance=5)
    with SessionLocal() as db:
        edition = build_edition(db, settings)
        assert edition is not None
        ranked = [
            ee.event_id
            for ee in db.scalars(
                select(EditionEvent)
                .where(EditionEvent.edition_id == edition.id)
                .order_by(EditionEvent.ranking)
            )
        ]
    assert ranked[:2] == [published.id, pending.id]
    assert low.id not in ranked


def test_edition_falls_back_to_demo_when_feeds_are_quiet(seeded, settings):
    with SessionLocal() as db:
        edition = build_edition(db, settings)
        assert edition is not None and edition.is_demo
        count = len(db.scalars(select(EditionEvent).where(EditionEvent.edition_id == edition.id)).all())
        assert count == seeded["demo_articles"]
        assert db.scalar(select(DailyEdition.title).where(DailyEdition.id == edition.id)).startswith("DEMO")
