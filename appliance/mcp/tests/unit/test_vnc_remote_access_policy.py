"""Policy and lifecycle gates for optional same-session VNC access."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).parents[4]
APPLIANCE = ROOT / "appliance"
HARDEN = APPLIANCE / "scripts" / "harden-check.sh"
SUPERVISOR = APPLIANCE / "scripts" / "persistent-desktop-supervisor.sh"
STRONG_PASSWORD = "correct-horse-battery-staple"
STRONG_TOKEN = "a" * 32


def _preflight(**values: str) -> subprocess.CompletedProcess[str]:
    env = {
        "HOME": os.environ.get("HOME", "/tmp"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "QMT_MCP_AUTH_MODE": "static",
        "QMT_MCP_TOKEN": STRONG_TOKEN,
        "QMT_RDP_PASSWORD": STRONG_PASSWORD,
        "QMT_DESKTOP_MODE": "persistent",
        "MCP_HOST": "127.0.0.1",
        "RDP_BIND_ADDRESS": "127.0.0.1",
        "QMT_VNC_ENABLED": "1",
        "QMT_VNC_PASSWORD": "unique-vnc-password",
        "VNC_BIND_ADDRESS": "127.0.0.1",
    }
    env.update(values)
    return subprocess.run(
        [str(HARDEN), "/path/that/does/not/exist"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_status(path: Path, predicate, timeout: float = 15) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    last: dict[str, object] = {}
    while time.monotonic() < deadline:
        try:
            last = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            time.sleep(0.1)
            continue
        if predicate(last):
            return last
        time.sleep(0.1)
    raise AssertionError(f"status predicate timed out; last={last!r}")


def test_image_and_compose_keep_vnc_opt_in_and_loopback() -> None:
    dockerfile = (APPLIANCE / "Dockerfile").read_text(encoding="utf-8")
    common = (APPLIANCE / "docker-compose.common.yml").read_text(encoding="utf-8")
    base = (APPLIANCE / "docker-compose.yml").read_text(encoding="utf-8")
    vnc = (APPLIANCE / "docker-compose.vnc.yml").read_text(encoding="utf-8")

    assert '"x11vnc=${X11VNC_VERSION}"' in dockerfile
    assert '"tigervnc-tools=${TIGERVNC_TOOLS_VERSION}"' in dockerfile
    assert dockerfile.index("FROM wine-runtime AS runtime") < dockerfile.index("x11vnc=${X11VNC_VERSION}")
    assert 'QMT_VNC_ENABLED: "${QMT_VNC_ENABLED:-0}"' in common
    assert "EXPOSE 3389 5900 8765" not in dockerfile
    assert ":5900" not in base
    assert 'QMT_VNC_ENABLED: "1"' in vnc
    assert "${VNC_BIND_ADDRESS:-127.0.0.1}:${VNC_PORT:-15900}:5900" in vnc


def test_entrypoint_and_supervisor_do_not_copy_or_argv_expose_secret() -> None:
    entrypoint = (APPLIANCE / "scripts" / "qmt-entrypoint.sh").read_text(encoding="utf-8")
    desktop = SUPERVISOR.read_text(encoding="utf-8")

    assert "tigervncpasswd -f" in entrypoint
    assert "x11vnc -storepasswd" not in entrypoint
    assert 'echo "QMT_VNC_PASSWORD=' not in entrypoint
    assert "rm -rf /run/qmt/vnc" not in entrypoint
    assert "rm -f /run/qmt/vnc/passwd" in entrypoint
    assert entrypoint.index('chmod 0600 "$vnc_password_tmp"') < entrypoint.index(
        'chown "$RUNTIME_UID:$RUNTIME_GID" "$vnc_password_tmp"'
    )
    assert "QMT_VNC_PASSWORD" not in desktop
    assert "-rfbauth" in desktop
    assert "-norc" in desktop
    assert "-safer" in desktop
    assert "-nocmds" in desktop
    assert "-notightfilexfer" in desktop
    assert "-tightfilexfer" not in desktop.replace("-notightfilexfer", "")
    assert "-ultrafilexfer" not in desktop

    image_gate = (APPLIANCE / "scripts" / "verify-desktop-image.sh").read_text()
    assert 'x11vnc_help="$(x11vnc -help 2>&1 || :)"' in image_gate
    assert "grep -aFq -- '-notightfilexfer'" in image_gate
    assert "x11vnc -help 2>&1 | grep -Fq" not in image_gate
    assert "-forever" in desktop
    assert "-shared" in desktop
    assert "-noxdamage" in desktop
    assert "-repeat" in desktop
    assert "-nosel" in desktop
    assert "Xvfb" not in desktop
    assert 'if [ "$VNC_ENABLED" = "1" ]; then\n  case "$VNC_PORT" in' in desktop


def test_hardening_rejects_manual_mode_wildcard_and_weak_secret() -> None:
    secret = "never-print-this-vnc-secret"
    result = _preflight(
        QMT_DESKTOP_MODE="manual",
        VNC_BIND_ADDRESS="0.0.0.0",
        QMT_VNC_ALLOW_LAN="0",
        QMT_VNC_PASSWORD=secret,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "requires QMT_DESKTOP_MODE=persistent" in output
    assert "requires QMT_VNC_ALLOW_LAN=1" in output
    assert secret not in output

    weak = _preflight(QMT_VNC_PASSWORD="short")
    assert weak.returncode == 1
    assert "VNC password is too short" in weak.stdout


def test_hardening_accepts_owner_only_vnc_password_file(tmp_path: Path) -> None:
    secret_file = tmp_path / "vnc-password"
    secret_file.write_text("random-vnc-secret", encoding="utf-8")
    secret_file.chmod(0o600)

    result = _preflight(QMT_VNC_PASSWORD="", QMT_VNC_PASSWORD_FILE=str(secret_file))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VNC password is file-backed" in result.stdout

    secret_file.chmod(0o644)
    result = _preflight(QMT_VNC_PASSWORD="", QMT_VNC_PASSWORD_FILE=str(secret_file))
    assert result.returncode == 1
    assert "must not grant group/other permissions" in result.stdout


def test_supervisor_restarts_only_vnc_adapter(tmp_path: Path) -> None:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    status_file = tmp_path / "status.json"
    xauth = tmp_path / "Xauthority"
    auth = tmp_path / "vnc-passwd"
    xauth.write_text("fixture", encoding="utf-8")
    auth.write_bytes(b"fixture")
    xauth.chmod(0o600)
    auth.chmod(0o600)

    xorg = subprocess.Popen(["sleep", "300"])
    desktop_services = subprocess.Popen(["sleep", "300"])
    (tmp_path / "xrdp.pid").write_text(str(desktop_services.pid), encoding="ascii")
    (tmp_path / "sesman.pid").write_text(str(desktop_services.pid), encoding="ascii")

    _write_executable(
        bindir / "sesrun",
        "#!/bin/sh\nprintf 'session created display=:10\\n'\n",
    )
    _write_executable(
        bindir / "pgrep",
        "#!/bin/sh\nprintf '%s\\n' \"$FAKE_XORG_PID\"\n",
    )
    _write_executable(
        bindir / "gosu",
        '#!/bin/sh\nshift\nexec "$@"\n',
    )
    _write_executable(bindir / "curl", "#!/bin/sh\nexit 0\n")
    _write_executable(bindir / "wineserver", "#!/bin/sh\nexit 0\n")
    _write_executable(
        bindir / "timeout",
        '#!/bin/sh\nshift\nexec "$@"\n',
    )
    _write_executable(
        bindir / "x11vnc",
        """#!/usr/bin/env python3
import signal
import socket
import sys

port = int(sys.argv[sys.argv.index("-rfbport") + 1])
listener = socket.socket()
listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listener.bind(("0.0.0.0", port))
listener.listen()

def stop(*_args):
    listener.close()
    raise SystemExit(0)

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
while True:
    connection, _ = listener.accept()
    connection.close()
""",
    )

    vnc_port = _free_port()
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bindir}:{env.get('PATH', '/usr/bin:/bin')}",
            "FAKE_XORG_PID": str(xorg.pid),
            "QMT_DESKTOP_STATUS_FILE": str(status_file),
            "XRDP_SESRUN_BIN": str(bindir / "sesrun"),
            "XRDP_PIDFILE": str(tmp_path / "xrdp.pid"),
            "XRDP_SESMAN_PIDFILE": str(tmp_path / "sesman.pid"),
            "QMT_RDP_PASSWORD": STRONG_PASSWORD,
            "QMT_RDP_BOOT_RETRIES": "0",
            "QMT_RDP_BOOT_BACKOFF_S": "1",
            "QMT_DESKTOP_MONITOR_INTERVAL_S": "1",
            "QMT_VNC_ENABLED": "1",
            "QMT_VNC_PORT": str(vnc_port),
            "QMT_VNC_AUTH_FILE": str(auth),
            "QMT_VNC_XAUTHORITY": str(xauth),
            "QMT_VNC_RESTART_BACKOFF_S": "1",
        }
    )

    supervisor = subprocess.Popen(
        ["bash", str(SUPERVISOR)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        initial = _wait_status(
            status_file,
            lambda state: state.get("vnc_ready") is True and state.get("mcp_ready") is True,
        )
        assert initial["schema_version"] == 2
        assert initial["display"] == ":10"
        assert initial["xorg_pid"] == xorg.pid
        assert initial["vnc_state"] == "ready"
        first_vnc_pid = int(initial["vnc_pid"])

        os.kill(first_vnc_pid, signal.SIGTERM)
        recovered = _wait_status(
            status_file,
            lambda state: state.get("vnc_ready") is True and state.get("vnc_pid") not in (None, first_vnc_pid),
        )
        assert recovered["xorg_pid"] == xorg.pid
        assert supervisor.poll() is None
        assert xorg.poll() is None
    finally:
        if supervisor.poll() is None:
            supervisor.terminate()
            try:
                supervisor.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                supervisor.kill()
                supervisor.communicate(timeout=5)
        for process in (xorg, desktop_services):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
