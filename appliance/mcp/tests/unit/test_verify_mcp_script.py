"""Regression tests for the deployment verification shell script."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[4] / "skills/deploying-qmt-mcp-appliance/verify-mcp.sh"


@contextmanager
def mock_mcp(*, xtdata: str, tool_count: int):
    tool_names = ["qmt_health", "qmt_capabilities"]
    tool_names.extend(f"qmt_test_{index}" for index in range(max(0, tool_count - len(tool_names))))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format, *args):
            pass

        def send(self, status: int, body: str = "", headers: dict[str, str] | None = None):
            encoded = body.encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(encoded)))
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if self.path == "/livez":
                self.send(200, '{"ok":true,"server":"live"}', {"Content-Type": "application/json"})
                return
            self.send(404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            if self.headers.get("Authorization") != "Bearer test-token":
                self.send(401)
                return

            request = json.loads(body or b"{}")
            method = request.get("method")
            if self.headers.get("Mcp-Protocol-Version") != "2026-07-28":
                self.send(400)
                return
            if method == "server/discover":
                payload = {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "result": {"supportedVersions": ["2026-07-28"], "capabilities": {}},
                }
                self.send(200, json.dumps(payload, separators=(",", ":")))
                return
            if method == "tools/list":
                payload = {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "result": {"tools": [{"name": n} for n in tool_names]},
                }
                self.send(200, f"event: message\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n")
                return
            if method == "tools/call":
                health = {
                    "ok": True,
                    "broker_config": "loaded",
                    "xtquant_import": "ok",
                    "audit": "ok",
                    "xtdata": xtdata,
                    "xttrade": "not_authorized",
                }
                payload = {"jsonrpc": "2.0", "id": request["id"], "result": health}
                self.send(200, f"event: message\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n")
                return
            self.send(400)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def run_verifier(
    base_url: str,
    *,
    token: str | None = "test-token",
    access_token: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("QMT_MCP_TOKEN", None)
    env.pop("QMT_MCP_ACCESS_TOKEN", None)
    if token is not None:
        env["QMT_MCP_TOKEN"] = token
    if access_token is not None:
        env["QMT_MCP_ACCESS_TOKEN"] = access_token
    return subprocess.run(
        ["bash", str(SCRIPT), base_url],
        check=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env=env,
    )


def test_accepts_login_dependent_xtdata_state():
    with mock_mcp(xtdata="degraded", tool_count=37) as base_url:
        result = run_verifier(base_url)

    assert result.returncode == 0
    assert "verify-mcp: PASSED." in result.stdout


def test_rejects_xtdata_registration_error():
    with mock_mcp(xtdata="error", tool_count=37) as base_url:
        result = run_verifier(base_url)

    assert result.returncode == 1
    assert "xtdata=error" in result.stdout
    assert "verify-mcp: FAILED." in result.stdout


def test_rejects_incomplete_tool_registry():
    with mock_mcp(xtdata="ready", tool_count=36) as base_url:
        result = run_verifier(base_url)

    assert result.returncode == 1
    assert "expected at least 37" in result.stdout


def test_requires_token_when_not_interactive():
    result = run_verifier("http://127.0.0.1:38765", token=None)

    assert result.returncode == 2
    assert "set QMT_MCP_ACCESS_TOKEN or QMT_MCP_TOKEN" in result.stderr


def test_access_token_takes_precedence_over_static_token():
    with mock_mcp(xtdata="ready", tool_count=37) as base_url:
        result = run_verifier(base_url, token="wrong-static-token", access_token="test-token")

    assert result.returncode == 0
    assert "verify-mcp: PASSED." in result.stdout


def test_rejects_plain_http_for_remote_hosts():
    result = run_verifier("http://192.0.2.1:38765")

    assert result.returncode == 2
    assert "refusing remote plain HTTP" in result.stderr
