from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatAskIn(BaseModel):
    message: str = Field(min_length=2, max_length=500)


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    body: str
    status: Literal["ready", "pending", "failed"]
    cached: bool
    created_at: datetime


class ChatThreadOut(BaseModel):
    available: bool
    serious: bool
    pending: bool
    messages: list[ChatMessageOut]
