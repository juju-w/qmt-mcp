"""Account types + id validation + server-side allowlist (feature 004).

The allowlist is resolved from server config ONCE; tools look accounts up by id.
The agent passes only an account id and can never widen the set via arguments —
an unknown id is refused (fail-closed, constitution VI).
"""

from __future__ import annotations

import re
from enum import Enum

from qmt_mcp_core.errors import McpCoreError

# QMT account ids are short digit/alnum strings. Keep the check strict but lenient
# enough for the common broker formats (pure digits, or alnum with a dash).
ACCOUNT_ID_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z\-]{1,31}$")


class AccountType(str, Enum):
    STOCK = "STOCK"
    CREDIT = "CREDIT"
    FUTURE = "FUTURE"

    @classmethod
    def parse(cls, value: str) -> AccountType:
        try:
            return cls(str(value).strip().upper())
        except ValueError as exc:
            raise McpCoreError(
                "config",
                f"invalid account type: {value}",
                {"allowed": [t.value for t in cls]},
            ) from exc


def validate_account_id(account_id: str) -> str:
    aid = (account_id or "").strip()
    if not ACCOUNT_ID_RE.match(aid):
        raise McpCoreError("validation", f"invalid account id: {account_id}", {"expected": "short alphanumeric id"})
    return aid


class Allowlist:
    """Immutable, server-resolved set of permitted accounts."""

    def __init__(self, account_ids: list[str], account_type: AccountType):
        self.account_type = account_type
        self._ids = {validate_account_id(a) for a in account_ids if a and a.strip()}

    @classmethod
    def from_config(cls, raw_ids: str, raw_type: str) -> Allowlist:
        ids = [part.strip() for part in (raw_ids or "").split(",") if part.strip()]
        return cls(ids, AccountType.parse(raw_type or "STOCK"))

    def __bool__(self) -> bool:
        return bool(self._ids)

    def ids(self) -> list[str]:
        return sorted(self._ids)

    def require(self, account_id: str) -> str:
        """Return the id iff it is on the allowlist; else refuse (fail-closed)."""
        aid = validate_account_id(account_id)
        if aid not in self._ids:
            raise McpCoreError(
                "validation",
                "account is not on the server allowlist",
                {"account_id": aid, "allowed_count": len(self._ids)},
            )
        return aid
