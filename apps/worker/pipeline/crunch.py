"""Crunch It (worker side).

Two engines produce the same output shape:
  * "ai"      - provider call through the AIOrchestrator (consent-gated)
  * "offline" - deterministic extraction on our own server; no provider ever sees the notes
Every bullet/card keeps refs (N1/S2/M3) back to the user's items; notes stay "unverified".
"""

from __future__ import annotations

import re
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_config import load_routing
from app.config import Settings
from app.errors import NotFoundError
from app.models import AIJob, CrunchJob, CrunchOutput, Flashcard, UserPreferences, utcnow
from app.services.crunch import PROMPT_VERSION, CrunchItem, load_owned_inputs
from pipeline.ai_types import Prepared, ResourceGone
from pipeline.normalize import title_tokens
from pipeline.prompts import CRUNCH_SYSTEM, crunch_user_prompt, estimate_tokens
from pipeline.providers.base import GenerationResult
from pipeline.validate import CrunchOut, validate_crunch

_FACT_LINE = re.compile(r"^\s*[-•*]\s*(.+)$")
_TERM_DEF = re.compile(r"^\s*([^:\n]{2,60}?)\s*(?::| - | – | — )\s*(.{3,240})$")
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_CLOZE = re.compile(
    rf"(\b\d{{1,2}}\s+(?:{_MONTHS})\s+\d{{4}}\b|\b(?:1[5-9]|20)\d{{2}}\b|\b\d+(?:\.\d+)?\s?(?:%|m\b|km\b|crore\b|lakh\b|million\b|billion\b))"
)


@dataclass
class CrunchDraft:
    title: str
    bullets: list[dict[str, Any]]
    sections: list[dict[str, Any]]
    mnemonics: list[str]
    traps: list[dict[str, Any]]
    flashcards: list[dict[str, Any]]
    source_refs: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)


def _ref_table(items: list[CrunchItem]) -> list[dict[str, Any]]:
    return [
        {
            "ref": i.ref,
            "type": i.type,
            "id": str(i.id),
            "title": i.title[:140],
            "url": i.url,
            "verified": i.verified,
        }
        for i in items
    ]


def _similar(a: str, b: str) -> bool:
    ta, tb = title_tokens(a), title_tokens(b)
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= 0.75


def _mistake_parts(item: CrunchItem) -> tuple[str, str, str]:
    fields = dict.fromkeys(("Correct answer", "I picked", "Why"), "")
    for line in item.text.splitlines():
        key, _, value = line.partition(":")
        if key.strip() in fields:
            fields[key.strip()] = value.strip()
    return fields["Correct answer"], fields["I picked"], fields["Why"]


def _sentences(text: str) -> list[str]:
    body = "\n".join(line for line in text.splitlines() if not line.startswith("Tags:"))
    parts = re.split(r"(?<=[.!?])\s+|\n+", body)
    return [p.strip(" -•*\t") for p in parts if len(p.split()) >= 3]


def _cloze(fact: str) -> tuple[str, str] | None:
    match = _CLOZE.search(fact)
    if not match:
        return None
    answer = match.group(1).strip()
    return fact[: match.start()] + "_____" + fact[match.end() :], answer


_HOOK_STOP = {"the", "this", "trap", "fill", "what", "which", "who", "when", "where", "how"}


def _hook_word(text: str, exclude: set[str]) -> str | None:
    """First distinctive capitalised word (e.g. 'GST', 'Pragyan') not already used in the hook."""
    for word in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", text):
        if word[0].isupper() and word.lower() not in _HOOK_STOP | exclude:
            return word
    for word in re.findall(r"[A-Za-z]{4,}", text):
        if word.lower() not in _HOOK_STOP | exclude:
            return word.capitalize()
    return None


def offline_crunch(items: list[CrunchItem], settings: dict[str, Any]) -> CrunchDraft:
    banglish = settings.get("language", "banglish") == "banglish"
    limit = 8 if settings.get("length", "short") == "short" else 20
    want_cards = int(settings.get("flashcards", 8))
    candidates: list[tuple[int, dict[str, Any]]] = []
    traps: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []

    for item in items:
        topic = item.topic or "general"
        if item.type == "mistake":
            correct, picked, why = _mistake_parts(item)
            candidates.append(
                (
                    0,
                    {
                        "text": f"{item.title} → {correct}",
                        "source_refs": [item.ref],
                        "verified": True,
                        "topic": topic,
                    },
                )
            )
            if settings.get("include_traps", True) and correct:
                trap = (
                    f"Trap: '{picked}' noy - shothik uttor '{correct}'. {why}"
                    if banglish
                    else f"Trap: not '{picked}' - the answer is '{correct}'. {why}"
                )
                traps.append({"text": trap.strip()[:320], "source_refs": [item.ref]})
            cards.append(
                {
                    "front": item.title[:320],
                    "back": f"{correct} - {why}".strip(" -")[:480],
                    "source_refs": [item.ref],
                    "exam_topic": topic,
                }
            )
        elif item.type == "snapshot":
            facts = [m.group(1).strip() for line in item.text.splitlines() if (m := _FACT_LINE.match(line))]
            for fact in facts:
                candidates.append(
                    (
                        1,
                        {
                            "text": fact[:320],
                            "source_refs": [item.ref],
                            "verified": item.verified,
                            "topic": topic,
                        },
                    )
                )
                cloze = _cloze(fact)
                if cloze:
                    cards.append(
                        {
                            "front": f"Fill in: {cloze[0]}"[:320],
                            "back": cloze[1],
                            "source_refs": [item.ref],
                            "exam_topic": topic,
                        }
                    )
            if not facts:
                for sentence in _sentences(item.text)[:2]:
                    candidates.append(
                        (
                            2,
                            {
                                "text": sentence[:320],
                                "source_refs": [item.ref],
                                "verified": item.verified,
                                "topic": topic,
                            },
                        )
                    )
        else:
            for line in item.text.splitlines():
                match = _TERM_DEF.match(line)
                if match and not line.startswith("Tags:"):
                    cards.append(
                        {
                            "front": match.group(1).strip()[:320],
                            "back": match.group(2).strip()[:480],
                            "source_refs": [item.ref],
                            "exam_topic": topic,
                        }
                    )
            for sentence in _sentences(item.text) or [item.title]:
                candidates.append(
                    (
                        3,
                        {
                            "text": sentence[:320],
                            "source_refs": [item.ref],
                            "verified": False,
                            "topic": topic,
                        },
                    )
                )

    bullets: list[dict[str, Any]] = []
    for _, bullet in sorted(candidates, key=lambda c: c[0]):
        if any(_similar(bullet["text"], b["text"]) for b in bullets):
            continue
        bullets.append(bullet)
        if len(bullets) >= limit:
            break

    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for bullet in bullets:
        grouped.setdefault(bullet["topic"], []).append(bullet)
    sections = [
        {"topic": topic, "bullets": [{k: b[k] for k in ("text", "source_refs", "verified")} for b in group]}
        for topic, group in grouped.items()
    ]

    mnemonics: list[str] = []
    for topic, group in grouped.items():
        words: list[str] = []
        for bullet in group:
            word = _hook_word(bullet["text"], exclude={w.lower() for w in words})
            if word:
                words.append(word)
            if len(words) == 5:
                break
        if len(words) >= 3:
            mnemonics.append(f"{topic.title()}: {'-'.join(w[0].upper() for w in words)} ({', '.join(words)})")

    unique_cards: list[dict[str, Any]] = []
    for card in cards:
        if card["back"] and all(card["front"] != c["front"] for c in unique_cards):
            unique_cards.append(card)
    unique_cards = unique_cards[:want_cards]

    warnings = [
        "Offline engine: deterministic extraction on our server - no AI provider received your notes."
    ]
    if any(i.type == "note" for i in items):
        warnings.append("Sticky-note points are your own text (user-provided, unverified).")
    if len(unique_cards) < want_cards:
        warnings.append(f"Only {len(unique_cards)} flashcard(s) could be extracted from this material.")
    title = (
        f"{len(items)}-ta item theke {len(bullets)}-ta revision point ready"
        if banglish
        else f"{len(bullets)} revision points from {len(items)} items"
    )
    return CrunchDraft(
        title=title,
        bullets=[{k: b[k] for k in ("text", "source_refs", "verified")} for b in bullets],
        sections=sections,
        mnemonics=mnemonics,
        traps=traps[:10],
        flashcards=unique_cards,
        source_refs=_ref_table(items),
        warnings=warnings,
    )


def draft_from_ai(out: CrunchOut, items: list[CrunchItem], warnings: list[str]) -> CrunchDraft:
    verified = {i.ref: i.verified for i in items}

    def bullet(b: Any) -> dict[str, Any]:
        return {
            "text": b.text,
            "source_refs": b.source_refs,
            "verified": all(verified.get(r, False) for r in b.source_refs),
        }

    extra = []
    if any(i.type == "note" for i in items):
        extra.append("Points citing sticky notes (N refs) come from your own unverified notes.")
    return CrunchDraft(
        title=out.title,
        bullets=[bullet(b) for b in out.concise_bullets],
        sections=[{"topic": s.topic, "bullets": [bullet(b) for b in s.bullets]} for s in out.topic_sections],
        mnemonics=out.mnemonics,
        traps=[{"text": t.text, "source_refs": t.source_refs} for t in out.exam_traps],
        flashcards=[
            {"front": c.front, "back": c.back, "source_refs": c.source_refs, "exam_topic": c.exam_topic}
            for c in out.flashcards
        ],
        source_refs=_ref_table(items),
        warnings=warnings + extra,
    )


def persist_draft(
    db: Session, job: CrunchJob, draft: CrunchDraft, engine: str, model: str | None
) -> uuid.UUID:
    now = utcnow()
    refs = {r["ref"]: r for r in draft.source_refs}
    output = CrunchOutput(
        user_id=job.user_id,
        input_digest=job.input_digest,
        title=draft.title[:200],
        concise_bullets=draft.bullets,
        topic_sections=draft.sections,
        mnemonics=draft.mnemonics,
        exam_traps=draft.traps,
        source_refs=draft.source_refs,
        warnings=draft.warnings,
        engine=engine,
        model=model,
        prompt_version=PROMPT_VERSION,
    )
    db.add(output)
    db.flush()
    for card in draft.flashcards:
        db.add(
            Flashcard(
                user_id=job.user_id,
                crunch_output_id=output.id,
                source_ref={
                    "refs": card["source_refs"],
                    "items": [refs[r] for r in card["source_refs"] if r in refs],
                },
                front=card["front"],
                back=card["back"],
                exam_topic=card.get("exam_topic"),
                due_at=now,
            )
        )
    job.status = "completed"
    job.output_id = output.id
    job.completed_at = now
    job.error_code = None
    job.status_message = (
        f"Crunch it ✨ - {len(draft.source_refs)} items theke {len(draft.bullets)}-ta revision points ready."
    )
    db.commit()
    return output.id


def _uuids(values: list[Any]) -> list[uuid.UUID]:
    return [uuid.UUID(str(v)) for v in values or []]


class CrunchHandler:
    kind = "crunch"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.route = load_routing(settings)["crunch"]

    def _crunch_job(self, db: Session, job: AIJob) -> CrunchJob:
        crunch_job = db.get(CrunchJob, uuid.UUID(str(job.payload.get("crunch_job_id"))))
        if crunch_job is None:
            raise ResourceGone("Crunch job no longer exists")
        return crunch_job

    def prepare(self, db: Session, job: AIJob) -> Prepared:
        crunch_job = self._crunch_job(db, job)
        try:
            items = load_owned_inputs(
                db,
                crunch_job.user_id,
                _uuids(crunch_job.selected_note_ids),
                _uuids(crunch_job.selected_snapshot_ids),
                _uuids(crunch_job.selected_mistake_ids),
            )
        except NotFoundError as exc:
            raise ResourceGone("Some selected items were deleted - start a new Crunch.") from exc
        crunch_job.status = "running"
        crunch_job.started_at = crunch_job.started_at or utcnow()
        crunch_job.status_message = "Crunching your notes..."
        consent = db.scalar(
            select(UserPreferences.crunch_ai_consent).where(UserPreferences.user_id == crunch_job.user_id)
        )
        db.commit()
        context: dict[str, Any] = {
            "crunch_job_id": crunch_job.id,
            "items": items,
            "settings": dict(crunch_job.settings or {}),
            # Consent is re-read at processing time so a withdrawal after queueing is honoured.
            "consent": consent or "none",
        }
        if crunch_job.engine == "offline":
            return Prepared(offline=True, context=context)
        user = crunch_user_prompt(items, context["settings"])
        if estimate_tokens(user) > self.route.max_input_tokens:
            raise ResourceGone(
                "Selection is too large for the AI input budget - select fewer items or use offline mode."
            )
        return Prepared(
            system=CRUNCH_SYSTEM,
            user=user,
            schema=CrunchOut.model_json_schema(),
            schema_name="crunch_output",
            estimated_tokens=estimate_tokens(CRUNCH_SYSTEM, user) + self.route.max_output_tokens,
            max_output_tokens=self.route.max_output_tokens,
            context=context,
        )

    def run_offline(self, db: Session, job: AIJob, prepared: Prepared) -> str:
        crunch_job = self._crunch_job(db, job)
        draft = offline_crunch(prepared.context["items"], prepared.context["settings"])
        return f"crunch_output:{persist_draft(db, crunch_job, draft, 'offline', None)}"

    def accept(
        self, db: Session, job: AIJob, prepared: Prepared, result: GenerationResult, provider: str, model: str
    ) -> str:
        items: list[CrunchItem] = prepared.context["items"]
        validated = validate_crunch(
            result.data, {i.ref for i in items}, int(prepared.context["settings"].get("flashcards", 8))
        )
        crunch_job = self._crunch_job(db, job)
        draft = draft_from_ai(validated.output, items, validated.warnings)
        return f"crunch_output:{persist_draft(db, crunch_job, draft, 'ai', f'{provider}:{model}')}"

    def on_deferred(self, db: Session, job: AIJob, message: str) -> None:
        crunch_job = db.get(CrunchJob, uuid.UUID(str(job.payload.get("crunch_job_id"))))
        if crunch_job is not None and crunch_job.status != "completed":
            crunch_job.status = "deferred"
            crunch_job.status_message = message[:500]
            db.commit()

    def on_failed(self, db: Session, job: AIJob, code: str, message: str) -> None:
        crunch_job = db.get(CrunchJob, uuid.UUID(str(job.payload.get("crunch_job_id"))))
        if crunch_job is not None and crunch_job.status != "completed":
            crunch_job.status = "failed"
            crunch_job.error_code = code[:64]
            crunch_job.status_message = message[:500]
            db.commit()
