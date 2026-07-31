"""Static and preflight gates for the persistent desktop security boundary."""

from __future__ import annotations

import configparser
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[4]
APPLIANCE = ROOT / "appliance"
HARDEN = APPLIANCE / "scripts" / "harden-check.sh"
STRONG_PASSWORD = "correct-horse-battery-staple"
STRONG_TOKEN = "a" * 32


def _preflight(**values: str) -> subprocess.CompletedProcess[str]:
    env = {
        "HOME": os.environ.get("HOME", "/tmp"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "QMT_MCP_AUTH_MODE": "static",
        "QMT_MCP_TOKEN": STRONG_TOKEN,
        "QMT_RDP_PASSWORD": STRONG_PASSWORD,
        "MCP_HOST": "127.0.0.1",
        "RDP_BIND_ADDRESS": "127.0.0.1",
    }
    env.update(values)
    return subprocess.run(
        [str(HARDEN), "/path/that/does/not/exist"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _ini(name: str) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(strict=False)
    parser.read(APPLIANCE / "config" / "xrdp" / name)
    return parser


def test_xrdp_sources_are_version_and_checksum_pinned() -> None:
    dockerfile = (APPLIANCE / "Dockerfile").read_text(encoding="utf-8")
    assert "XRDP_VERSION=0.10.6.1" in dockerfile
    assert "XORGXRDP_VERSION=0.10.5" in dockerfile
    assert "2f7beb5a3b2529c8d72dc0df9b8cdca31ab0e0c14d1e3421210f5e6ec0ab3b75" in dockerfile
    assert "a5d03435f0ef48bf3d5010e63d9264f2334e7063cba3ecd8d4c0a15616a4f712" in dockerfile
    assert "COPY --from=xrdp-builder" in dockerfile
    assert dockerfile.index("FROM wine-runtime AS runtime") < dockerfile.index("COPY --from=xrdp-builder")
    assert "RUN /usr/local/bin/verify-desktop-image.sh" in dockerfile


def test_project_xrdp_policy_is_tls_only_and_single_session() -> None:
    xrdp = _ini("xrdp.ini")
    sesman = _ini("sesman.ini")

    assert xrdp["Globals"]["security_layer"] == "tls"
    assert xrdp["Globals"]["ssl_protocols"] == "TLSv1.2, TLSv1.3"
    assert xrdp["Globals"]["autorun"] == "Xorg"
    assert xrdp["Channels"]["rdpdr"] == "false"
    assert xrdp["Channels"]["cliprdr"] == "false"
    assert sesman["Security"]["allowrootlogin"] == "false"
    assert sesman["Security"]["alwaysgroupcheck"] == "true"
    assert sesman["Security"]["terminalserverusers"] == "qmt-rdp"
    assert sesman["Sessions"]["maxsessions"] == "1"
    assert sesman["Sessions"]["killdisconnected"] == "false"


def test_base_compose_defaults_rdp_to_loopback_without_a_password() -> None:
    compose = (APPLIANCE / "docker-compose.yml").read_text(encoding="utf-8")
    common = (APPLIANCE / "docker-compose.common.yml").read_text(encoding="utf-8")

    assert "${RDP_BIND_ADDRESS:-127.0.0.1}:${RDP_PORT:-13389}:3389" in compose
    assert 'QMT_RDP_PASSWORD: "${QMT_RDP_PASSWORD:-}"' in common
    assert 'USER_SUDO: "no"' in common
    assert "no-new-privileges:true" in common
    assert "cap_drop:\n      - ALL" in common
    for capability in ("CHOWN", "DAC_OVERRIDE", "KILL", "SETGID", "SETUID"):
        assert f"      - {capability}\n" in common
    assert "      - FOWNER\n" not in common
    assert "ports:" not in common


def test_bootstrap_uses_fd_password_and_kernel_singletons() -> None:
    desktop = (APPLIANCE / "scripts" / "persistent-desktop-supervisor.sh").read_text(encoding="utf-8")
    configure = (APPLIANCE / "scripts" / "configure-xrdp.sh").read_text(encoding="utf-8")
    entrypoint = (APPLIANCE / "scripts" / "qmt-entrypoint.sh").read_text(encoding="utf-8")
    qmt = (APPLIANCE / "scripts" / "start-qmt.sh").read_text(encoding="utf-8")
    mcp = (APPLIANCE / "scripts" / "qmt-supervisor.sh").read_text(encoding="utf-8")

    assert '"$SESRUN_BIN"' in desktop
    assert "-F 0" in desktop
    assert " -p " not in desktop
    assert 'XRDP_PIDFILE="${XRDP_PIDFILE:-/run/xrdp.pid}"' in desktop
    assert 'SESMAN_PIDFILE="${XRDP_SESMAN_PIDFILE:-/run/xrdp-sesman.pid}"' in desktop
    assert "chown root:xrdp /etc/xrdp/rsakeys.ini" in configure
    assert "chmod 0640 /etc/xrdp/rsakeys.ini" in configure
    assert 'install -d -m 0700 -o "$RUNTIME_UID"' in entrypoint
    assert "flock -n 9" in qmt
    assert "flock -n 9" in mcp


def test_preflight_rejects_unsafe_rdp_fixtures_without_leaking_secret() -> None:
    secret = "never-print-this-rdp-secret"
    wildcard = _preflight(
        QMT_RDP_PASSWORD=secret,
        RDP_BIND_ADDRESS="0.0.0.0",
        QMT_RDP_ALLOW_LAN="0",
    )
    assert wildcard.returncode == 1
    assert "requires QMT_RDP_ALLOW_LAN=1" in wildcard.stdout
    assert secret not in wildcard.stdout + wildcard.stderr

    drive = _preflight(
        QMT_RDP_DRIVE_REDIRECTION="1",
        QMT_RDP_ALLOW_UNSAFE_CHANNELS="0",
    )
    assert drive.returncode == 1
    assert "drive redirection requires" in drive.stdout


def test_preflight_accepts_owner_only_password_file(tmp_path: Path) -> None:
    secret_file = tmp_path / "rdp-password"
    secret_file.write_text(STRONG_PASSWORD, encoding="utf-8")
    secret_file.chmod(0o600)

    result = _preflight(QMT_RDP_PASSWORD="", QMT_RDP_PASSWORD_FILE=str(secret_file))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RDP password is file-backed" in result.stdout

    secret_file.chmod(0o644)
    result = _preflight(QMT_RDP_PASSWORD="", QMT_RDP_PASSWORD_FILE=str(secret_file))
    assert result.returncode == 1
    assert "must not grant group/other permissions" in result.stdout
