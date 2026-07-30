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
| 019 MCP 协议基座 | ✅ 完成——官方 Python/Go SDK；主推 2026-07-28，同端点兼容 2025；官方 conformance 进 CI |
| 020 工具契约与 Profile | ✅ 完成——统一 output schema/structuredContent/行为注解；6 种启动 profile + glob 裁剪 |
| 021 OAuth 授权 | ✅ 完成——static/oauth/hybrid；JWT/JWKS resource server、scope 工具裁剪、qmtctl PKCE 登录/刷新 |

每个 feature 的 `specs/<id>/` 下有 spec/plan/tasks/research/data-model/contracts。
发布镜像：`ghcr.io/juju-w/qmt-mcp`（broker 中立基础镜像，可安全公开分发）。

## 工作环境（关键）

- 开发机写代码，**构建/运行在一台原生 amd64 Linux 主机上**（Wine 需要真 amd64；可本机或远程）。
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
  构建 GHCR 镜像、可选国内镜像和 Linux/macOS/Windows × amd64/arm64 的 qmtctl 包。
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
```

## 流程

Spec-Driven（spec-kit）：`/speckit-specify → clarify → plan → tasks → implement`，一次一个 feature，
plan 必过宪章检查（`.specify/memory/constitution.md`）。范围蔓延就新开 spec，不要往进行中的 spec 里塞。
