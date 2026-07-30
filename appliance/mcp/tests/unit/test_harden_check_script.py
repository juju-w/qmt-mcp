"""Security preflight behavior for static, OAuth, and hybrid deployments."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[3] / "scripts" / "harden-check.sh"
STRONG_TOKEN = "a" * 32


def _run(**values: str) -> subprocess.CompletedProcess[str]:
    env = {
        "HOME": os.environ.get("HOME", "/tmp"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "QMT_RDP_PASSWORD": "correct-horse-battery-staple",
        "MCP_HOST": "127.0.0.1",
    }
    env.update(values)
    return subprocess.run(
        [str(SCRIPT), "/path/that/does/not/exist"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_static_mode_requires_a_strong_token() -> None:
    assert _run(QMT_MCP_AUTH_MODE="static").returncode == 1
    assert _run(QMT_MCP_AUTH_MODE="static", QMT_MCP_TOKEN=STRONG_TOKEN).returncode == 0


def test_oauth_mode_does_not_require_static_token() -> None:
    result = _run(
        QMT_MCP_AUTH_MODE="oauth",
        QMT_MCP_OAUTH_ISSUER="http://127.0.0.1:9000",
        QMT_MCP_OAUTH_JWKS_URL="http://127.0.0.1:9000/jwks",
        QMT_MCP_OAUTH_RESOURCE="http://127.0.0.1:8765/mcp",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_oauth_mode_fails_closed_when_configuration_is_incomplete() -> None:
    result = _run(QMT_MCP_AUTH_MODE="oauth")
    assert result.returncode == 1
    assert "OAuth issuer is required" in result.stdout


def test_hybrid_mode_requires_both_static_and_oauth_configuration() -> None:
    oauth = {
        "QMT_MCP_AUTH_MODE": "hybrid",
        "QMT_MCP_OAUTH_ISSUER": "https://auth.example.com",
        "QMT_MCP_OAUTH_AUTHORIZATION_SERVERS": "https://auth.example.com",
        "QMT_MCP_OAUTH_JWKS_URL": "https://auth.example.com/jwks.json",
        "QMT_MCP_OAUTH_RESOURCE": "https://qmt.example.com/mcp",
    }
    assert _run(**oauth).returncode == 1
    result = _run(**oauth, QMT_MCP_TOKEN=STRONG_TOKEN)
    assert result.returncode == 0, result.stdout + result.stderr
