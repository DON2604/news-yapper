"""Notes, snapshots, mistakes, collections."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse

from app.schemas.study import (
    CollectionIn,
    CollectionItemIn,
    CollectionOut,
    MistakeOut,
    MistakeReviewIn,
    MistakeReviewOut,
    NoteIn,
    NoteOut,
    NotePatch,
    SnapshotIn,
    SnapshotOut,
)
from app.security.auth import DB, CurrentUser
from app.security.rate_limit import rate_limit
from app.services import collections as collection_service
from app.services import mistakes as mistake_service
from app.services import notes as note_service
from app.services import snapshots as snapshot_service
from app.services.users import get_preferences

router = APIRouter(dependencies=[Depends(rate_limit("study", 300))])


@router.get("/notes", response_model=list[NoteOut], tags=["notes"])
def list_notes(
    db: DB,
    user: CurrentUser,
    archived: bool = False,
    tag: str | None = Query(default=None, max_length=32),
    q: str | None = Query(default=None, max_length=80),
) -> list[NoteOut]:
    return [
        note_service.note_out(n) for n in note_service.list_notes(db, user, archived=archived, tag=tag, q=q)
    ]


@router.post("/notes", response_model=NoteOut, status_code=201, tags=["notes"])
def create_note(payload: NoteIn, db: DB, user: CurrentUser) -> NoteOut:
    return note_service.note_out(note_service.create_note(db, user, payload))


@router.patch("/notes/{note_id}", response_model=NoteOut, tags=["notes"])
def update_note(note_id: uuid.UUID, payload: NotePatch, db: DB, user: CurrentUser) -> NoteOut | JSONResponse:
    note = note_service.get_owned(db, user, note_id)
    if note is None:
        raise HTTPException(404, "Note not found")
    try:
        return note_service.note_out(note_service.update_note(db, note, payload, user))
    except note_service.VersionConflict as conflict:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "This sticky changed on another device.",
                "current": note_service.note_out(conflict.current).model_dump(mode="json"),
            },
        )


@router.delete("/notes/{note_id}", status_code=204, tags=["notes"])
def delete_note(note_id: uuid.UUID, db: DB, user: CurrentUser) -> Response:
    note = note_service.get_owned(db, user, note_id)
    if note is None:
        raise HTTPException(404, "Note not found")
    note_service.delete_note(db, note)
    return Response(status_code=204)


@router.get("/snapshots", response_model=list[SnapshotOut], tags=["snapshots"])
def list_snapshots(db: DB, user: CurrentUser) -> list[SnapshotOut]:
    return [snapshot_service.snapshot_out(db, s) for s in snapshot_service.list_snapshots(db, user)]


@router.post("/snapshots", response_model=SnapshotOut, tags=["snapshots"])
def save_snapshot(payload: SnapshotIn, response: Response, db: DB, user: CurrentUser) -> SnapshotOut:
    snap, created = snapshot_service.save_snapshot(db, user, payload.article_slug)
    response.status_code = 201 if created else 200
    return snapshot_service.snapshot_out(db, snap, created=created)


@router.delete("/snapshots/{snapshot_id}", status_code=204, tags=["snapshots"])
def delete_snapshot(snapshot_id: uuid.UUID, db: DB, user: CurrentUser) -> Response:
    snap = snapshot_service.get_owned(db, user, snapshot_id)
    if snap is None:
        raise HTTPException(404, "Snapshot not found")
    snapshot_service.delete_snapshot(db, snap)
    return Response(status_code=204)


@router.get("/mistakes", response_model=list[MistakeOut], tags=["mistakes"])
def list_mistakes(
    db: DB, user: CurrentUser, status: Literal["active", "resolved", "all"] = "active"
) -> list[MistakeOut]:
    return mistake_service.list_mistakes(db, user, status)


@router.post("/mistakes/{mistake_id}/review", response_model=MistakeReviewOut, tags=["mistakes"])
def review_mistake(
    mistake_id: uuid.UUID, payload: MistakeReviewIn, db: DB, user: CurrentUser
) -> MistakeReviewOut:
    entry = mistake_service.get_owned(db, user, mistake_id)
    if entry is None:
        raise HTTPException(404, "Mistake not found")
    return mistake_service.review(db, user, entry, payload, get_preferences(db, user).timezone)


@router.get("/collections", response_model=list[CollectionOut], tags=["collections"])
def list_collections(db: DB, user: CurrentUser) -> list[CollectionOut]:
    return [collection_service.collection_out(db, c) for c in collection_service.list_collections(db, user)]


@router.post("/collections", response_model=CollectionOut, status_code=201, tags=["collections"])
def create_collection(payload: CollectionIn, db: DB, user: CurrentUser) -> CollectionOut:
    return collection_service.collection_out(db, collection_service.create_collection(db, user, payload))


@router.post("/collections/{collection_id}/items", response_model=CollectionOut, tags=["collections"])
def add_collection_item(
    collection_id: uuid.UUID, payload: CollectionItemIn, db: DB, user: CurrentUser
) -> CollectionOut:
    col = collection_service.get_owned(db, user, collection_id)
    if col is None:
        raise HTTPException(404, "Collection not found")
    collection_service.add_item(db, user, col, payload)
    return collection_service.collection_out(db, col)


@router.delete(
    "/collections/{collection_id}/items/{item_type}/{item_id}", status_code=204, tags=["collections"]
)
def remove_collection_item(
    collection_id: uuid.UUID,
    item_type: Literal["note", "snapshot", "mistake", "crunch"],
    item_id: uuid.UUID,
    db: DB,
    user: CurrentUser,
) -> Response:
    col = collection_service.get_owned(db, user, collection_id)
    if col is None:
        raise HTTPException(404, "Collection not found")
    collection_service.remove_item(db, col, item_type, item_id)
    return Response(status_code=204)


@router.delete("/collections/{collection_id}", status_code=204, tags=["collections"])
def delete_collection(collection_id: uuid.UUID, db: DB, user: CurrentUser) -> Response:
    col = collection_service.get_owned(db, user, collection_id)
    if col is None:
        raise HTTPException(404, "Collection not found")
    collection_service.delete_collection(db, col)
    return Response(status_code=204)
