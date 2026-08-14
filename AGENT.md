# AGENT.md · AI 协作指南

给在本仓库工作的 AI Agent 的上手文档：项目地图、工作环境、构建/测试方法、以及一堆**踩过的坑**。先读这份，再动手。

## 项目本质

券商无关的 **QMT-MCP**：支持 Linux/NAS 上的 Docker + Wine appliance，也支持 Windows x64
原生桌面启动器。两种拓扑共享 MCP server 与 streamable-http 工具契约，均不分发券商终端、
`xtquant`、账号或凭据。详见 `README.md`。

## 当前状态（feature 进度）

| Feature | 状态 |
|---|---|
| 001 基础镜像 + broker pack | ✅ 完成（路径转义、client 优先级、密码、autostart 等修复）|
| 002 MCP server core | ✅ 实现+验证（`qmt_mcp_core`：鉴权/健康/审计/注册表/线程池/无写工具断言）|
| 003 行情工具 xtdata | ✅ 完成——11/11 工具真机验证（含中文板块，经 zh_CN.GBK 修复）；见 specs/003/VERIFICATION.md |
| 006 合约模糊搜索 | ✅ 完成——中文名/代码/别名/拼音首字母/板块/主题 模糊匹配 + 排序；见 specs/006/VERIFICATION.md |
| 008 CI + 测试基座 | ✅ 完成——pytest + ruff + Go test/vet/build + gitleaks + release policy |
| 009 开源就绪 | ✅ 完成——LICENSE(MIT)/SECURITY/CONTRIBUTING |
| 010 部署与安全加固 | ✅ 完成——DEPLOY.md/Caddy TLS 示例/compose.tls/harden-check.sh |
| 011 发布与版本 | ✅ 完成——main CI 后自动 SemVer、GitHub Release、GHCR/国内镜像和 6 平台 qmtctl 包 |
| 004 账户只读查询 xttrade | 🟡 只读查询族已实现（gated：flag+allowlist，readiness-gated，边界已宿主测试）；成功路径被券商权限硬卡（`m_nPythonConnectNet`），**欢迎有权限者 PR 验证** |
| 005 进程守护/就绪/autostart | ✅ 完成——supervisor/readiness/healthcheck/tmpfs guard 全部 amd64 真机验证通过 |
| 007 qmtctl CLI | ✅ 完成——Go CLI 覆盖 version/auth、行情订阅、账户/组合、期权、参考数据、板块、公式等命令族；支持静态 token 与已有 OAuth access token |
| 012 数据库持久化 PostgreSQL | ✅ 完成——asyncpg 原生异步 + sync facade；opt-in via `QMT_DB_URL`；行情仓库 bars read/write-through；graceful degradation |
| 013 行情预取/订阅缓存 | ✅ 完成——subscribe/unsubscribe/list/status 4 工具 + CLI；官方 `subscribe_quote` 优先、轮询兜底；内存热缓存 <1ms |
| 014 组合风险分析 | ✅ 完成——portfolio_summary/positions/exposure/risk_checks 4 工具（只读，依赖 xttrade 白名单）+ CLI |
| 015 期权波动率数据 | ✅ 完成——underlyings/chain/detail/quotes/iv/volatility_index_inputs 6 工具（只读，不发布指数值）+ CLI |
| 016 xtdata 参考数据 | ✅ 完成——财务/分红/新股/可转债/ETF/周期等 9 工具（只读，按运行时能力降级）+ CLI |
| 017 自定义板块管理 | ✅ 完成——文件夹及板块增删改查 7 工具（默认关闭，受管前缀沙箱）+ CLI |
| 018 公式因子运行时 | ✅ 完成——调用/批量/生成/订阅/缓存等 7 工具（默认关闭，白名单 + 输出沙箱）+ CLI |
| 019 MCP 协议基座 | ✅ 完成——官方 Python/Go SDK 与 conformance 基座；0.x 兼容策略由 029 取代 |
| 020 工具契约与 Profile | ✅ 完成——统一 output schema/structuredContent/行为注解；6 种启动 profile + glob 裁剪 |
| 021 OAuth 授权 | ✅ 完成——static/oauth/hybrid；JWT/JWKS resource server、scope 工具裁剪、qmtctl PKCE 登录/刷新 |
| 022 MCP 分页与压缩 | ✅ 完成——授权后 `tools/list` opaque cursor 分页、qmtctl 有界聚合、JSON gzip/SSE 排除 |
| 023 MCP Tasks | ✅ 完成——2026-07-28 Tasks，持久化生命周期、qmtctl 等待/脱离/现代同步路径 |
| 024 MCP 任务多轮输入 | ✅ 完成——标准 inputRequests、部分回答、MRTR→Task 组合、qmtctl 显式响应 |
| 025 MCP 任务状态通知 | ✅ 完成——2026-07-28 `subscriptions/listen` + `notifications/tasks`，qmtctl 通知优先/轮询回退 |
| 026 安全持久桌面 | ✅ 完成——xrdp 0.10 TLS-only、启动预建单会话、断线重连、loopback 默认与 manual 回滚 |
| 027 VNC 远程访问 | ✅ 完成——可保存凭据/移动端 raw VNC，复用 026 的唯一 Xorg/QMT 会话，默认关闭与 loopback |
| 028 Windows 原生启动器 | ✅ 已发布——.NET 10/Avalonia、中英文切换、DPAPI、终端探测/守护、内置 Python、ZIP/setup、Windows CI/Release；真实 QMT xtdata 已验证 |
| 029 MCP 1.0 协议基线 | ✅ 完成——仅支持 2026-07-28、无会话 Streamable HTTP；服务端/qmtctl 均拒绝 2025 fallback |
| 030 MCP K线 App | ✅ 完成——官方 Apps 扩展、单标的交互式 K线/成交量/均线、主机内刷新与全屏、文本与结构化回退 |
| 031 MCP App 故事原型 | ✅ 完成——单 HTML、Agent/App/状态分组、Codex/Claude 风格宿主会话、四个 App 页面、长页滚动与离线预览 |

每个 feature 的 `specs/<id>/` 下有 spec/plan/tasks/research/data-model/contracts。
发布镜像：`ghcr.io/juju-w/qmt-mcp`（broker 中立基础镜像，可安全公开分发）。

## 工作环境（关键）

- Docker appliance 构建/运行在**原生 amd64 Linux**（Wine 需要真 amd64）；Windows launcher
  核心/UI 可在 macOS 开发，最终打包和安装 smoke 必须在 Windows x64 CI/真机完成。
- 若用远程主机，访问信息放本地 `.env`（如 `SSH_*`）——**已 gitignore，绝不提交**。
- 在该主机上用 docker 构建/部署。本地构建 tag `qmt-appliance-base:local`，发布镜像 `ghcr.io/juju-w/qmt-mcp`；容器按实例命名（如 `qmt-<broker-id>`）。
- **Python 固定 3.12**：`xtquant` 官方最高只支持到 3.12，不要升级 Wine 内的 Python。
- **Go 固定 1.25**：qmtctl 使用官方 MCP Go SDK 1.7.x，开发、CI、发布工具链必须一致。
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
8. **持久桌面和券商登录是两层状态**：`QMT_DESKTOP_MODE=persistent` 会在容器启动时创建唯一
   Xorg/XFCE 会话并启动 QMT/MCP，RDP 重连不应更换这些 PID；但券商登录窗口仍可能等待人工操作，
   此时 `/livez` 正常而 `qmt_health.xtdata` 为 degraded。不要把 MCP 存活误报成行情 ready。
9. **VNC 是同一桌面的可选客户端协议**：启用时 x11vnc 只能附着 026 的 persistent Xorg，禁止
   新建 Xvfb/QMT/MCP。raw VNC 不加密且只使用密码前 8 个字符，默认必须 loopback + SSH/VPN；
   密码用 `tigervncpasswd -f` 从 stdin 生成临时 auth file，不能放进 argv 或 `mcp.env`。

## 安全 / 开源前必做

- 永不提交：`.env`、token、broker 二进制（终端 exe / xtquant / setup_qmt）、`*/pack/`、workspace。
  这些已在 `.gitignore`。
- **开源前脱敏**：从 tracked 文档/spec 注释里清掉真实**账户号、余额数字、主机 IP/凭据**。
- 只读默认；交易工具须显式开关 + 账户白名单 + 审计（见 constitution）。

## 开发与 CI/CD 规范

- 功能和修复从分支提交 PR，不直接向 `main` 推业务提交；合并前 CI 必须通过。
- commit subject 和 PR title 使用 Conventional Commits，例如
  `feat(cli): add command`、`fix(release): preserve cache`、`docs(skills): sync qmtctl usage`。
- `feat` 触发 minor，`!` 或 `BREAKING CHANGE:` 触发 major，其他被接受的非破坏类型触发 patch。
- 正常发布不要手改 `VERSION`、创建 tag 或手工发 Release。`main` CI 成功后自动生成 release commit，
  构建 GHCR 镜像、可选国内镜像、六平台 qmtctl 包和 Windows x64 launcher ZIP/setup。
- 合并后必须观察 `main` CI 和后续 Release 到终态；失败时修复根因并重新验证，不能只以 PR CI 通过收尾。
- Dockerfile 按依赖失效边界分层：稳定系统/Wine/Python 依赖放在频繁变化的源码前，下载与清理留在同一层。
  最新版本可更新共享 `buildcache`，历史 tag 重试只能读取，不能覆盖。
- 发布流程与缓存细节以 `docs/RELEASE.md` 为准；部署 skill 不复制开发规范。
- 永不提交 token、账户信息、broker pack、个人策略文件或本机 `.env`。

提交前至少运行：

```bash
cd appliance/mcp
ruff check .
ruff format --check .
pytest -m 'not integration'

cd ../../cli/qmtctl
go test ./...
go vet ./...
go build ./...
go build ./cmd/conformance

cd ../..
python -m unittest discover -s .github/scripts -p 'test_*.py'
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12 .github/workflows/*.yml
git diff --check

cd launcher
dotnet restore QmtMcp.Launcher.slnx --locked-mode
dotnet build QmtMcp.Launcher.slnx --configuration Release --no-restore
dotnet test QmtMcp.Launcher.slnx --configuration Release --no-build
```

## 流程

Spec-Driven（spec-kit）：`/speckit-specify → clarify → plan → tasks → implement`，一次一个 feature，
plan 必过宪章检查（`.specify/memory/constitution.md`）。范围蔓延就新开 spec，不要往进行中的 spec 里塞。

新增 MCP App 先按 [`docs/MCP-APP-PROTOTYPES.md`](docs/MCP-APP-PROTOTYPES.md)
制作一个离线单 HTML 故事原型。先判断普通文本、对话内确认还是 App；不要把每个工具结果都包装成 App。
