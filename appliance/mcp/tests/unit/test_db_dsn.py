"""Unit tests for DSN parse + redaction (feature 012)."""

from __future__ import annotations

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_db.dsn import parse_dsn, redact


def test_parse_dsn_ok():
    d = parse_dsn("postgresql://user:pw@db.host:6543/qmt")
    assert d == {"host": "db.host", "port": 6543, "user": "user", "database": "qmt"}


def test_parse_dsn_default_port():
    assert parse_dsn("postgres://u:p@h/qmt")["port"] == 5432


@pytest.mark.parametrize("bad", ["", "mysql://u:p@h/db", "postgresql://h", "postgresql://u@h/"])
def test_parse_dsn_rejects(bad):
    with pytest.raises(McpCoreError) as exc:
        parse_dsn(bad)
    assert exc.value.error_type == "config"


def test_redact_masks_password():
    assert redact("postgresql://user:secret@h:5432/qmt") == "postgresql://user:***@h:5432/qmt"


def test_redact_no_password_unchanged():
    assert redact("postgresql://user@h/qmt") == "postgresql://user@h/qmt"


def test_redact_never_leaks_secret():
    assert "secret" not in redact("postgresql://user:secret@h/qmt")
