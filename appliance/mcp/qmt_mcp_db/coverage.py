"""Cached-range coverage math (pure; feature 012).

Decides whether the warehouse already holds a requested bar range so the bars tool
can serve from the DB instead of re-downloading. Conservative: only an explicit,
fully-covered closed range qualifies; open-ended requests fall back to xtdata
(we cannot know the DB holds the very latest data).

Date strings are compared lexicographically, which is correct for the fixed-width
YYYYMMDD / YYYYMMDDHHMMSS forms the tools already validate.
"""

from __future__ import annotations


def is_covered(cached_min: str | None, cached_max: str | None, req_start: str, req_end: str) -> bool:
    if not cached_min or not cached_max:
        return False
    if not req_start or not req_end:
        # open-ended range -> may need data newer than the cache -> fall back
        return False
    return str(cached_min) <= str(req_start) and str(req_end) <= str(cached_max)
