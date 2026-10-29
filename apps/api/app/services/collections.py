from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ConflictError, InvalidInputError, NotFoundError
from app.models import (
    ArticleSnapshot,
    CollectionItem,
    CrunchOutput,
    MistakeVaultEntry,
    Note,
    StudyCollection,
    User,
)
from app.schemas.study import CollectionIn, CollectionItemIn, CollectionOut
from app.security.sanitize import clean_text

_ITEM_MODELS: dict[str, Any] = {
    "note": Note,
    "snapshot": ArticleSnapshot,
    "mistake": MistakeVaultEntry,
    "crunch": CrunchOutput,
}


def collection_out(db: Session, col: StudyCollection) -> CollectionOut:
    items = db.scalars(select(CollectionItem).where(CollectionItem.collection_id == col.id)).all()
    return CollectionOut(
        id=col.id,
        name=col.name,
        color=col.color,
        description=col.description,
        item_counts=dict(Counter(i.item_type for i in items)),
        items=[
            CollectionItemIn.model_validate({"item_type": i.item_type, "item_id": i.item_id}) for i in items
        ],
        created_at=col.created_at,
    )


def list_collections(db: Session, user: User) -> list[StudyCollection]:
    return list(
        db.scalars(
            select(StudyCollection).where(StudyCollection.user_id == user.id).order_by(StudyCollection.name)
        )
    )


def get_owned(db: Session, user: User, collection_id: uuid.UUID) -> StudyCollection | None:
    return db.scalar(
        select(StudyCollection).where(StudyCollection.id == collection_id, StudyCollection.user_id == user.id)
    )


def create_collection(db: Session, user: User, payload: CollectionIn) -> StudyCollection:
    name = clean_text(payload.name, 80)
    if not name:
        raise InvalidInputError("Name required")
    if db.scalar(
        select(StudyCollection.id).where(StudyCollection.user_id == user.id, StudyCollection.name == name)
    ):
        raise ConflictError("Collection already exists")
    col = StudyCollection(
        user_id=user.id, name=name, color=payload.color, description=clean_text(payload.description, 500)
    )
    db.add(col)
    db.commit()
    db.refresh(col)
    return col


def add_item(db: Session, user: User, col: StudyCollection, payload: CollectionItemIn) -> None:
    """Ownership of the referenced item is enforced in this transaction (polymorphic join table)."""
    model = _ITEM_MODELS[payload.item_type]
    owned = db.scalar(select(model.id).where(model.id == payload.item_id, model.user_id == user.id))
    if owned is None:
        raise NotFoundError("Item not found")
    exists = db.get(CollectionItem, (col.id, payload.item_type, payload.item_id))
    if exists is None:
        db.add(CollectionItem(collection_id=col.id, item_type=payload.item_type, item_id=payload.item_id))
        db.commit()


def remove_item(db: Session, col: StudyCollection, item_type: str, item_id: uuid.UUID) -> None:
    item = db.get(CollectionItem, (col.id, item_type, item_id))
    if item is not None:
        db.delete(item)
        db.commit()


def delete_collection(db: Session, col: StudyCollection) -> None:
    db.delete(col)
    db.commit()
