# Broker-AGNOSTIC base image for the QMT-MCP appliance (feature 001).
#
# Contains ONLY the generic, broker-neutral runtime:
#   - Wine new-WoW64 on native linux/amd64
#   - Windows Python 3.12 installed into the Wine prefix
#   - CJK fonts (Linux desktop + inside the Wine prefix)
#   - official MCP SDK + uvicorn + numpy/pandas (MCP + xtdata deps)
#   - the read-only QMT MCP launcher + scripts + XFCE autostart
#   - xrdp desktop
#   - detect-broker tooling (python3 + python3-yaml)
#
# It contains NO QMT terminal, NO xtquant, NO broker data. Those are supplied at
# runtime as a read-write "broker pack" mounted at /broker; detect-broker resolves
# them on start. Switch brokers by swapping the mounted pack — never rebuild.
#
# Build MUST run on linux/amd64. Apple Silicon only works under emulation, where
# QMT native services can hit the Rosetta AVX assertion; build/run on a native
# amd64 host.
#
# Base image PINNED to a date-stamped stable tag (immutable in practice). Do NOT
# use the floating `:stable` tag — pulling a different base has produced Wine
# prefixes that fail to load a display driver (nodrv_CreateWindow). Bump this tag
# deliberately when upgrading the base (optionally append @sha256:... for a hard
# pin).
ARG WINE_BASE=docker.1ms.run/scottyhardy/docker-wine:stable-11.0-20260531
ARG XRDP_BUILD_BASE=docker.1ms.run/library/ubuntu:24.04

# Ubuntu 24.04 still packages xrdp 0.9.x. Build the current patched releases
# from the signed upstream release artifacts instead of inheriting that package.
# Keep this in a separate stage so the compiler toolchain never reaches runtime.
FROM ${XRDP_BUILD_BASE} AS xrdp-builder

ARG XRDP_VERSION=0.10.6.1
ARG XRDP_SHA256=2f7beb5a3b2529c8d72dc0df9b8cdca31ab0e0c14d1e3421210f5e6ec0ab3b75
ARG XORGXRDP_VERSION=0.10.5
ARG XORGXRDP_SHA256=a5d03435f0ef48bf3d5010e63d9264f2334e7063cba3ecd8d4c0a15616a4f712

RUN set -eux; \
    for f in /etc/apt/sources.list /etc/apt/sources.list.d/ubuntu.sources; do \
      [ -f "$f" ] && sed -i \
        -e 's|http://archive.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
        -e 's|http://security.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
        "$f" || true; \
    done; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential ca-certificates curl \
        autoconf automake libtool pkg-config nasm \
        libfuse3-dev libjpeg-dev libopus-dev libpam0g-dev libpixman-1-dev \
        libssl-dev libx11-dev libxfixes-dev libxrandr-dev xserver-xorg-dev; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    mkdir -p /build /opt/xrdp-root; \
    curl -fsSL --retry 3 \
      "https://github.com/neutrinolabs/xrdp/releases/download/v${XRDP_VERSION}/xrdp-${XRDP_VERSION}.tar.gz" \
      -o /build/xrdp.tar.gz; \
    echo "${XRDP_SHA256}  /build/xrdp.tar.gz" | sha256sum -c -; \
    tar -xzf /build/xrdp.tar.gz -C /build; \
    cd "/build/xrdp-${XRDP_VERSION}"; \
    ./configure \
      --prefix=/usr \
      --sysconfdir=/etc \
      --localstatedir=/var \
      --with-systemdsystemunitdir=/lib/systemd/system \
      --enable-fuse \
      --enable-jpeg \
      --enable-opus \
      --enable-pixman; \
    make -j"$(nproc)"; \
    make install; \
    make DESTDIR=/opt/xrdp-root install

RUN set -eux; \
    export PKG_CONFIG_PATH=/usr/lib/pkgconfig:/usr/lib/x86_64-linux-gnu/pkgconfig; \
    test "$(pkg-config --modversion xrdp)" = "$XRDP_VERSION"; \
    curl -fsSL --retry 3 \
      "https://github.com/neutrinolabs/xorgxrdp/releases/download/v${XORGXRDP_VERSION}/xorgxrdp-${XORGXRDP_VERSION}.tar.gz" \
      -o /build/xorgxrdp.tar.gz; \
    echo "${XORGXRDP_SHA256}  /build/xorgxrdp.tar.gz" | sha256sum -c -; \
    tar -xzf /build/xorgxrdp.tar.gz -C /build; \
    cd "/build/xorgxrdp-${XORGXRDP_VERSION}"; \
    ./configure --prefix=/usr --sysconfdir=/etc; \
    make -j"$(nproc)"; \
    make DESTDIR=/opt/xrdp-root install

FROM ${WINE_BASE} AS wine-runtime

# ---- pinned versions / sources (override with --build-arg) ----
ARG PY_VERSION=3.12.10
# npmmirror (taobao) mirror of python.org/ftp — fast & reliable from CN; falls
# back to python.org via --build-arg if needed.
ARG PY_URL=https://registry.npmmirror.com/-/binary/python/3.12.10/python-3.12.10-amd64.exe

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
    DEBIAN_FRONTEND=noninteractive apt-get purge -y xrdp xorgxrdp; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget git unzip ca-certificates \
        p7zip-full unrar \
        python3 python3-yaml \
        locales \
        libfuse3-3 libjpeg-turbo8 libopus0 libpixman-1-0 \
        fonts-noto-cjk fonts-wqy-microhei fonts-wqy-zenhei; \
    getent group xrdp >/dev/null || groupadd --system xrdp; \
    getent passwd xrdp >/dev/null || useradd --system --gid xrdp --home-dir /run/xrdp --shell /usr/sbin/nologin xrdp; \
    grep -qxF 'zh_CN.GBK GBK' /etc/locale.gen || echo 'zh_CN.GBK GBK' >> /etc/locale.gen; \
    locale-gen zh_CN.GBK; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

# QMT is a Chinese (GBK/cp936) application. Build the Wine prefix and run it under
# zh_CN.GBK so Wine's ANSI codepage is 936 and xtquant's Chinese data paths (e.g.
# get_sector_list, which reads GBK-encoded files) decode correctly instead of
# failing with UnicodeDecodeError/charmap. detect-broker reads broker.yaml as
# explicit UTF-8, so it is unaffected; MCP JSON over HTTP is UTF-8 regardless.
ENV LANG=zh_CN.GBK \
    LC_ALL=zh_CN.GBK

# Copy only the dependency lock before the expensive Wine provisioning.
# Application source is copied later, so ordinary MCP changes keep this layer.
COPY mcp/requirements.txt /tmp/qmt-mcp-requirements.txt

# ---- pre-create wineuser (uid/gid 1000) to match runtime USER_UID/USER_GID ----
RUN groupadd --gid 1000 wineuser \
 && useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home --home-dir /home/wineuser wineuser

# ---- XFCE autostart for the MCP launcher (starts with the desktop session) ----
RUN install -d -o wineuser -g wineuser /home/wineuser/.config/autostart \
 && printf '%s\n' \
      '[Desktop Entry]' \
      'Type=Application' \
      'Name=QMT MCP' \
      'Comment=Read-only QMT MCP (streamable-http), supervised, on login' \
      'Exec=/usr/local/bin/qmt-supervisor.sh' \
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
 && chown -R wineuser:wineuser /home/wineuser/.config

# ---- Wine-side provisioning as wineuser (prefix + Python + fonts + MCP deps) ----
# NOTE: no xtquant here — it is provided by the broker pack at runtime.
# Keep this layer independent from application source. It is the slowest layer
# and should rebuild only when the base image, Python, fonts, or requirements
# change.
USER wineuser
WORKDIR /home/wineuser
RUN set -eux; \
    export HOME=/home/wineuser; \
    curl -fL --retry 3 "$PY_URL" -o /tmp/python-amd64.exe; \
    xvfb-run -a wineboot --init; wineserver -w; \
    xvfb-run -a wine /tmp/python-amd64.exe \
        /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 TargetDir="$PY_WIN_DIR"; \
    rm -f /tmp/python-amd64.exe; \
    wineserver -w; \
    SITE="$WINEPREFIX/drive_c/Python312/Lib/site-packages"; \
    test -d "$SITE"; \
    xvfb-run -a wine "$PY_WIN_DIR\\python.exe" -m pip config set \
        global.index-url https://pypi.tuna.tsinghua.edu.cn/simple; \
    xvfb-run -a wine "$PY_WIN_DIR\\python.exe" -m pip install -q --no-cache-dir \
        --require-hashes -r 'Z:\tmp\qmt-mcp-requirements.txt'; \
    mkdir -p "$WINEPREFIX/drive_c/windows/Fonts"; \
    cp /usr/share/fonts/opentype/noto/*CJK*.ttc "$WINEPREFIX/drive_c/windows/Fonts/" 2>/dev/null || true; \
    cp /usr/share/fonts/truetype/wqy/*.ttc      "$WINEPREFIX/drive_c/windows/Fonts/" 2>/dev/null || true; \
    # Dependency smoke only. The application smoke runs after its source copy.
    xvfb-run -a wine "$PY_WIN_DIR\\python.exe" --version; \
    xvfb-run -a wine "$PY_WIN_DIR\\python.exe" -c "from importlib.metadata import version; import mcp, uvicorn, numpy, pandas; print('mcp', version('mcp'))"; \
    wineserver -k || true

# Keep the expensive Wine/Python prefix independent from xrdp and application
# changes. Future desktop security updates now rebuild only the source builder
# and these short final layers.
FROM wine-runtime AS runtime

ARG XRDP_VERSION=0.10.6.1
ARG XORGXRDP_VERSION=0.10.5

USER root

# Patched xrdp/xorgxrdp binaries and configs built above. The Ubuntu 0.9 package
# metadata is removed so scanners and later apt operations cannot mistake or
# overwrite the effective runtime. Copy explicit usr-merge-safe roots: the
# source install also stages unused systemd units under /lib, while the Wine
# base exposes /lib as a symlink to /usr/lib.
COPY --from=xrdp-builder /opt/xrdp-root/usr/ /usr/
COPY --from=xrdp-builder /opt/xrdp-root/etc/ /etc/
RUN set -eux; \
    rm -f /etc/xrdp/cert.pem /etc/xrdp/key.pem /etc/xrdp/rsakeys.ini; \
    /usr/sbin/xrdp --version | grep -F '0.10.6.1'; \
    test -x /usr/bin/xrdp-sesrun; \
    test -f /usr/lib/xorg/modules/libxorgxrdp.so; \
    install -d /usr/share/qmt; \
    printf '%s\n' "$XRDP_VERSION" > /usr/share/qmt/xrdp.version; \
    printf '%s\n' "$XORGXRDP_VERSION" > /usr/share/qmt/xorgxrdp.version

# Appliance-owned policy. Runtime setup fills the per-instance certificate and
# the explicitly selected clipboard/drive policy before xrdp starts.
COPY config/xrdp/ /etc/xrdp/

# ---- frequently changing application source ----
COPY --chmod=0755 scripts/ /usr/local/bin/

# Fail the image build itself if the patched desktop boundary regresses. This
# keeps CI from loading a multi-gigabyte Wine image merely to run the same gate.
RUN /usr/local/bin/verify-desktop-image.sh

COPY --chown=wineuser:wineuser mcp/ /opt/qmt-mcp/

# Build-time application smoke (NO xtquant — it comes from the broker pack).
# Source changes rerun only this short check, not Wine/Python provisioning.
USER wineuser
RUN set -eux; \
    export HOME=/home/wineuser; \
    xvfb-run -a wine "$PY_WIN_DIR\\python.exe" -c "import sys; sys.path.insert(0, r'Z:\\opt\\qmt-mcp'); import qmt_mcp; assert qmt_mcp.filter_trade_tools() == []; print('mcp core import OK')"; \
    QMT_MCP_TOKEN=smoke QMT_MCP_ENABLE_XTDATA=0 QMT_MCP_AUDIT_PATH='C:\users\wineuser\Temp\qmt-mcp-audit-smoke.jsonl' \
      timeout 180 xvfb-run -a wine "$PY_WIN_DIR\\python.exe" -c "import sys; sys.path.insert(0, r'Z:\\opt\\qmt-mcp'); import qmt_mcp_core.smoke as smoke; smoke.main(); import os; os._exit(0)"; \
    wineserver -k || true

USER root
WORKDIR /
EXPOSE 3389 8765

# Healthcheck (005/026): persistent mode creates the desktop at boot, so /livez
# comes up without waiting for an RDP client. Manual mode retains the historical
# behaviour and stays unhealthy until the first desktop login starts MCP.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD /usr/local/bin/healthcheck.sh

ENTRYPOINT ["/usr/local/bin/qmt-entrypoint.sh"]
