---
name: deploying-qmt-mcp-appliance
description: Use when building or deploying the QMT-MCP appliance for the first time, deploying to a remote Linux host, building from a Windows workstation, or when the container exits immediately, exits with code 10-14, reports `bash\r: No such file or directory`, has no xtquant package, or `/livez` returns nothing and the container stays unhealthy.
---

# Deploying the QMT-MCP Appliance

First-deploy and remote-deploy failures, and how to verify the result. For steady-state
operations, tool tables, and `qmtctl` usage see **qmt-mcp-ops**.

## Core principle

Three things break a first deploy, and none of them announce themselves clearly:
the **broker pack is incomplete** (the QMT installer ships no `xtquant`), the
**scripts have CRLF endings** (baked into the image, not visible in `git diff`), and
the **MCP only starts on RDP desktop login** (so a correct deploy still looks dead).

## Pre-flight

| Check | Command | Requirement |
|---|---|---|
| Native amd64 | `dpkg --print-architecture` | `amd64`. Apple Silicon = emulation, QMT hits Rosetta AVX |
| Disk | `df -h /` | **≥ 12 GB free.** Final image ≈ 8.7 GB, build cache adds ≈ 5 GB |
| Real disk mount | — | Pack must NOT be on tmpfs/ramfs (RAM exhaustion) |
| Host tools | `command -v 7z unzip` | `make-broker-pack.sh` needs `7z`; `unzip` (zip) or `unrar` (RAR5) |

Docker's real usage may live under `/var/lib/containerd`, not `/var/lib/docker` — check
both when hunting space. `docker builder prune -af` reclaims the cache after a build.

## Gotcha 1: CRLF from a Windows checkout kills the image

**Symptom:** container exits instantly; `/usr/bin/env: 'bash\r': No such file or directory`.

**Cause:** git `core.autocrlf=true` checks out `scripts/*.sh` with CRLF. `COPY scripts/`
bakes `#!/usr/bin/env bash\r` into the image. The repo's *stored blobs are LF*, so
`git diff` shows nothing and `git status` is clean.

```bash
# Detect (on the build host, before building)
head -1 appliance/scripts/qmt-entrypoint.sh | od -c | head -2   # look for \r \n

# Fix
find . -type f \( -name "*.sh" -o -name "*.py" \) -exec sed -i 's/\r$//' {} +
```

A `.gitattributes` forcing `eol=lf` on `*.sh`/`*.py`/`*.yml`/`*.yaml`/`Dockerfile`
prevents recurrence.

**You MUST rebuild after fixing.** The bad shebangs live in an image layer; fixing the
working tree changes nothing about an already-built image. Verify inside the image, not
on disk:

```bash
docker run --rm --entrypoint /bin/head <image> -1 /usr/local/bin/qmt-entrypoint.sh | od -c | head -2
```

Probe *after* `docker build` fully exports ("unpacking to ... done"). Probing mid-export
silently reads the previous image and you will "confirm" a fix that didn't happen.

## Gotcha 2: the QMT installer contains no xtquant

`make-broker-pack.sh` wants two inputs. Brokers ship the terminal installer; the
`xtquant` Python package is **separate and often not provided**. Verify before assuming:

```bash
7z l <setup_qmt.exe> | grep -iE 'xtquant|xtdata\.py'   # DLLs only = no Python package
```

Get a version-matched wheel from PyPI instead. **A wheel is a zip**, so the pack script
accepts it if renamed:

```bash
curl -fsSL -o xtquant.whl "https://pypi.tuna.tsinghua.edu.cn/packages/.../xtquant-250807.1.2-py3-none-any.whl"
sha256sum xtquant.whl                                   # verify against the PyPI index
cp xtquant.whl xtquant.zip                              # .whl is not a recognised extension
scripts/make-broker-pack.sh setup_qmt.exe xtquant.zip brokers/<id>/pack <broker-id>
```

The wheel must carry a `.pyd` matching the image's Python — `datacenter.cp312-win_amd64.pyd`
for Windows Python 3.12. Prove it imports under Wine rather than trusting the file listing:

```bash
docker exec -u wineuser <container> bash -lc \
  'cd /broker && xvfb-run -a wine "C:\\Python312\\python.exe" -c \
   "import sys; sys.path.insert(0, r\"Z:\\broker\"); import xtquant; from xtquant import xtdata; print(\"OK\")"'
```

Pass a script file rather than inline `-c` when nesting through `ssh` + `docker exec` —
backslashes get eaten and you get `failed to open "C:Python312python.exe"`.

## Gotcha 3: two client exes are not ambiguous

Real QMT trees ship both `XtItClient.exe` and `XtMiniQmt.exe`. This looks like exit 13
but isn't: `detect-broker` walks `CLIENT_NAMES` in priority order and the first name with
**exactly one** hit wins, so `XtItClient.exe` resolves. Pin it in `broker.yaml` anyway
for reproducibility. `userdata_mini` need not exist — it's created at login.

## Gotcha 4: a healthy deploy looks dead

MCP and the QMT terminal are launched by **XFCE autostart on RDP login**, not by the
entrypoint. So after `up -d` (and after every `restart`): container is `unhealthy`,
`/livez` returns nothing, no process listening inside. **This is by design.**

To verify the server headlessly without an RDP session:

```bash
docker exec -u wineuser -d <container> bash -lc \
  'nohup /usr/local/bin/qmt-supervisor.sh > /tmp/sup.log 2>&1'
sleep 50 && docker exec <container> cat /tmp/sup.log   # expect "Application startup complete"
```

`xtdata: degraded` + `无法连接xtquant服务` and `xttrade: not_authorized` persist until a
human logs into the *terminal* over RDP. Not a deploy fault — don't chase it.

## Remote deploy from a Windows workstation

```bash
# rsync is often absent on both ends; tar-over-ssh needs nothing extra
tar czf - --exclude='.git' --exclude='__pycache__' --exclude='brokers/*/pack' \
    appliance cli skills VERSION | ssh <host> 'tar xzf - -C ~/project/qmt-mcp'
ssh <host> "cd ~/project/qmt-mcp && find . -type f \( -name '*.sh' -o -name '*.py' \) \
    -exec sed -i 's/\r\$//' {} +"        # ALWAYS strip CRLF after transferring
```

Upload the installer with `cat file | ssh host 'cat > dest'` and **compare `md5sum` on both
ends** — a truncated 240 MB upload produces confusing downstream failures.

Pull the base image separately before building. The pinned mirror
(`docker.1ms.run`) intermittently drops layers, surfacing as
`failed to compute cache key: short read: expected N bytes but got 0` — a *network*
error wearing a cache error's clothes. `docker pull` it, then build.

## Verification

Run `verify-mcp.sh` (in this skill directory) — handshake, auth enforcement, and tool
count in one shot:

```bash
./verify-mcp.sh http://<host>:38765 <token>
```

Manual probes worth knowing:

| Check | Expected |
|---|---|
| `curl -s <base>/livez` | `{"ok": true, "server": "live"}` |
| `curl -o /dev/null -w '%{http_code}' -X POST <base>/mcp -d '{}'` | `401` |
| `docker inspect <c> --format '{{.State.Health.Status}}'` | `healthy` |
| audit log `<pack>/logs/mcp-audit.jsonl` | one JSONL line per tool call |

MCP calls need `Accept: application/json, text/event-stream` and the `mcp-session-id`
header from `initialize`; responses are SSE (`event: message\ndata: {...}`).

Audit timestamps carry Wine's TZ offset (e.g. `+0100`) while the container is
`Asia/Shanghai`. Same instant, different notation — not a misconfiguration.

`harden-check.sh` defaults to `appliance/.env` **relative to the repo root**. Run from
`appliance/` and it reports "not found" then fails on empty values it never read. Pass
the path: `./scripts/harden-check.sh .env`.

## Red flags

- Probing an image for a fix while `docker build` is still exporting
- Trusting `git status`/`git diff` to reveal CRLF (they can't)
- Concluding "deploy failed" from `unhealthy` + dead `/livez` before starting a session
- Assuming the broker installer includes `xtquant`
- Skipping the `md5sum` check on a large upload
- Chasing `xtdata: degraded` before the terminal has been logged into

## Common mistakes

| Mistake | Consequence |
|---|---|
| Fix CRLF, don't rebuild | Container keeps dying on baked-in `bash\r` |
| `docker build` without pre-pulling base | Spurious "cache key" failure mid-build |
| Pass `.whl` to `make-broker-pack.sh` | `unsupported xtquant archive` — copy to `.zip` |
| Nested inline `wine -c "..."` over ssh | `failed to open "C:Python312python.exe"` |
| Publish MCP on `0.0.0.0` over plain HTTP | Bearer token sniffable; use TLS proxy per `docs/DEPLOY.md` |
