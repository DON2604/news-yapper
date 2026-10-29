from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent

_FORBIDDEN_KEYS = {
    "body",
    "title",
    "text",
    "content",
    "note",
    "prompt",
    "api_key",
    "token",
    "secret",
    "email",
}


def record(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: str | uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    **metadata: Any,
) -> None:
    """Audit trail without secrets or private note contents."""
    safe = {k: v for k, v in metadata.items() if k.lower() not in _FORBIDDEN_KEYS}
    db.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            safe_metadata=safe,
        )
    )
