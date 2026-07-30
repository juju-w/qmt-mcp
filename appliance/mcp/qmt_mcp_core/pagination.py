"""Stable opaque cursor pagination for MCP catalog views."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Callable, Iterable
from typing import TypeVar

T = TypeVar("T")

_CURSOR_VERSION = 1
_MAX_CURSOR_LENGTH = 1024
_VIEW_DIGEST_LENGTH = 32


class InvalidPaginationCursor(ValueError):
    """The supplied cursor cannot resume the current visible view."""


def _view_fingerprint(keys: list[str]) -> str:
    payload = json.dumps(keys, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(payload).hexdigest()[:_VIEW_DIGEST_LENGTH]


def _encode_cursor(after: str, view: str) -> str:
    payload = json.dumps(
        {"after": after, "v": _CURSOR_VERSION, "view": view},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str) -> tuple[str, str]:
    if not isinstance(cursor, str) or not cursor or len(cursor) > _MAX_CURSOR_LENGTH:
        raise InvalidPaginationCursor("Invalid pagination cursor")
    try:
        encoded = cursor.encode("ascii")
        padding = b"=" * (-len(encoded) % 4)
        raw = base64.b64decode(encoded + padding, altchars=b"-_", validate=True)
        payload = json.loads(raw.decode("ascii"))
    except (UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise InvalidPaginationCursor("Invalid pagination cursor") from exc
    if not isinstance(payload, dict) or set(payload) != {"after", "v", "view"}:
        raise InvalidPaginationCursor("Invalid pagination cursor")
    after = payload.get("after")
    view = payload.get("view")
    if (
        payload.get("v") != _CURSOR_VERSION
        or not isinstance(after, str)
        or not after
        or not isinstance(view, str)
        or len(view) != _VIEW_DIGEST_LENGTH
        or any(char not in "0123456789abcdef" for char in view)
    ):
        raise InvalidPaginationCursor("Invalid pagination cursor")
    return after, view


def paginate_by_key(
    items: Iterable[T],
    *,
    page_size: int,
    cursor: str | None,
    key: Callable[[T], str],
) -> tuple[list[T], str | None]:
    """Return one deterministic page bound to the complete visible item set."""
    if page_size < 1:
        raise ValueError("page_size must be positive")

    ordered = sorted(items, key=key)
    keys = [key(item) for item in ordered]
    if any(not isinstance(item_key, str) or not item_key for item_key in keys):
        raise ValueError("pagination keys must be non-empty strings")
    if len(set(keys)) != len(keys):
        raise ValueError("pagination keys must be unique")

    view = _view_fingerprint(keys)
    start = 0
    if cursor is not None:
        after, cursor_view = _decode_cursor(cursor)
        if not hmac.compare_digest(cursor_view, view):
            raise InvalidPaginationCursor("Invalid pagination cursor")
        try:
            start = keys.index(after) + 1
        except ValueError as exc:
            raise InvalidPaginationCursor("Invalid pagination cursor") from exc

    page = ordered[start : start + page_size]
    end = start + len(page)
    next_cursor = _encode_cursor(keys[end - 1], view) if page and end < len(ordered) else None
    return page, next_cursor
