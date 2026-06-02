# Self-contained QMT/MiniQMT image on Wine (new WoW64), native linux/amd64.
#
# Everything is baked at build time on a native amd64 host (the x86 NAS):
#   - CJK fonts (Linux side + inside the Wine prefix)
#   - Windows Python 3.12 installed into the Wine prefix
#   - xtquant (vendor build) placed into site-packages
#   - 金阳光/QMT (NSIS) extracted under /workspace/QMT/extracted
#
# Build MUST run on linux/amd64. On Apple Silicon this only works under
# emulation and the QMT native services may crash (Rosetta AVX assertion);
# build and run on the x86 NAS instead.
FROM docker.1ms.run/scottyhardy/docker-wine:stable

# ---- versions / sources (override with --build-arg) ----
ARG PY_VERSION=3.12.10
ARG PY_URL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
ARG XTQUANT_URL=https://dict.thinktrader.net/packages/xtquant_250807.rar
ARG QMT_SETUP_URL=https://downloadspeed.ebscn.com/zyrj/qmt/setup_qmt.exe

# C:\Python312 — keep in sync with the 3.12 PY_VERSION above
ENV WINEARCH=wow64 \
    WINEPREFIX=/home/wineuser/.wine \
    WINEDEBUG=-all \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PY_WIN_DIR=C:\\Python312

# ---- system packages: CJK fonts, archive tools, utilities ----
# Use the Aliyun mirror for the Ubuntu archive (noble uses deb822 .sources).
# unrar (RARLAB) is required: the xtquant archive is RAR v5 with a compression
# method that the container's old p7zip cannot decode. 7z is kept for the
# NSIS QMT installer.
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
        fonts-noto-cjk fonts-wqy-microhei fonts-wqy-zenhei; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

# ---- helper scripts ----
COPY scripts/ /usr/local/bin/
RUN chmod +x /usr/local/bin/*.sh

# ---- download installers/artifacts (small build context, reproducible) ----
RUN mkdir -p /opt/installers /workspace/QMT /workspace/python /workspace/app \
 && echo "Downloading Windows Python ${PY_VERSION}..." \
 && curl -fL --retry 3 "$PY_URL"        -o /opt/installers/python-amd64.exe \
 && echo "Downloading xtquant..." \
 && curl -fL --retry 3 "$XTQUANT_URL"   -o /opt/installers/xtquant.rar \
 && echo "Downloading 金阳光/QMT setup..." \
 && curl -fL --retry 3 "$QMT_SETUP_URL" -o /opt/installers/setup_qmt.exe

# ---- extract 金阳光/QMT (NSIS) into /workspace/QMT/extracted ----
RUN 7z x -y /opt/installers/setup_qmt.exe -o/workspace/QMT/extracted >/dev/null \
 && test -f /workspace/QMT/extracted/bin.x64/XtItClient.exe \
 && echo "QMT extracted: $(du -sh /workspace/QMT/extracted | cut -f1)"

# ---- extract xtquant vendor package into /workspace/python ----
# RAR v5: use RARLAB unrar (container p7zip is too old for this method).
RUN unrar x -y /opt/installers/xtquant.rar /workspace/python/ \
 && XTQ_PKG="$(find /workspace/python -maxdepth 3 -type d -name xtquant | head -1)" \
 && test -n "$XTQ_PKG" \
 && echo "xtquant package: $XTQ_PKG"

# ---- pre-create wineuser (uid/gid 1000) to match runtime USER_UID/USER_GID ----
# The base entrypoint creates this user at *runtime*; we create it here with the
# same ids so build-time provisioning lands in a 1000:1000-owned home. The
# entrypoint's user-creation is idempotent and its home-ownership check then
# passes (1000:1000 == USER_UID:USER_GID), so the baked prefix is not clobbered.
# Keep docker-compose USER_UID/USER_GID at 1000 for this to hold.
RUN groupadd --gid 1000 wineuser \
 && useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home --home-dir /home/wineuser wineuser

RUN chown -R wineuser:wineuser /workspace /opt/installers

# ---- read-only QMT MCP: vendored servers + launcher + XFCE autostart ----
COPY mcp/ /opt/qmt-mcp/
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
 && chown -R wineuser:wineuser /opt/qmt-mcp /home/wineuser/.config

# ---- Wine-side provisioning as wineuser (prefix + Python + xtquant + fonts) ----
USER wineuser
WORKDIR /home/wineuser
RUN set -eux; \
    export HOME=/home/wineuser; \
    # initialise the new WoW64 prefix
    xvfb-run -a wineboot --init; wineserver -w; \
    # install Windows Python 3.12 into the prefix (same /quiet flags proven to work)
    xvfb-run -a wine /opt/installers/python-amd64.exe \
        /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 TargetDir="$PY_WIN_DIR"; \
    wineserver -w; \
    SITE="$WINEPREFIX/drive_c/Python312/Lib/site-packages"; \
    test -d "$SITE"; \
    # point pip at a domestic mirror (Tsinghua) for future installs
    xvfb-run -a wine "$PY_WIN_DIR\\python.exe" -m pip config set \
        global.index-url https://pypi.tuna.tsinghua.edu.cn/simple; \
    # MCP server deps (read-only QMT MCP launcher)
    xvfb-run -a wine "$PY_WIN_DIR\\python.exe" -m pip install -q fastmcp uvicorn; \
    # place xtquant into site-packages (all cp3x pyds shipped; Py3.12 picks cp312)
    XTQ_PKG="$(find /workspace/python -maxdepth 3 -type d -name xtquant | head -1)"; \
    cp -r "$XTQ_PKG" "$SITE/"; \
    # drop CJK fonts into the Wine Fonts dir so QMT renders Chinese
    mkdir -p "$WINEPREFIX/drive_c/windows/Fonts"; \
    cp /usr/share/fonts/opentype/noto/*CJK*.ttc "$WINEPREFIX/drive_c/windows/Fonts/" 2>/dev/null || true; \
    cp /usr/share/fonts/truetype/wqy/*.ttc      "$WINEPREFIX/drive_c/windows/Fonts/" 2>/dev/null || true; \
    # smoke tests
    xvfb-run -a wine "$PY_WIN_DIR\\python.exe" --version; \
    xvfb-run -a wine "$PY_WIN_DIR\\python.exe" -c "import xtquant, xtquant.xtdata; print('xtquant OK')"; \
    # MCP smoke test: vendored modules import + read-only filter applies (no QMT needed)
    xvfb-run -a wine "$PY_WIN_DIR\\python.exe" -c "import sys; sys.path.insert(0, r'Z:\\opt\\qmt-mcp'); import qmt_mcp; qmt_mcp.filter_trade_tools(); print('mcp filter OK')"; \
    wineserver -w

USER root
WORKDIR /workspace
EXPOSE 3389 8765
ENTRYPOINT ["/usr/local/bin/qmt-entrypoint.sh"]
