from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import ArticleSnapshot, Note, User, utcnow
from app.schemas.study import NoteIn, NoteOut, NotePatch
from app.security.sanitize import clean_tags, clean_text

CONTENT_FIELDS = {"title", "body", "tags", "exam_topic"}


class VersionConflict(Exception):
    def __init__(self, current: Note) -> None:
        super().__init__("Note was modified elsewhere")
        self.current = current


def note_out(note: Note) -> NoteOut:
    return NoteOut(
        id=note.id,
        title=note.title,
        body=note.body,
        color=note.color,
        tags=[str(t) for t in note.tags or []],
        exam_topic=note.exam_topic,
        board_x=note.board_x,
        board_y=note.board_y,
        pinned=note.pinned,
        archived=note.archived,
        revision_version=note.revision_version,
        snapshot_id=note.snapshot_id,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def list_notes(
    db: Session, user: User, *, archived: bool = False, tag: str | None = None, q: str | None = None
) -> list[Note]:
    stmt = select(Note).where(Note.user_id == user.id, Note.deleted_at.is_(None), Note.archived.is_(archived))
    if tag:
        stmt = stmt.where(Note.tags.contains([tag.lower()]))
    if q:
        term = f"%{q.strip()[:80]}%"
        stmt = stmt.where(Note.title.ilike(term) | Note.body.ilike(term))
    return list(db.scalars(stmt.order_by(Note.pinned.desc(), Note.updated_at.desc())).all())


def get_owned(db: Session, user: User, note_id: uuid.UUID) -> Note | None:
    return db.scalar(
        select(Note).where(Note.id == note_id, Note.user_id == user.id, Note.deleted_at.is_(None))
    )


def _owned_snapshot(db: Session, user: User, snapshot_id: uuid.UUID | None) -> uuid.UUID | None:
    if snapshot_id is None:
        return None
    owned = db.scalar(
        select(ArticleSnapshot.id).where(
            ArticleSnapshot.id == snapshot_id, ArticleSnapshot.user_id == user.id
        )
    )
    if owned is None:
        raise NotFoundError("Snapshot not found")
    return owned


def create_note(db: Session, user: User, payload: NoteIn) -> Note:
    note = Note(
        user_id=user.id,
        title=clean_text(payload.title, 200),
        body=clean_text(payload.body, 5000),
        color=payload.color,
        tags=clean_tags(payload.tags),
        exam_topic=clean_text(payload.exam_topic, 32) or None,
        board_x=payload.board_x,
        board_y=payload.board_y,
        pinned=payload.pinned,
        snapshot_id=_owned_snapshot(db, user, payload.snapshot_id),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def update_note(db: Session, note: Note, payload: NotePatch, user: User) -> Note:
    if payload.expected_version is not None and payload.expected_version != note.revision_version:
        raise VersionConflict(note)
    data = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    content_changed = False
    for key, value in data.items():
        if key == "title":
            value = clean_text(value, 200)
        elif key == "body":
            value = clean_text(value, 5000)
        elif key == "tags":
            value = clean_tags(value)
        elif key == "exam_topic":
            value = clean_text(value, 32) or None
        if key in CONTENT_FIELDS and getattr(note, key) != value:
            content_changed = True
        setattr(note, key, value)
    if content_changed:
        note.revision_version += 1
    db.commit()
    db.refresh(note)
    return note


def delete_note(db: Session, note: Note) -> None:
    note.deleted_at = utcnow()
    db.commit()
