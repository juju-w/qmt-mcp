"""Dependency-light tests for stable MCP catalog pagination."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from qmt_mcp_core.pagination import InvalidPaginationCursor, paginate_by_key


@dataclass(frozen=True)
class Item:
    name: str


def _page(items, page_size, cursor=None):
    return paginate_by_key(items, page_size=page_size, cursor=cursor, key=lambda item: item.name)


def test_pages_are_sorted_non_overlapping_and_terminate():
    items = [Item("delta"), Item("alpha"), Item("charlie"), Item("bravo"), Item("echo")]

    first, cursor1 = _page(items, 2)
    second, cursor2 = _page(items, 2, cursor1)
    final, cursor3 = _page(items, 2, cursor2)

    assert [item.name for item in first] == ["alpha", "bravo"]
    assert [item.name for item in second] == ["charlie", "delta"]
    assert [item.name for item in final] == ["echo"]
    assert cursor1
    assert cursor2
    assert cursor3 is None


def test_exact_page_and_empty_catalog_omit_cursor():
    page, cursor = _page([Item("bravo"), Item("alpha")], 2)
    assert [item.name for item in page] == ["alpha", "bravo"]
    assert cursor is None

    page, cursor = _page([], 2)
    assert page == []
    assert cursor is None


def test_cursor_is_deterministic_for_same_visible_view():
    items = [Item("charlie"), Item("alpha"), Item("bravo")]
    assert _page(items, 1)[1] == _page(reversed(items), 1)[1]


def test_cursor_is_rejected_when_visible_view_changes():
    items = [Item("alpha"), Item("bravo"), Item("charlie")]
    _page1, cursor = _page(items, 1)

    with pytest.raises(InvalidPaginationCursor):
        _page([*items, Item("delta")], 1, cursor)

    with pytest.raises(InvalidPaginationCursor):
        _page(items[1:], 1, cursor)


@pytest.mark.parametrize(
    "cursor",
    [
        "",
        "not-base64!",
        "e30",  # {}
        "A" * 1025,
    ],
)
def test_malformed_or_oversized_cursor_is_rejected(cursor):
    with pytest.raises(InvalidPaginationCursor):
        _page([Item("alpha"), Item("bravo")], 1, cursor)


def test_duplicate_keys_and_invalid_page_sizes_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        _page([Item("alpha"), Item("alpha")], 1)
    with pytest.raises(ValueError, match="page_size"):
        _page([Item("alpha")], 0)
