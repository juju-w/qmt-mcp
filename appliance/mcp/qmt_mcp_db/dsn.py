"""DSN parsing + redaction (pure; feature 012).

The DSN (QMT_DB_URL) is a secret — never log/health-report it verbatim. `redact()`
masks the password so diagnostics can mention the target without leaking it.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from qmt_mcp_core.errors import McpCoreError


def parse_dsn(url: str) -> dict[str, str | int | None]:
    parts = urlsplit((url or "").strip())
    if parts.scheme not in {"postgres", "postgresql"}:
        raise McpCoreError(
            "config",
            "QMT_DB_URL must be a postgresql:// DSN",
            {"scheme": parts.scheme or "<empty>"},
        )
    if not parts.hostname or not (parts.path or "").lstrip("/"):
        raise McpCoreError("config", "QMT_DB_URL must include host and database name")
    return {
        "host": parts.hostname,
        "port": parts.port or 5432,
        "user": parts.username,
        "database": (parts.path or "").lstrip("/"),
    }


def redact(url: str) -> str:
    """Return the DSN with any password replaced by ***."""
    parts = urlsplit((url or "").strip())
    if not parts.password:
        return url or ""
    user = parts.username or ""
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{user}:***@{host}{port}" if user else f"***@{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
