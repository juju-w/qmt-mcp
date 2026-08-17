# QMT-MCP

**简体中文** · [English](README.en.md)

[![CI](https://github.com/juju-w/qmt-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/juju-w/qmt-mcp/actions/workflows/ci.yml)
[![Release](https://github.com/juju-w/qmt-mcp/actions/workflows/release.yml/badge.svg)](https://github.com/juju-w/qmt-mcp/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docker image](https://img.shields.io/badge/image-ghcr.io%2Fjuju--w%2Fqmt--mcp-2496ED?logo=docker&logoColor=white)](https://github.com/juju-w/qmt-mcp/pkgs/container/qmt-mcp)
[![Stars](https://img.shields.io/github/stars/juju-w/qmt-mcp?style=social)](https://github.com/juju-w/qmt-mcp/stargazers)

**把依赖 Windows QMT 终端的 `xtquant`，变成 Agent 可以直接调用的 MCP 服务。**

QMT-MCP 提供两种运行方式：Windows x64 上使用原生桌面启动器，自动发现/启动
QMT 与 MCP；Linux/NAS 上使用 Docker + Wine 常驻多个隔离实例。Codex、Claude
Code、自建 Agent 和 `qmtctl` 都通过 Streamable HTTP MCP 获取行情和可选的账户
只读数据。

> **1.0 协议要求**：QMT-MCP 仅支持稳定版 MCP `2026-07-28`，使用无会话的
> Streamable HTTP。MCP Host 必须支持 `server/discover` 和每请求元数据。

<p align="center">
  <img src="docs/illustrations/qmt-mcp-agent-workflow.webp" width="960" alt="用户向 AI Agent 提出多个自然语言任务，Agent 通过 QMT-MCP 的 xtdata 和 xttrade 能力获取行情、研究、组合风险以及计划中的条件交易结果">
</p>
<p align="center"><sub>xtdata 场景已经可用；xttrade 账户和组合查询需要券商权限，条件交易是框架预留的计划中能力。</sub></p>

## 它解决的核心问题

- **QMT 不再绑定 Agent 所在的电脑**：可以在本机 Windows 托管，也可以常驻
  Linux/NAS/服务器；Agent 只连接一个带 token 的 `/mcp` 端点。
- **AI 不必猜证券代码**：支持中文名、代码、别名、主题和拼音首字母搜索，并可按
  相关性、流动性或规模排序候选。
- **部署可以复制和隔离**：Windows 用独立 profile，Docker 用独立 broker pack；
  公共发行包始终保持券商中立。
- **不只服务 AI**：Go 编写的单文件 `qmtctl` 同样适合人工排障、自动化脚本和 CI。

项目当前专注于**行情、研究数据和账户只读查询**，没有下单、撤单或划转工具。
账户查询还需要券商额外开通程序化交易 / 外部 Python 权限。

## 工作方式

下图是 Linux/NAS 拓扑；Windows 模式由原生 launcher 直接托管同一个 MCP server
和本机 QMT，不需要容器或 RDP。

```mermaid
flowchart LR
    U["你"]
    A["Codex / Claude Code / qmtctl"]
    B["broker pack<br/>券商终端 + xtquant"]
    subgraph C["qmt-mcp 容器 · amd64 Linux"]
        M["MCP server"]
        M --> X["xtquant"]
        X --> Q["QMT / MiniQMT"]
    end

    U -->|"RDP / VNC 登录"| Q
    A -->|"Streamable HTTP MCP + token"| M
    B --> Q
```

一次典型查询由 Agent 自动完成两步：

```text
1. qmt_xtdata_search_instruments("中证500", types=["etf"], rank_by="liquidity")
2. qmt_xtdata_snapshot(["510500.SH", "512500.SH", ...])

结果：按相关性召回真正的中证500 ETF，再结合成交额、盘口和规模给出候选与理由。
```

## 快速开始

### 从 0.x 升级到 1.0

先升级 MCP Host 和 `qmtctl`，再升级服务端。1.0 移除了 2025 协议的
`initialize` / `notifications/initialized`、`Mcp-Session-Id` 和旧 HTTP+SSE
transport；旧客户端会收到明确的 unsupported-protocol 错误，不会建立兼容会话。

### Windows x64：不用 Docker

1. 从 [Releases](https://github.com/juju-w/qmt-mcp/releases) 下载
   `qmt-mcp-launcher_<版本>_setup.exe`，或便携 ZIP。
2. 打开 QMT-MCP，在 **设置** 选择券商 QMT 的 `XtItClient.exe` / `XtMiniQmt.exe`；
   也可以先点 **自动查找客户端**。
3. 确认 `xtquant` 与 `userdata_mini` 路径，保存后点 **启动**。若 QMT 安装目录中
   没有 `xtquant`，请先在券商 QMT 客户端下载/安装 Python SDK；也可以解压券商提供的
   SDK 包，在设置中手动选择包含 `xtquant` 子目录的导入根目录。
4. 在正常弹出的券商窗口完成人工登录；状态页显示 **行情数据：已就绪** 后复制
   本地 MCP 连接。

启动器只监听 `127.0.0.1`，token 用当前 Windows 用户的 DPAPI 加密。发行包内置
Python 3.11（兼容券商提供的 `cp311` xtquant 扩展）、MCP 依赖和本项目服务端源码，但不包含券商终端、`xtquant`、账号或
登录凭据，也不会自动填写密码、验证码或交易确认。界面支持简体中文和英文，首次
启动跟随 Windows 显示语言，右上角可以即时切换并记住选择。

### Linux / NAS：Docker appliance

> 运行主机必须是**原生 amd64 Linux**。Apple Silicon 可以开发代码，但不建议生产跑 QMT/Wine。

1. 准备 broker pack

```bash
cd appliance
cp .env.example .env
scripts/make-broker-pack.sh <setup_qmt.exe> <xtquant_xxxxxx.rar> brokers/<id>/pack
```

2. 配置 `.env`

```env
BROKER_PACK=./brokers/<id>/pack
QMT_MCP_TOKEN=<change-me>
QMT_DESKTOP_MODE=persistent
QMT_RDP_PASSWORD=<at-least-12-chars>
```

3. 启动

```bash
docker compose build
docker compose up -d
```

4. 连接

```text
RDP:  127.0.0.1:13389   wineuser / QMT_RDP_PASSWORD
VNC:  127.0.0.1:15900   可选；适合移动端或可保存凭据的客户端
MCP:  http://<host>:18765/mcp
Auth: Authorization: Bearer <QMT_MCP_TOKEN>
```

远程服务器建议先 SSH 转发：

```bash
ssh -N \
  -L 13389:127.0.0.1:13389 \
  -L 15900:127.0.0.1:15900 \
  -L 18765:127.0.0.1:18765 \
  <user>@<server>
```

然后本机连接 `127.0.0.1:13389` 和 `http://127.0.0.1:18765/mcp`。

## 用 qmtctl 先试一下

`qmtctl` 是 Go 写的命令行客户端，适合人工 smoke、脚本和 CI。

```bash
cd cli/qmtctl
go build -o qmtctl .

export QMT_MCP_URL=http://127.0.0.1:18765/mcp
export QMT_MCP_TOKEN=<token>

./qmtctl health
./qmtctl search 中证500 --types etf --rank liquidity
./qmtctl snapshot 510500.SH
./qmtctl bars 510500.SH --period 1d --count 20
./qmtctl smoke
```

更多命令见 [`cli/qmtctl/README.md`](cli/qmtctl/README.md)。

## 运行中的样子

<p align="center">
  <img src="docs/screenshots/mcp-app-storyboard.png" width="960" alt="QMT-MCP 在 AI 对话宿主中的完整故事原型，包含自然语言提问、工具调用和内嵌 K 线 App">
</p>
<p align="center"><sub>从自然语言问题到工具调用、内嵌 App 和 Agent 结论。<a href="docs/prototypes/qmt-mcp-app-story.html">打开单文件交互原型</a>。</sub></p>

| 个股行情快照 | 行业板块成分 | Docker 内 QMT 终端（RDP） |
|:---:|:---:|:---:|
| <img src="docs/screenshots/snapshot-stock.png" width="250" alt="xtdata 个股行情"> | <img src="docs/screenshots/sector-board.png" width="250" alt="xtdata 行业板块"> | <img src="docs/screenshots/rdp-qmt-in-docker.png" width="250" alt="RDP 登录 Docker 内的 QMT 终端"> |

## 已实现能力

| 能力 | 状态 | 说明 |
|---|---|---|
| Windows 原生启动器 | ✅ | 无需 Docker、系统 Python 或 .NET；中英文界面、自动发现 QMT、托盘守护、DPAPI token、ZIP/setup 发布 |
| 持久 QMT 桌面 + RDP/VNC | ✅ | 启动即拉起终端 + MCP；RDP 与可选 VNC 共用单会话 |
| 行情 `xtdata` | ✅ | 快照、K线、下载历史、合约详情、板块、日历、指数权重 |
| 交互式 MCP App | ✅ | 单标的 K 线、成交量、MA5/10/20、悬浮读数、缩放、日周月切换；普通 Host 自动文本回退 |
| 合约模糊搜索 | ✅ | 中文名、代码、别名、拼音首字母、板块、主题；支持流动性排序 |
| 智能选股 / ETF 筛选 | ✅ | 严格 universe、点时因子、硬过滤、可解释百分位排名、短期结果快照 |
| 行情订阅热缓存 | ✅ | 官方 `subscribe_quote` 优先，轮询兜底 |
| 期权 / 参考数据 | ✅ | 期权链、报价、IV 输入；财务、新股、分红、可转债、ETF 参考数据 |
| qmtctl CLI | ✅ | 单文件命令行客户端，覆盖常用 MCP 工具 |
| PostgreSQL 持久化 | ✅ 可选 | 行情仓库，`QMT_DB_URL` 打开，默认关闭 |
| 账户只读查询 `xttrade` | ⚠️ 需券商权限 | 默认关闭；需要程序化交易/外部 Python 权限和账户白名单 |
| 自定义板块 / 公式因子 | ✅ 可选 | 默认关闭；受管前缀、白名单和输出沙箱 |
| MCP `2026-07-28` | ✅ 唯一版本 | 无会话 Streamable HTTP；Tasks、状态通知、多轮输入、工具分页、gzip、结构化结果 |
| OAuth 2.1 授权 | ✅ 可用 | static/oauth/hybrid；JWT/JWKS 校验、scope 裁剪、qmtctl PKCE 登录与刷新 |

## MCP 工具怎么用

推荐 Agent 遵守这个顺序：

1. 先用 `qmt_xtdata_search_instruments` 或 `qmt_xtdata_resolve_instrument`
   找合约，尤其是用户只说中文名、ETF 主题、简称或拼音首字母时。
2. 高置信候选再调用 `qmt_xtdata_snapshot`、`qmt_xtdata_bars`、
   `qmt_xtdata_kline_chart`、`qmt_xtdata_instrument_detail`。
3. 低置信或 `resolved=false` 时让用户澄清，不要编代码。

| 工具 | 说明 |
|---|---|
| `qmt_health` · `qmt_capabilities` | 健康 / 能力状态（鉴权、依赖、工具族） |
| 搜索与解析 | `qmt_xtdata_search_instruments`、`qmt_xtdata_resolve_instrument`、`qmt_xtdata_search_sectors` |
| 智能筛选 | `qmt_factor_catalog`、`qmt_screen_instruments`、`qmt_explain_screen_result` |
| 行情 | `qmt_xtdata_snapshot`、`qmt_xtdata_bars`、`qmt_xtdata_kline_chart`、`qmt_xtdata_download_history`、`qmt_xtdata_download_history_batch` |
| 合约与板块 | `qmt_xtdata_instrument_detail`、`qmt_xtdata_sector_list`、`qmt_xtdata_sector_constituents`、`qmt_xtdata_index_weight` |
| 日历 | `qmt_xtdata_trading_dates`、`qmt_xtdata_trading_calendar`、`qmt_xtdata_holidays` |
| 订阅缓存 | `qmt_xtdata_quote_subscribe`、`qmt_xtdata_quote_unsubscribe`、`qmt_xtdata_quote_subscriptions`、`qmt_xtdata_quote_subscription_status` |
| 期权与参考数据 | `qmt_xtdata_option_*`、`qmt_xtdata_financial_data`、`qmt_xtdata_ipo_info`、`qmt_xtdata_dividend_factors`、`qmt_xtdata_cb_info`、`qmt_xtdata_etf_info` |
| 账户只读（选配） | `qmt_xttrade_asset`、`qmt_xttrade_positions`、`qmt_xttrade_orders`、`qmt_xttrade_trades` 等 |
| 组合风险（选配） | `qmt_portfolio_summary`、`qmt_portfolio_positions`、`qmt_portfolio_exposure`、`qmt_portfolio_risk_checks` |
| 受管写操作（默认关闭） | 自定义板块、公式/因子输出；仅限受管前缀/白名单/沙箱 |

当前 xttrade 账户工具均为**只读**、带鉴权与审计、返回结构化 JSON。仓库没有下单、
撤单或划转工具。账户查询需 `QMT_ENABLE_XTTRADE_QUERY=1`、`QMT_TRADE_ACCOUNTS`
白名单，以及券商开通「程序化交易 / 外部 Python 接口」权限；未开通时返回
`not_authorized`，服务不崩溃。

### 智能选股与 ETF 筛选

筛选工具面向私人 QMT 实例，是只读但有短期内存状态的研究能力：先调用
`qmt_factor_catalog` 发现当前终端真实可用的 factor、窗口、单位、profile、预设和
ETF 暴露组，再由 `qmt_screen_instruments` 在一个严格可比的 universe 内过滤和排名，
最后用返回的 `screen_id` 调用 `qmt_explain_screen_result` 查看某个候选的过滤轨迹、
原始值、百分位、权重和贡献。

例如“筛选中证500 ETF，排除 20 日平均成交额低于 5000 万的产品，再按流动性和
波动率排序”。Agent 必须先解析为 `exposure=csi_500`；代码里碰巧带 `500` 的标普、
科技或生物科技 ETF 不会混入。股票和 ETF 不跨资产排名，普通公司财务因子不会用于
银行、证券或保险；财务口径按公告时间截断，比例参数用小数表示（`0.10` 即 10%）。
显式历史 `as_of` 的市值和换手率使用当时已公告的股本，缺少 `Capital` 数据时返回
missing，不会回退到当前股本。基准映射、IOPV 和 ETF 成分重合度等 P1 因子在服务端
实现与终端权限都满足前会留在目录中但标记为 unavailable。

`qmt_screen_instruments` 可由 MCP `2026-07-28` Host 作为 Task 执行。结果只保存在有
TTL、数量和 64 MiB 总预算的进程内 LRU 中，默认 15 分钟；服务重启或过期后需要重跑。
同一交易会话的日线/财务观察可短期复用，实时价差仅复用 5 秒，源错误使用更短负缓存。
它不依赖 PostgreSQL，不会自动调用历史/财务/ETF 下载工具，也不会下单。缺少本地数据
或权限时会返回具体 capability 和修复建议。当前筛选结果使用 Host 原生文字与结构化
内容；需要查看单标的走势时再调用独立的 K 线 MCP App。

```env
QMT_SCREEN_MAX_UNIVERSE_CODES=5000
QMT_SCREEN_MAX_FACTOR_REFS=24
QMT_SCREEN_MAX_RESULTS=100
QMT_SCREEN_RESULT_TTL_SECONDS=900
QMT_SCREEN_RESULT_CACHE_MAX=100
QMT_SCREEN_RESULT_CACHE_MAX_BYTES=67108864
QMT_SCREEN_FACTOR_CACHE_MAX=50000
```

### 交互式 K 线 MCP App

可以直接对 Agent 说「显示天岳先进最近 120 天的日 K」或「把 510500 的周线画出来」。
Agent 先解析标的，再调用 `qmt_xtdata_kline_chart`。声明
`io.modelcontextprotocol/ui` 的 MCP Apps Host 会在对话里显示可缩放、可悬浮查看
OHLC/成交量、可切换日周月和复权方式的图表；普通 Host、qmtctl 和脚本仍得到简短
文字摘要与完整 `structuredContent`，不会出现空白结果。

App 模板使用版本化 `ui://` 资源，全部 CSS/JavaScript/图表引擎已打进单个 HTML；
运行时不需要 Node、CDN 或额外端口，也不请求摄像头、麦克风、定位等权限。

新 App 先在完整 Agent 对话里做单文件故事原型，只有图形、比较、风险和确认等
文本难以高效表达的任务才使用 App。约定与判断表见
[`docs/MCP-APP-PROTOTYPES.md`](docs/MCP-APP-PROTOTYPES.md)。

## 安全模型

每个可见工具都发布 `title`、输入/输出 JSON Schema 和只读/破坏性/幂等/
外部访问行为注解。客户端可读取 `structuredContent`；不消费该字段的调用方仍可
读取语义相同的 JSON 文本块。业务字段不因 schema 校验被增删。

可以在 `appliance/.env` 按 Agent 用途缩小工具面：

```env
QMT_MCP_TOOL_PROFILE=market
QMT_MCP_TOOL_ALLOWLIST=qmt_xtdata_snapshot,qmt_xtdata_option_*
QMT_MCP_TOOL_DENYLIST=qmt_xtdata_download_*
```

支持 `full`、`readonly`、`market`、`account`、`core`、`custom`；`custom`
必须配置 allowlist。模式和 glob 在进程启动时固定，修改后需重启容器。OAuth
模式下它们会再与 token scope 取交集；`qmt:admin` 也不能越过启动 Profile 和
feature gate。

公网或多用户场景可切换到外部 OAuth authorization server 签发 JWT 的
`oauth`/`hybrid` 模式；QMT-MCP 只做 resource server，不保存用户密码、不签发
token。完整配置和 scope 表见 [客户端接入](docs/MCP-CLIENTS.md) 与
[部署加固](appliance/docs/DEPLOY.md)。

## 高级能力简表

### MCP Tasks

服务端以稳定版 `2026-07-28` 的 `io.modelcontextprotocol/tasks` 扩展承载下载、
财务数据、批量公式、因子生成和缓存刷新等长操作。声明该扩展的客户端可断开后
继续查询或取消任务；未声明该扩展的现代客户端仍走同步 `tools/call`。

```bash
qmtctl cache refresh --force
qmtctl --task-mode detach --json cache refresh --force
qmtctl task get tsk_<id>
qmtctl task wait tsk_<id>
qmtctl task cancel tsk_<id>
```

### 工具分页与 HTTP 压缩

`tools/list` 默认每页最多 50 个已授权工具，并用标准 opaque cursor 继续翻页。
qmtctl 会自动取完全部页面。远程 MCP JSON 响应在客户端接受 gzip 且正文足够大时
自动压缩，SSE 始终不压缩。

```env
QMT_MCP_LIST_PAGE_SIZE=50
QMT_MCP_GZIP_MIN_SIZE=1024
```

### 数据库持久化

```env
QMT_DB_URL=postgresql://user:pass@host:5432/qmt
```

默认关闭。打开后行情仓库支持 bars read/write-through；数据库不可用时优雅降级。

## 运行要求与限制

- **Windows 模式**：Windows 10 22H2 / Windows 11 x64；使用券商安装的 QMT 与匹配的 `xtquant`。
- **Docker 模式**：原生 amd64 Linux；不要在 Apple Silicon 上跑生产，QMT/Wine 可能触发模拟器或 AVX 问题。
- **Python 3.12**：`xtquant` 官方最高支持到 3.12，本项目固定 Wine 内 Python 3.12。
- **GBK 区域**：QMT 是 cp936 中文程序，镜像用 `zh_CN.GBK` 构建 Wine prefix。
- **券商权限**：行情通常只需登录 QMT；账户只读/交易连接需要券商额外开通程序化权限。
- **broker pack 自备**：仓库和镜像都不包含 QMT、xtquant、账号、token。

## 项目结构与开发

```text
appliance/   # Docker appliance：compose、Dockerfile、MCP server、broker pack 工具
cli/         # qmtctl：Go CLI，走 streamable-http MCP
launcher/    # Windows x64 原生桌面启动器、打包与安装器
docs/        # 客户端接入、发布、截图说明
skills/      # Agent 运维知识库
specs/       # spec-kit：每个 feature 的 spec/plan/tasks/verification
```

用 **Spec-Driven Development** 管理，一次一个 feature、先 spec 后实现；原则见
[`constitution.md`](.specify/memory/constitution.md)，AI 协作见 [`AGENT.md`](AGENT.md)，
测试见 [`appliance/mcp/tests/README.md`](appliance/mcp/tests/README.md)。

常用入口：

- [broker pack 制作与切换](appliance/docs/BROKER-PACK.md)
- [部署与安全加固](appliance/docs/DEPLOY.md)
- [Codex / Claude Code / WorkBuddy 接入](docs/MCP-CLIENTS.md)
- [qmtctl CLI](cli/qmtctl/README.md)
- [发布流程](docs/RELEASE.md)

## 版本与自动发布

提交和 PR 标题统一使用 `type(scope): description` 格式，例如
`feat(xtdata): add option filters`、`fix(cli): preserve session headers`。
`main` 的 CI 通过后会按 Conventional Commits 自动计算 SemVer，更新 `VERSION` 和
`CHANGELOG.md`，创建 release commit 与 tag，并发布：

- `ghcr.io/juju-w/qmt-mcp:X.Y.Z` 与 `latest`（appliance 仅 linux/amd64）
- Linux / macOS / Windows 的 qmtctl（amd64 + arm64）
- Windows x64 原生启动器 ZIP 与当前用户安装包
- `SHA256SUMS` 和 GitHub Release

镜像使用持久 BuildKit cache；普通 MCP 源码变更不会重新安装 Wine 和 Windows
Python 依赖。也可以配置阿里云 ACR 等国内仓库，CI 会复制同一个镜像 digest，
不会二次构建。详细规则、国内镜像变量和旧 tag 重试方法见
[`docs/RELEASE.md`](docs/RELEASE.md)，版本增量映射见
[`CONTRIBUTING.md`](CONTRIBUTING.md)。

## 参与贡献 / Help wanted 🙋

最需要社区帮忙的是 **04 账户查询工具（`xttrade` 只读）**：联调"成功路径"需要一个**已开通
「程序化交易 / 外部 Python 接口」权限**（`m_nPythonConnectNet`）的账户，而我自己的账户没有此权限
（达不到券商门槛），只能验证"未授权时优雅降级"。**如果你有已开通权限的账户，欢迎一起把 04 跑通并提
PR** —— 见 [`specs/004`](specs/004-account-query-tools/spec.md)。

其它方向（行情工具、部署示例、文档等）也欢迎 PR。流程见 [`CONTRIBUTING.md`](CONTRIBUTING.md)；
安全问题请按 [`SECURITY.md`](SECURITY.md) 私下报告。

## 赞助支持 ☕

业余时间开发维护，完全开源免费，但开发重度依赖 AI 编程助手（订阅费不便宜 😅）。如果项目帮到你，
欢迎请我喝杯咖啡 / 支持 AI 订阅费——也欢迎点个 ⭐ Star！🙏

| 微信 | 支付宝 |
|:---:|:---:|
| <img src="docs/sponsor/wechat.jpg" width="200" alt="微信赞赏码"> | <img src="docs/sponsor/alipay.jpg" width="200" alt="支付宝收款码"> |

## 致谢 / 许可

- 本仓库以 **MIT 许可证**发布（[`LICENSE`](LICENSE)）。
- 本项目的开发大量借助 AI 编程助手 **OpenAI GPT / Codex** 与 **Anthropic Claude（Claude Code）**
  加速完成 —— 在此致谢 🤖。
- MCP 服务为本仓库独立实现（`appliance/mcp/qmt_mcp_core` + `qmt_mcp_xtdata` + `qmt_mcp_xttrade` + `qmt_mcp_db`）。
- 基础镜像基于 [`scottyhardy/docker-wine`](https://github.com/scottyhardy/docker-wine)。
- QMT 终端、xtquant 归各券商 / 迅投所有，**不含在本仓库**，由使用者自行获取。
