"""Crunch It (API side): resolve owned inputs -> canonical manifest -> SHA-256 digest ->
cache hit or enqueue one idempotent job. The worker does the actual crunching.

Shared helpers here (load_owned_inputs, CrunchItem) are also used by the worker so the
digest, budget and prompt all see exactly the same item text.
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai_config import crunch_disclosure
from app.config import get_settings
from app.errors import ForbiddenError, InvalidInputError, NotFoundError
from app.models import (
    AIJob,
    ArticleSnapshot,
    CollectionItem,
    CrunchJob,
    CrunchOutput,
    Flashcard,
    MistakeVaultEntry,
    Note,
    StudyCollection,
    User,
    UserPreferences,
    utcnow,
)
from app.schemas.study import (
    CrunchIn,
    CrunchJobOut,
    CrunchOutputOut,
    CrunchPreviewItem,
    CrunchPreviewOut,
)
from app.services import audit
from app.services.revision import flashcard_out

PROMPT_VERSION = "crunch-v1"
PROMPT_OVERHEAD_TOKENS = 700
CRUNCH_PRIORITY = 100


class CrunchLimitError(Exception):
    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class CrunchItem:
    ref: str
    type: str
    id: uuid.UUID
    version: str
    title: str
    text: str
    verified: bool
    topic: str | None
    url: str | None

    @property
    def chars(self) -> int:
        return len(self.title) + len(self.text)

    def manifest_entry(self) -> dict[str, str]:
        return {"t": self.type, "id": str(self.id), "v": self.version}


def _note_item(n: Note, i: int) -> CrunchItem:
    tags = f"\nTags: {', '.join(n.tags)}" if n.tags else ""
    return CrunchItem(
        ref=f"N{i}",
        type="note",
        id=n.id,
        version=str(n.revision_version),
        title=n.title or "Untitled sticky",
        text=f"{n.body}{tags}",
        verified=False,
        topic=n.exam_topic or (n.tags[0] if n.tags else None),
        url=None,
    )


def _snapshot_item(s: ArticleSnapshot, i: int) -> CrunchItem:
    facts = "\n".join(f"- {f.get('claim', '')}" for f in s.saved_key_facts or [])
    body = "\n".join(p for p in (s.saved_banglish_summary, facts) if p)
    return CrunchItem(
        ref=f"S{i}",
        type="snapshot",
        id=s.id,
        version=s.saved_at.isoformat(),
        title=s.saved_title,
        text=body,
        verified=s.verified,
        topic=s.category,
        url=s.source_url,
    )


def _mistake_item(m: MistakeVaultEntry, i: int) -> CrunchItem:
    options = [str(o) for o in m.options_snapshot]
    correct = options[m.correct_choice] if 0 <= m.correct_choice < len(options) else ""
    wrong = options[m.incorrect_choice] if 0 <= m.incorrect_choice < len(options) else ""
    text = f"Correct answer: {correct}\nI picked: {wrong}\nWhy: {m.explanation_snapshot}"
    return CrunchItem(
        ref=f"M{i}",
        type="mistake",
        id=m.id,
        version=str(m.revision_version),
        title=m.prompt_snapshot,
        text=text,
        verified=True,
        topic=m.topic,
        url=(m.evidence_urls or [None])[0],
    )


def load_owned_inputs(
    db: Session,
    user_id: uuid.UUID,
    note_ids: list[uuid.UUID],
    snapshot_ids: list[uuid.UUID],
    mistake_ids: list[uuid.UUID],
) -> list[CrunchItem]:
    """Load only rows owned by user_id. Missing/foreign IDs raise LookupError (no existence leak)."""
    note_ids, snapshot_ids, mistake_ids = (
        sorted(set(x), key=str) for x in (note_ids, snapshot_ids, mistake_ids)
    )
    notes = (
        db.scalars(
            select(Note).where(Note.id.in_(note_ids), Note.user_id == user_id, Note.deleted_at.is_(None))
        ).all()
        if note_ids
        else []
    )
    snaps = (
        db.scalars(
            select(ArticleSnapshot).where(
                ArticleSnapshot.id.in_(snapshot_ids), ArticleSnapshot.user_id == user_id
            )
        ).all()
        if snapshot_ids
        else []
    )
    mistakes = (
        db.scalars(
            select(MistakeVaultEntry).where(
                MistakeVaultEntry.id.in_(mistake_ids), MistakeVaultEntry.user_id == user_id
            )
        ).all()
        if mistake_ids
        else []
    )
    if len(notes) != len(note_ids) or len(snaps) != len(snapshot_ids) or len(mistakes) != len(mistake_ids):
        raise NotFoundError("One or more selected items were not found")

    by_id_n = {n.id: n for n in notes}
    by_id_s = {s.id: s for s in snaps}
    by_id_m = {m.id: m for m in mistakes}
    items: list[CrunchItem] = []
    items += [_note_item(by_id_n[i], k + 1) for k, i in enumerate(note_ids)]
    items += [_snapshot_item(by_id_s[i], k + 1) for k, i in enumerate(snapshot_ids)]
    items += [_mistake_item(by_id_m[i], k + 1) for k, i in enumerate(mistake_ids)]
    return items


def _expand_selection(db: Session, user: User, payload: CrunchIn) -> tuple[list[uuid.UUID], ...]:
    note_ids = list(payload.note_ids)
    snapshot_ids = list(payload.snapshot_ids)
    mistake_ids = list(payload.mistake_ids)
    if payload.collection_id is not None:
        col = db.scalar(
            select(StudyCollection).where(
                StudyCollection.id == payload.collection_id, StudyCollection.user_id == user.id
            )
        )
        if col is None:
            raise NotFoundError("Collection not found")
        for item in db.scalars(select(CollectionItem).where(CollectionItem.collection_id == col.id)).all():
            if item.item_type == "note":
                note_ids.append(item.item_id)
            elif item.item_type == "snapshot":
                snapshot_ids.append(item.item_id)
            elif item.item_type == "mistake":
                mistake_ids.append(item.item_id)
    if payload.last_week:
        since = utcnow() - timedelta(days=7)
        note_ids += db.scalars(
            select(Note.id).where(
                Note.user_id == user.id, Note.deleted_at.is_(None), Note.updated_at >= since
            )
        ).all()
        snapshot_ids += db.scalars(
            select(ArticleSnapshot.id).where(
                ArticleSnapshot.user_id == user.id, ArticleSnapshot.saved_at >= since
            )
        ).all()
        mistake_ids += db.scalars(
            select(MistakeVaultEntry.id).where(
                MistakeVaultEntry.user_id == user.id, MistakeVaultEntry.last_wrong_at >= since
            )
        ).all()
    return list(set(note_ids)), list(set(snapshot_ids)), list(set(mistake_ids))


def manifest_digest(
    items: list[CrunchItem], settings: dict[str, Any], engine: str
) -> tuple[dict[str, Any], str]:
    manifest = {
        "prompt_version": PROMPT_VERSION,
        "engine": engine,
        "settings": settings,
        "items": sorted((i.manifest_entry() for i in items), key=lambda e: (e["t"], e["id"])),
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return manifest, hashlib.sha256(canonical.encode()).hexdigest()


def _resolve_engine(requested: str, disclosure: dict[str, Any]) -> str:
    if requested == "offline":
        return "offline"
    if requested == "ai":
        if disclosure["consent"] == "none":
            raise ForbiddenError("AI Crunch needs your consent first (Settings -> Privacy).")
        return "ai"
    return "ai" if disclosure["ai_available"] and disclosure["consent"] != "none" else "offline"


def job_out(db: Session, job: CrunchJob, cached: bool = False) -> CrunchJobOut:
    count = (
        len(job.selected_note_ids or [])
        + len(job.selected_snapshot_ids or [])
        + len(job.selected_mistake_ids or [])
    )
    return CrunchJobOut(
        id=job.id,
        status=job.status,
        engine=job.engine,
        status_message=job.status_message,
        output_id=job.output_id,
        requested_at=job.requested_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_code=job.error_code,
        item_count=count,
        cached=cached,
    )


def preview(
    db: Session, user: User, prefs: UserPreferences, payload: CrunchIn
) -> tuple[CrunchPreviewOut, list[CrunchItem]]:
    settings = get_settings()
    note_ids, snapshot_ids, mistake_ids = _expand_selection(db, user, payload)
    items = load_owned_inputs(db, user.id, note_ids, snapshot_ids, mistake_ids)
    disclosure = crunch_disclosure(settings, prefs.crunch_ai_consent)
    engine = _resolve_engine(payload.engine, disclosure)
    manifest, digest = manifest_digest(items, payload.settings.model_dump(), engine)
    total_chars = sum(i.chars for i in items)
    warnings: list[str] = []
    if any(i.type == "note" for i in items):
        warnings.append("Sticky notes are your own text: Crunch labels them user-provided/unverified.")
    if engine == "ai" and not disclosure["ai_available"]:
        warnings.append("No AI provider is configured right now - the job will wait in the queue.")
    if engine == "offline":
        warnings.append(
            "Offline engine: deterministic extraction on this server, no AI provider receives your notes."
        )
    within = 0 < len(items) <= settings.crunch_max_items and total_chars <= settings.crunch_max_input_chars
    existing = db.scalar(
        select(CrunchJob).where(CrunchJob.user_id == user.id, CrunchJob.input_digest == digest)
    )
    return (
        CrunchPreviewOut(
            items=[
                CrunchPreviewItem.model_validate(
                    {
                        "type": i.type,
                        "id": i.id,
                        "title": i.title[:140],
                        "chars": i.chars,
                        "verified": i.verified,
                    }
                )
                for i in items
            ],
            total_chars=total_chars,
            token_estimate=math.ceil(total_chars / 4) + PROMPT_OVERHEAD_TOKENS,
            max_chars=settings.crunch_max_input_chars,
            max_items=settings.crunch_max_items,
            within_budget=within,
            digest=digest,
            engine_resolved=engine,
            existing_job=job_out(db, existing, cached=existing.status == "completed") if existing else None,
            disclosure=disclosure,
            warnings=warnings,
        ),
        items,
    )


def request_crunch(
    db: Session, user: User, prefs: UserPreferences, payload: CrunchIn
) -> tuple[CrunchJob, bool]:
    """Returns (job, cached). Idempotent on (user, input digest)."""
    settings = get_settings()
    pv, items = preview(db, user, prefs, payload)
    if not items:
        raise InvalidInputError("Select at least one note, snapshot or mistake")
    if not pv.within_budget:
        raise CrunchLimitError(
            f"Too much input ({len(items)} items, {pv.total_chars} chars). "
            f"Limit: {settings.crunch_max_items} items / {settings.crunch_max_input_chars} chars - select fewer."
        )

    existing = db.scalar(
        select(CrunchJob)
        .where(CrunchJob.user_id == user.id, CrunchJob.input_digest == pv.digest)
        .with_for_update()
    )
    if existing is not None:
        if existing.status == "completed" and existing.output_id:
            return existing, True
        if existing.status == "failed":
            existing.status = "queued"
            existing.error_code = None
            existing.status_message = "Re-queued after a previous failure"
            ai_job = db.get(AIJob, existing.ai_job_id) if existing.ai_job_id else None
            if ai_job is not None:
                ai_job.status = "queued"
                ai_job.attempts = 0
                ai_job.next_run_at = utcnow()
                ai_job.error_code = None
            db.commit()
        return existing, False

    now = utcnow()
    recent = db.scalars(
        select(CrunchJob.requested_at)
        .where(CrunchJob.user_id == user.id, CrunchJob.requested_at >= now - timedelta(days=1))
        .order_by(CrunchJob.requested_at.desc())
    ).all()
    if len(recent) >= settings.crunch_daily_limit_per_user:
        raise CrunchLimitError("Daily Crunch limit reached - kal abar try kor!", retry_after=3600)
    if recent and (now - recent[0]).total_seconds() < settings.crunch_cooldown_seconds:
        wait = settings.crunch_cooldown_seconds - int((now - recent[0]).total_seconds())
        raise CrunchLimitError("Ektu wait kor - Crunch cooldown.", retry_after=max(1, wait))

    manifest, digest = manifest_digest(items, payload.settings.model_dump(), pv.engine_resolved)
    job = CrunchJob(
        user_id=user.id,
        input_manifest=manifest,
        input_digest=digest,
        selected_note_ids=[str(i.id) for i in items if i.type == "note"],
        selected_snapshot_ids=[str(i.id) for i in items if i.type == "snapshot"],
        selected_mistake_ids=[str(i.id) for i in items if i.type == "mistake"],
        settings=payload.settings.model_dump(),
        engine=pv.engine_resolved,
        status="queued",
        status_message="Queued - waiting for the worker",
        priority=CRUNCH_PRIORITY,
        requested_at=now,
    )
    db.add(job)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        concurrent = db.scalar(
            select(CrunchJob).where(CrunchJob.user_id == user.id, CrunchJob.input_digest == digest)
        )
        if concurrent is None:
            raise
        return concurrent, concurrent.status == "completed"
    ai_job = AIJob(
        kind="crunch",
        resource_type="crunch_job",
        resource_id=job.id,
        payload={"crunch_job_id": str(job.id), "engine": job.engine, "consent": prefs.crunch_ai_consent},
        dedupe_key=f"crunch:{job.id}",
        priority=CRUNCH_PRIORITY,
        status="queued",
        max_attempts=settings.ai_max_job_attempts,
        token_estimate=pv.token_estimate,
        input_digest=digest,
        contains_private_data=True,
        next_run_at=now,
    )
    db.add(ai_job)
    db.flush()
    job.ai_job_id = ai_job.id
    audit.record(
        db,
        "crunch.requested",
        "crunch_job",
        job.id,
        actor_user_id=user.id,
        items=len(items),
        engine=job.engine,
    )
    db.commit()
    db.refresh(job)
    return job, False


def get_owned_job(db: Session, user: User, job_id: uuid.UUID) -> CrunchJob | None:
    return db.scalar(select(CrunchJob).where(CrunchJob.id == job_id, CrunchJob.user_id == user.id))


def output_out(db: Session, out: CrunchOutput) -> CrunchOutputOut:
    cards = db.scalars(
        select(Flashcard).where(Flashcard.crunch_output_id == out.id).order_by(Flashcard.created_at)
    ).all()
    return CrunchOutputOut(
        id=out.id,
        title=out.title,
        concise_bullets=list(out.concise_bullets or []),
        topic_sections=list(out.topic_sections or []),
        mnemonics=[str(m) for m in out.mnemonics or []],
        exam_traps=list(out.exam_traps or []),
        source_refs=list(out.source_refs or []),
        warnings=[str(w) for w in out.warnings or []],
        engine=out.engine,
        model=out.model,
        prompt_version=out.prompt_version,
        created_at=out.created_at,
        flashcards=[flashcard_out(c) for c in cards],
    )


def get_owned_output(db: Session, user: User, output_id: uuid.UUID) -> CrunchOutput | None:
    return db.scalar(
        select(CrunchOutput).where(CrunchOutput.id == output_id, CrunchOutput.user_id == user.id)
    )


def list_outputs(db: Session, user: User) -> list[CrunchOutput]:
    return list(
        db.scalars(
            select(CrunchOutput)
            .where(CrunchOutput.user_id == user.id)
            .order_by(CrunchOutput.created_at.desc())
            .limit(30)
        ).all()
    )
