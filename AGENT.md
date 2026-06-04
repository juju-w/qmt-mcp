# AGENT.md · AI 协作指南

给在本仓库工作的 AI Agent 的上手文档：项目地图、工作环境、构建/测试方法、以及一堆**踩过的坑**。先读这份，再动手。

## 项目本质

券商无关的 **QMT-MCP appliance**：Wine(new wow64) 在原生 amd64 上跑 Windows QMT 终端，
`xtquant` 能力经 MCP(streamable-http+token) 暴露给 Agent。基础镜像 broker 中立，券商相关的终端/xtquant/
配置作为运行时挂载的 **broker pack**（`/broker`）。详见 `README.md`。

## 当前状态（feature 进度）

| Feature | 状态 |
|---|---|
| 001 基础镜像 + broker pack | ✅ 完成（路径转义、client 优先级、密码、autostart 等修复）|
| 002 MCP server core | ✅ 实现+验证（`qmt_mcp_core`：鉴权/健康/审计/注册表/线程池/无写工具断言）|
| 003 行情工具 xtdata | ✅ 完成——11/11 工具真机验证（含中文板块，经 zh_CN.GBK 修复）；见 specs/003/VERIFICATION.md |
| 006 合约模糊搜索 | ✅ 完成——中文名/代码/别名/拼音首字母/板块/主题 模糊匹配 + 排序；见 specs/006/VERIFICATION.md |
| 008 CI + 测试基座 | ✅ 完成——宿主可跑 pytest（52 passed）+ ruff + GitHub Actions（lint/test/gitleaks）|
| 009 开源就绪 | ✅ 完成——LICENSE(MIT)/SECURITY/CONTRIBUTING |
| 010 部署与安全加固 | ✅ 完成——DEPLOY.md/Caddy TLS 示例/compose.tls/harden-check.sh |
| 011 发布与版本 | ✅ 完成——VERSION/CHANGELOG/release.yml（tag→GHCR `ghcr.io/juju-w/qmt-mcp`）|
| 004 账户只读查询 xttrade | 🟡 只读查询族已实现（gated：flag+allowlist，readiness-gated，边界已宿主测试）；成功路径被券商权限硬卡（`m_nPythonConnectNet`），**欢迎有权限者 PR 验证** |
| 005 进程守护/就绪/autostart | ⏳ 已出 plan+contracts；autostart 已落地，待系统化（supervisor/readiness/healthcheck）|
| 007 qmtctl CLI | ✅ 完成——Go 编译 CLI（health/tools/search/resolve/snapshot/bars/cache/account/smoke），release 多平台二进制 |
| 012 数据库持久化 PostgreSQL | ✅ 完成——asyncpg 原生异步 + sync facade；opt-in via `QMT_DB_URL`；行情仓库 bars read/write-through；graceful degradation |

每个 feature 的 `specs/<id>/` 下有 spec/plan/tasks/research/data-model/contracts。
发布镜像：`ghcr.io/juju-w/qmt-mcp`（broker 中立基础镜像，可安全公开分发）。

## 工作环境（关键）

- 开发机写代码，**构建/运行在一台原生 amd64 Linux 主机上**（Wine 需要真 amd64；可本机或远程）。
- 若用远程主机，访问信息放本地 `.env`（如 `SSH_*`）——**已 gitignore，绝不提交**。
- 在该主机上用 docker 构建/部署。本地构建 tag `qmt-appliance-base:local`，发布镜像 `ghcr.io/juju-w/qmt-mcp`；容器按实例命名（如 `qmt-<broker-id>`）。
- **Python 固定 3.12**：`xtquant` 官方最高只支持到 3.12，不要升级 Wine 内的 Python。
- **free-threading（无 GIL）已调研、不采用**：无 GIL 是 3.13t/3.14t（不是 3.12）；导入未标记 FT 安全的 C 扩展会让解释器**自动重开 GIL**，而 `xtquant` 是专有编译扩展、不可能标 FT 安全 → 零收益且未测有风险；况且本服务是 I/O 密集（HTTP/asyncpg/共享内存），GIL 非瓶颈。结论：保持 3.12 + GIL。

## 构建 / 部署 / 测试

```bash
# 构建（在 amd64 主机上，build 目录放持久盘）
docker build -t qmt-appliance-base:local <build-dir>
# 部署
docker compose --env-file inst-<id>.env -p qmt-<id> up -d --force-recreate
```

**测 MCP 行情工具（in-process，最可靠）**：用真实 config 构建 core，直接调注册表里的 callable，
绕开 HTTP/鉴权，对 live xtdata 验证结构化输出：

```python
import sys, os; sys.path.insert(0, r'Z:\opt\qmt-mcp'); sys.path.insert(0, os.environ['QMT_XTQUANT_DIR_WIN'])
from qmt_mcp_core.config import CoreConfig
from qmt_mcp_core.app import create_app
cfg = CoreConfig(..., enable_xtdata=True, test_mode=True, allow_unauth_loopback=True)
_,_,health,registry = create_app(cfg)
registry._tools['qmt_xtdata_snapshot']['callable'](codes=['000001.SZ'])
```

在 Wine python 里跑：`wine /home/wineuser/.wine/drive_c/Python312/python.exe -u script.py`
（QMT 需已登录；行情走共享内存）。

## 踩过的坑（务必遵守）

1. **base 镜像钉到日期版 stable tag**（如 `scottyhardy/docker-wine:stable-11.0-20260531`，实际上不可变）。
   **不要**用浮动的 `:stable`——拉到不同 base 会产出**加载不出显示驱动**的 wine prefix
   （`nodrv_CreateWindow`）。升级 base 要显式改 tag（可再 `@sha256:` 硬钉）。
2. **wine prefix 显示驱动**：base 钉了 digest 后，烤进镜像的 prefix 开机即健康，start-qmt.sh
   **不再做** `wineboot -u` 运行时自愈（旧自愈会卡在 `wineserver -w`，已于 771cbc7 移除）。
   万一某次 prefix 坏了（`nodrv_CreateWindow`），手动 `wineboot -u` 修复，**切勿**再加 `wineserver -w`。
3. **resolved env 值必须单引号**。Wine 路径含反斜杠（`Z:\broker\...`），`detect-broker` 写
   `/run/qmt/broker.env`、entrypoint 折叠进 `/opt/qmt-mcp/mcp.env` 时若不加单引号，bash
   `source` 会把反斜杠吃掉 → wine 打不开文件。启动客户端用 **unix 路径**（wine 接受）最稳。
4. **GBK/cp936**：QMT 是中文 GBK 程序。镜像用 `LANG=zh_CN.GBK` 建 prefix，否则 `get_sector_list`
   等读中文文件的路径会 UnicodeDecode/charmap 崩。`detect-broker` 读 broker.yaml 显式用 utf-8，不受影响。
5. **docker exec 复杂命令用脚本文件**（scp 上去再 `bash file.sh`），别在 `ssh "... sudo bash -c '...'"`
   里塞多层引号/括号/heredoc——会被层层 shell 吃掉。heredoc 喂 `docker exec` 要加 `-i`。
6. **交易权限**：`xttrader.connect()==-1` 多半是账户没开 `m_nPythonConnectNet/程序化交易`
   （券商后台授权），不是代码问题。账户余额可从 mini 日志 `push accountdetail` 读到（非 API）。
7. **client 探测优先级**：真实 QMT 树里 `bin.x64` 同时有 `XtItClient.exe`(投研版) 和
   `XtMiniQmt.exe`。投研版 + 独立交易会拉起 `XtMiniQmt linkMini`。detect-broker 按优先级选
   `XtItClient.exe`；独立的 `XtMiniQmt.exe` 直接启在 wine 下不一定稳。

## 安全 / 开源前必做

- 永不提交：`.env`、token、broker 二进制（终端 exe / xtquant / setup_qmt）、`*/pack/`、workspace。
  这些已在 `.gitignore`。
- **开源前脱敏**：从 tracked 文档/spec 注释里清掉真实**账户号、余额数字、主机 IP/凭据**。
- 只读默认；交易工具须显式开关 + 账户白名单 + 审计（见 constitution）。

## 流程

Spec-Driven（spec-kit）：`/speckit-specify → clarify → plan → tasks → implement`，一次一个 feature，
plan 必过宪章检查（`.specify/memory/constitution.md`）。范围蔓延就新开 spec，不要往进行中的 spec 里塞。
