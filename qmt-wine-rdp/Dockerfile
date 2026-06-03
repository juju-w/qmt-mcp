# Broker-AGNOSTIC base image for the QMT-MCP appliance (feature 001).
#
# Contains ONLY the generic, broker-neutral runtime:
#   - Wine new-WoW64 on native linux/amd64
#   - Windows Python 3.12 installed into the Wine prefix
#   - CJK fonts (Linux desktop + inside the Wine prefix)
#   - fastmcp + uvicorn + numpy/pandas (MCP + xtdata deps)
#   - the read-only QMT MCP launcher + scripts + XFCE autostart
#   - xrdp desktop
#   - detect-broker tooling (python3 + python3-yaml)
#
# It contains NO QMT terminal, NO xtquant, NO broker data. Those are supplied at
# runtime as a read-write "broker pack" mounted at /broker; detect-broker resolves
# them on start. Switch brokers by swapping the mounted pack — never rebuild.
#
# Build MUST run on linux/amd64. Apple Silicon only works under emulation, where
# QMT native services can hit the Rosetta AVX assertion; build/run on the x86 NAS.
FROM docker.1ms.run/scottyhardy/docker-wine:stable

# ---- pinned versions / sources (override with --build-arg) ----
ARG PY_VERSION=3.12.10
ARG PY_URL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe

ENV WINEARCH=wow64 \
    WINEPREFIX=/home/wineuser/.wine \
    WINEDEBUG=-all \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PY_WIN_DIR=C:\\Python312 \
    BROKER_MOUNT=/broker

# ---- system packages: CJK fonts, archive tools (pack-making), broker config ----
# Aliyun mirror for the Ubuntu archive (noble deb822). unrar handles the RAR5
# xtquant used by make-broker-pack; 7z handles the NSIS terminal installer.
# python3 + python3-yaml power detect-broker. NO xtquant, NO terminal here.
RUN set -eux; \
    for f in /etc/apt/sources.list /etc/apt/sources.list.d/ubuntu.sources; do \
      [ -f "$f" ] && sed -i \
        -e 's|http://archive.ubuntu.com/ubuntu|https://mirrors.aliyun.com/ubuntu|g' \
        -e 's|http://security.ubuntu.com/ubuntu|https://mirrors.aliyun.com/ubuntu|g' \
        "$f" || true; \
    done; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget git unzip ca-certificates \
        p7zip-full unrar \
        python3 python3-yaml \
        fonts-noto-cjk fonts-wqy-microhei fonts-wqy-zenhei; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

# ---- helper scripts + MCP launcher ----
COPY scripts/ /usr/local/bin/
RUN chmod +x /usr/local/bin/*.sh /usr/local/bin/detect-broker.py

COPY mcp/ /opt/qmt-mcp/

# ---- download the Windows Python installer (generic; not broker-specific) ----
RUN mkdir -p /opt/installers \
 && curl -fL --retry 3 "$PY_URL" -o /opt/installers/python-amd64.exe

# ---- pre-create wineuser (uid/gid 1000) to match runtime USER_UID/USER_GID ----
RUN groupadd --gid 1000 wineuser \
 && useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home --home-dir /home/wineuser wineuser

# ---- XFCE autostart for the MCP launcher (starts on RDP login) ----
RUN install -d -o wineuser -g wineuser /home/wineuser/.config/autostart \
 && printf '%s\n' \
      '[Desktop Entry]' \
      'Type=Application' \
      'Name=QMT MCP' \
      'Comment=Read-only QMT MCP (SSE) on login' \
      'Exec=/usr/local/bin/start-mcp.sh' \
      'Terminal=false' \
      'X-GNOME-Autostart-enabled=true' \
      > /home/wineuser/.config/autostart/qmt-mcp.desktop \
 && printf '%s\n' \
      '[Desktop Entry]' \
      'Type=Application' \
      'Name=QMT Client' \
      'Comment=Launch the broker QMT terminal on login' \
      'Exec=/usr/local/bin/start-qmt.sh' \
      'Terminal=false' \
      'X-GNOME-Autostart-enabled=true' \
      > /home/wineuser/.config/autostart/qmt-client.desktop \
 && chown -R wineuser:wineuser /opt/qmt-mcp /home/wineuser/.config /opt/installers

# ---- Wine-side provisioning as wineuser (prefix + Python + fonts + MCP deps) ----
# NOTE: no xtquant here — it is provided by the broker pack at runtime.
USER wineuser
WORKDIR /home/wineuser
RUN set -eux; \
    export HOME=/home/wineuser; \
    xvfb-run -a wineboot --init; wineserver -w; \
    xvfb-run -a wine /opt/installers/python-amd64.exe \
        /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 TargetDir="$PY_WIN_DIR"; \
    wineserver -w; \
    SITE="$WINEPREFIX/drive_c/Python312/Lib/site-packages"; \
    test -d "$SITE"; \
    xvfb-run -a wine "$PY_WIN_DIR\\python.exe" -m pip config set \
        global.index-url https://pypi.tuna.tsinghua.edu.cn/simple; \
    xvfb-run -a wine "$PY_WIN_DIR\\python.exe" -m pip install -q fastmcp uvicorn numpy pandas; \
    mkdir -p "$WINEPREFIX/drive_c/windows/Fonts"; \
    cp /usr/share/fonts/opentype/noto/*CJK*.ttc "$WINEPREFIX/drive_c/windows/Fonts/" 2>/dev/null || true; \
    cp /usr/share/fonts/truetype/wqy/*.ttc      "$WINEPREFIX/drive_c/windows/Fonts/" 2>/dev/null || true; \
    # build-time smoke: Python + MCP core (NO xtquant — comes from pack)
    xvfb-run -a wine "$PY_WIN_DIR\\python.exe" --version; \
    xvfb-run -a wine "$PY_WIN_DIR\\python.exe" -c "import fastmcp, uvicorn, numpy, pandas; print('fastmcp', fastmcp.__version__)"; \
    xvfb-run -a wine "$PY_WIN_DIR\\python.exe" -c "import sys; sys.path.insert(0, r'Z:\\opt\\qmt-mcp'); import qmt_mcp; assert qmt_mcp.filter_trade_tools() == []; print('mcp core import OK')"; \
    QMT_MCP_TOKEN=smoke QMT_MCP_ENABLE_XTDATA=0 QMT_MCP_AUDIT_PATH='C:\users\wineuser\Temp\qmt-mcp-audit-smoke.jsonl' \
      xvfb-run -a wine "$PY_WIN_DIR\\python.exe" -c "import sys; sys.path.insert(0, r'Z:\\opt\\qmt-mcp'); import qmt_mcp_core.smoke as smoke; smoke.main()"; \
    wineserver -w

USER root
WORKDIR /
EXPOSE 3389 8765
ENTRYPOINT ["/usr/local/bin/qmt-entrypoint.sh"]
