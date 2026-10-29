"""User text is stored as plain text: all HTML is stripped server-side and the
frontend renders it as text nodes only (never as HTML)."""

from __future__ import annotations

import html
import re

import nh3

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TAG_SAFE = re.compile(r"[^\w\s\-#+.&/]", re.UNICODE)


def clean_text(value: str | None, max_len: int) -> str:
    if not value:
        return ""
    stripped = nh3.clean(value, tags=set(), clean_content_tags={"script", "style"})
    text = html.unescape(stripped)
    text = _CONTROL.sub("", text).replace("\r\n", "\n")
    return text.strip()[:max_len]


def clean_tags(tags: list[str] | None, max_tags: int = 12, max_len: int = 32) -> list[str]:
    out: list[str] = []
    for tag in tags or []:
        t = _TAG_SAFE.sub("", clean_text(tag, max_len)).strip().lower()
        if t and t not in out:
            out.append(t)
        if len(out) >= max_tags:
            break
    return out
