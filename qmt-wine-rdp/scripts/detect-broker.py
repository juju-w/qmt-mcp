#!/usr/bin/env python3
"""detect-broker — resolve a mounted broker pack into a runtime config.

Runs (as root) inside qmt-entrypoint.sh before the base entrypoint. Reads
/broker/broker.yaml (optional), auto-detects the client exe / userdata_mini /
xtquant package, converts paths to Wine form, and writes /run/qmt/broker.env.
Fails fast (non-zero) on a missing/ambiguous/invalid pack — never guesses.

Contract: specs/001-broker-pack-base/contracts/detect-broker.md
Exit codes: 0 ok | 10 mount | 11 yaml | 12 explicit-missing | 13 client | 14 xtquant
"""
from __future__ import annotations

import os
import sys

MOUNT = os.environ.get("BROKER_MOUNT", "/broker")
OUT = os.environ.get("BROKER_ENV_OUT", "/run/qmt/broker.env")
CLIENT_NAMES = ("XtItClient.exe", "XtMiniQmt.exe", "XtMiniQMT.exe")

try:
    import yaml  # python3-yaml
except Exception:  # pragma: no cover
    yaml = None


def die(code: int, msg: str):
    print(f"[detect-broker] FATAL({code}): {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def log(msg: str):
    print(f"[detect-broker] {msg}", file=sys.stderr, flush=True)


def win(path: str) -> str:
    """Linux path -> Wine path. Wine maps '/' to drive Z:."""
    return "Z:" + os.path.abspath(path).replace("/", "\\")


def find_dirs(root: str, name: str, must_contain: str | None = None) -> list[str]:
    hits = []
    for dirpath, dirnames, _ in os.walk(root):
        for d in dirnames:
            if d.lower() == name.lower():
                full = os.path.join(dirpath, d)
                if must_contain is None or os.path.exists(os.path.join(full, must_contain)):
                    hits.append(full)
    return sorted(hits)


def find_files(root: str, names: tuple[str, ...]) -> list[str]:
    lower = {n.lower() for n in names}
    hits = []
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if f.lower() in lower:
                hits.append(os.path.join(dirpath, f))
    return sorted(hits)


def load_yaml() -> dict:
    path = os.path.join(MOUNT, "broker.yaml")
    if not os.path.isfile(path):
        log("no broker.yaml; using full auto-detection")
        return {}
    if yaml is None:
        die(11, "python3-yaml unavailable but broker.yaml present")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception as exc:
        die(11, f"broker.yaml parse error: {exc}")
    if not isinstance(data, dict):
        die(11, "broker.yaml must be a mapping")
    sv = data.get("schema_version", 1)
    if sv != 1:
        die(11, f"unsupported schema_version={sv!r} (expected 1)")
    mode = ((data.get("mcp") or {}).get("mode")) or "readonly"
    if mode not in ("readonly", "trade"):
        die(11, f"invalid mcp.mode={mode!r} (expected readonly|trade)")
    return data


def resolve_client(cfg: dict) -> str:
    explicit = (cfg.get("terminal") or {}).get("client")
    if explicit:
        p = os.path.join(MOUNT, explicit)
        if not os.path.isfile(p):
            die(12, f"configured terminal.client not found: {p}")
        return p
    hits = find_files(MOUNT, CLIENT_NAMES)
    if not hits:
        die(13, f"no QMT client {CLIENT_NAMES} under {MOUNT}; set terminal.client in broker.yaml")
    if len(hits) > 1:
        die(13, "multiple client candidates; set terminal.client:\n  " + "\n  ".join(hits))
    return hits[0]


def resolve_xtquant(cfg: dict) -> str:
    """Return the directory to place on sys.path (parent of the xtquant pkg)."""
    explicit = (cfg.get("xtquant") or {}).get("path")
    if explicit:
        p = os.path.join(MOUNT, explicit)
        if os.path.isfile(os.path.join(p, "xtquant", "__init__.py")):
            return p  # p is the parent
        if os.path.isfile(os.path.join(p, "__init__.py")) and os.path.basename(p.rstrip("/")) == "xtquant":
            return os.path.dirname(p)  # p is the package itself
        die(12, f"configured xtquant.path has no importable xtquant: {p}")
    hits = find_dirs(MOUNT, "xtquant", must_contain="__init__.py")
    if not hits:
        die(14, f"no importable xtquant package under {MOUNT}; add one or set xtquant.path")
    if len(hits) > 1:
        die(14, "multiple xtquant packages; set xtquant.path:\n  " + "\n  ".join(hits))
    return os.path.dirname(hits[0])


def resolve_userdata(cfg: dict, client: str) -> str:
    """userdata_mini is created at login; never hard-fail. Explicit > beside-client > single > default."""
    explicit = (cfg.get("terminal") or {}).get("userdata")
    if explicit:
        return os.path.join(MOUNT, explicit)
    qmt_root = os.path.dirname(os.path.dirname(client))  # .../bin.x64/exe -> qmt root
    beside = os.path.join(qmt_root, "userdata_mini")
    if os.path.isdir(beside):
        return beside
    hits = find_dirs(MOUNT, "userdata_mini")
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        log("multiple userdata_mini found; defaulting beside client: " + beside)
    return beside  # created on first login


def main():
    if not os.path.isdir(MOUNT) or not os.access(MOUNT, os.R_OK):
        die(10, f"broker pack mount {MOUNT} is missing or unreadable")
    if not os.listdir(MOUNT):
        die(10, f"broker pack mount {MOUNT} is empty")
    if not os.access(MOUNT, os.W_OK):
        die(10, f"broker pack mount {MOUNT} must be read-write")

    cfg = load_yaml()
    broker_id = (cfg.get("broker") or {}).get("id") or os.path.basename(os.path.realpath(MOUNT))
    mode = ((cfg.get("mcp") or {}).get("mode")) or "readonly"

    client = resolve_client(cfg)
    bin_dir = os.path.dirname(client)
    xtq_dir = resolve_xtquant(cfg)
    userdata = resolve_userdata(cfg, client)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    lines = {
        "QMT_BROKER_ID": broker_id,
        "QMT_CLIENT_WIN": win(client),
        "QMT_BIN_DIR_WIN": win(bin_dir),
        "QMT_BIN_DIR": os.path.abspath(bin_dir),       # linux path (start-qmt cwd)
        "QMT_USERDATA_WIN": win(userdata),
        "QMT_XTQUANT_DIR_WIN": win(xtq_dir),
        "QMT_MCP_MODE": mode,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        for k, v in lines.items():
            fh.write(f"{k}={v}\n")

    log(f"broker resolved: id={broker_id} mode={mode}")
    log(f"  client   = {client}")
    log(f"  bin_dir  = {bin_dir}")
    log(f"  userdata = {userdata}")
    log(f"  xtquant  = {xtq_dir}")
    log(f"  wrote {OUT}")


if __name__ == "__main__":
    main()
