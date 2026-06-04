# qmt-mcp · Run QMT in Docker, plug it into AI agents over MCP

🌐 [简体中文](README.md) · **English**

[![CI](https://github.com/juju-w/qmt-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/juju-w/qmt-mcp/actions/workflows/ci.yml)
[![Release](https://github.com/juju-w/qmt-mcp/actions/workflows/release.yml/badge.svg)](https://github.com/juju-w/qmt-mcp/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white)](#)
[![image: ghcr.io/juju-w/qmt-mcp](https://img.shields.io/badge/image-ghcr.io%2Fjuju--w%2Fqmt--mcp-2496ED?logo=docker&logoColor=white)](https://github.com/juju-w/qmt-mcp/pkgs/container/qmt-mcp)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Stars](https://img.shields.io/github/stars/juju-w/qmt-mcp?style=social)](https://github.com/juju-w/qmt-mcp/stargazers)

Run the Windows **QMT / MiniQMT terminal** under Wine **inside a Docker container**
and expose its China A-share market-data and account capabilities to AI agents
over **MCP (Model Context Protocol)**. `docker compose up` one container, mount a
broker pack, and you're live.

> **Core idea**: the base image is **broker-agnostic** — switch brokers by swapping
> a mounted **broker pack**, never by rebuilding. One host can run several brokers
> in parallel.

```text
immutable base image  ghcr.io/juju-w/qmt-mcp           mounted at runtime
(Wine wow64 + Win Python 3.12 + MCP + xrdp)  ◄── broker pack → /broker
— broker-neutral, ships NO terminal/xtquant/account data   (QMT terminal + xtquant + broker.yaml)
```

## Screenshots

**✨ Fuzzy instrument search (the highlight)** — an AI agent asks in plain language
("the best CSI 500 ETF") and MCP returns ranked candidates by liquidity; the agent
never needs to know the raw QMT code:

<p align="center">
  <img src="docs/screenshots/fuzzy-search-etf.png" width="680" alt="AI agent fuzzy-searching ETFs via MCP">
</p>

| Stock snapshot | Sector board | QMT terminal in Docker (RDP) |
|:---:|:---:|:---:|
| <img src="docs/screenshots/snapshot-stock.png" width="250" alt="xtdata stock snapshot"> | <img src="docs/screenshots/sector-board.png" width="250" alt="xtdata sector board"> | <img src="docs/screenshots/rdp-qmt-in-docker.png" width="250" alt="RDP into the QMT terminal running in Docker"> |

## Status

| Capability | State | Notes |
|---|---|---|
| Launch QMT terminal + RDP login | ✅ | terminal + MCP auto-start after login |
| Market data `xtdata` (snapshot/bars/instruments/sectors/calendar) | ✅ ready | MCP tools return structured JSON (11/11 verified live) |
| **Fuzzy instrument search** (name/pinyin/alias/sector/theme) | ✅ ready | the agent locates instruments without knowing QMT codes |
| Read-only account queries `xttrade` | ⚠️ needs broker permission | degrades to `not_authorized` (no crash) when not enabled |
| Database persistence (PostgreSQL, optional) | ✅ ready | market-data warehouse, read/write-through, off by default |
| `qmtctl` CLI | ✅ ready | compiled Go CLI client for health/search/quotes/account queries |

> **Trading/account permission**: connecting `xtquant` to the trading interface
> (orders **and** account queries) requires the broker to enable "programmatic
> trading / external Python API" permission (`m_nPythonConnectNet`). Without it,
> only market data works. Enabling usually needs an asset threshold + a signed
> agreement — contact your broker.

## MCP tools

✨ **Highlight: fuzzy instrument search** — the agent doesn't need the QMT code up
front; it searches by Chinese name / pinyin initials / alias / sector / theme
(e.g. `天岳`, `ZGWX`, `恒生科技`, `纳指`), resolves a code, then fetches quotes.

| Tool | What it does |
|---|---|
| `qmt_health` · `qmt_capabilities` | health / capability state (auth, deps, tool families) |
| `qmt_xtdata_search_instruments` ✨ | **fuzzy-search** instruments by name/code/alias/pinyin/sector/theme, ranked by relevance + liquidity |
| `qmt_xtdata_resolve_instrument` ✨ | **resolve** a phrase to the best code + alternates (`resolved=false` when low-confidence) |
| `qmt_xtdata_search_sectors` | fuzzy-search sector names |
| `qmt_xtdata_instrument_detail` | metadata for one instrument |
| `qmt_xtdata_snapshot` | real-time snapshot (last price / bid-ask / …) |
| `qmt_xtdata_bars` | OHLC bars (tick / minute / day / week / month…) |
| `qmt_xtdata_sector_list` · `qmt_xtdata_sector_constituents` | sector list / constituents |
| `qmt_xtdata_index_weight` | index weights |
| `qmt_xtdata_trading_dates` · `qmt_xtdata_trading_calendar` · `qmt_xtdata_holidays` | trading calendar |
| `qmt_xtdata_download_history` · `_batch` | download history to local cache |
| `qmt_xtdata_instrument_cache_status` · `qmt_xtdata_refresh_instrument_cache` | search-cache status / refresh |
| `qmt_xtdata_quote_subscribe` · `qmt_xtdata_quote_unsubscribe` · `qmt_xtdata_quote_subscriptions` · `qmt_xtdata_quote_subscription_status` | quote subscription hot cache (`subscribe_quote` first, bounded polling fallback) |
| `qmt_xtdata_option_chain` · `qmt_xtdata_option_quotes` · `qmt_xtdata_option_iv` · `qmt_xtdata_volatility_index_inputs` | option chains, call/put quotes, IV, and VIX input packages (read-only; no index publishing) |
| `qmt_xtdata_financial_data` · `qmt_xtdata_ipo_info` · `qmt_xtdata_dividend_factors` · `qmt_xtdata_cb_info` · `qmt_xtdata_etf_info` | financial/IPO/dividend/CB/ETF reference data (read-only, capability-gated) |
| `qmt_portfolio_summary` · `qmt_portfolio_positions` · `qmt_portfolio_exposure` · `qmt_portfolio_risk_checks` | portfolio holdings/exposure/risk metrics (read-only, xttrade allowlist required) |
| `qmt_xtdata_sector_create` · `qmt_xtdata_sector_add_codes` · `qmt_xtdata_sector_remove_codes` · `qmt_xtdata_managed_sector_list` | custom sector management (off by default; managed prefixes only) |
| `qmt_xtdata_formula_call` · `qmt_xtdata_formula_call_batch` · `qmt_xtdata_formula_generate_factor` · `qmt_xtdata_formula_subscribe` | formula/factor runtime (off by default; server allowlist + output sandbox) |
| Account read-only `xttrade` (04, **opt-in**) | see table below, off by default |

**xttrade account-query tools** (require `QMT_ENABLE_XTTRADE_QUERY=1` + account allowlist):

| Tool | What it does |
|---|---|
| `qmt_xttrade_asset` | cash/total/market-value/frozen asset snapshot |
| `qmt_xttrade_positions` | holdings (code, volume, can-use/frozen/yesterday/on-road, open/avg price, market value) |
| `qmt_xttrade_orders` | today's orders (with `cancelable_only` filter) |
| `qmt_xttrade_trades` | today's fills (code, price, volume, amount, time, order id) |
| `qmt_xttrade_position_statistics` | aggregate position statistics |
| `qmt_xttrade_account_status` | trading account status |
| `qmt_xttrade_new_purchase_limit` | new-share (IPO) purchase limits |
| `qmt_xttrade_ipo_data` | today's IPO/new-issue data (not account-scoped) |

All tools are **read-only**, authenticated, audited, and return structured JSON
(no write/order/cancel/transfer tools).

> **Account queries (feature 04)** are off by default; enable with
> `QMT_ENABLE_XTTRADE_QUERY=1` **and** an account allowlist `QMT_TRADE_ACCOUNTS`,
> and the broker must have granted programmatic-trading permission for the success
> paths (otherwise `not_authorized`, gracefully). **Strictly read-only, no order/cancel/transfer**.
> Success paths await a permissioned account (PRs welcome).

## Quick start

> Must build & run on a **native amd64 host** (Apple Silicon is emulation-only and
> QMT may hit the Rosetta AVX assertion).

```bash
cd appliance
cp .env.example .env                       # fill in QMT_MCP_TOKEN / BROKER_PACK / ...
docker compose build                       # build the broker-neutral base image
scripts/make-broker-pack.sh <setup_qmt.exe> <xtquant_xxxxxx.rar> brokers/<id>/pack
docker compose up -d
```

Connect (after RDP login, log into your account in QMT; trading needs the
**independent-trading / minimal** mode):

```text
RDP:  <host>:13389   wineuser / password in .env  (use a real RDP client, not VNC)
MCP:  http://<host>:18765/mcp   with Authorization: Bearer <QMT_MCP_TOKEN>
```

You can also use the **qmtctl** CLI from the command line (see [`cli/qmtctl/README.md`](cli/qmtctl/README.md)):

```bash
cd cli/qmtctl && go build -o qmtctl .
export QMT_MCP_URL=http://<host>:18765/mcp QMT_MCP_TOKEN=<token>
./qmtctl health                       # health check
./qmtctl search 纳指                   # fuzzy instrument search
./qmtctl snapshot 510300.SH           # real-time quote snapshot
./qmtctl bars 510300.SH --period 1d   # OHLC bars
./qmtctl subscription add --id s1 510300.SH,510500.SH  # quote subscription
./qmtctl portfolio summary --account <id>              # portfolio summary
./qmtctl option chain --family 300ETF                  # option chain
./qmtctl ref financial 600000.SH --tables Income       # reference data
./qmtctl account asset --account <id> # account asset (requires xttrade enabled)
```

More: [broker pack guide](appliance/docs/BROKER-PACK.md) ·
[deploy & hardening](appliance/docs/DEPLOY.md)

## Requirements

- **Native amd64** — don't run production on Apple Silicon (emulation may trigger
  the Rosetta AVX crash).
- **GBK locale** — QMT is a cp936 Chinese program; the image builds the Wine prefix
  with `zh_CN.GBK`.

## Layout & development

```text
appliance/   # deployable appliance: Dockerfile · compose · scripts · mcp/ · brokers/ · docs/
cli/         # qmtctl: compiled Go CLI client (streamable-http MCP)
skills/      # AI agent ops knowledge base (deploy/MCP/CLI/troubleshooting)
specs/       # Spec-Driven Development (spec-kit): 001~018 spec/plan/tasks
```

Managed with **Spec-Driven Development**, one feature at a time, spec before code.
Principles in [`constitution.md`](.specify/memory/constitution.md); AI-agent map in
[`AGENT.md`](AGENT.md); tests in
[`appliance/mcp/tests/README.md`](appliance/mcp/tests/README.md).

## Contributing / Help wanted 🙋

The biggest ask is **feature 04 (read-only account queries via `xttrade`)**:
validating the success paths needs an account with **"programmatic trading /
external Python API" permission** (`m_nPythonConnectNet`), which the maintainer
does not have (below the broker's threshold) — so only the "graceful
not-authorized" path can be tested locally. **If you have a permissioned account,
PRs that help get 04 working are very welcome** — see
[`specs/004`](specs/004-account-query-tools/spec.md).

Other contributions (market-data tools, deployment examples, docs) are welcome
too. See [`CONTRIBUTING.md`](CONTRIBUTING.md); report security issues privately per
[`SECURITY.md`](SECURITY.md).

## Sponsor ☕

Built and maintained in my spare time, fully open-source and free — but it leans
heavily on AI coding assistants (subscriptions aren't cheap 😅). If it helped you,
a coffee toward the AI-subscription cost is hugely appreciated — and a ⭐ Star helps
too! 🙏

| WeChat | Alipay |
|:---:|:---:|
| <img src="docs/sponsor/wechat.jpg" width="200" alt="WeChat donation"> | <img src="docs/sponsor/alipay.jpg" width="200" alt="Alipay donation"> |

## Acknowledgements / License

- Released under the **MIT License** ([`LICENSE`](LICENSE)).
- Development was greatly accelerated by the AI coding assistants **OpenAI GPT /
  Codex** and **Anthropic Claude (Claude Code)** — thank you 🤖.
- The MCP server is an independent implementation in this repo
  (`appliance/mcp/qmt_mcp_core` + `qmt_mcp_xtdata` + `qmt_mcp_xttrade` + `qmt_mcp_db`).
- Base image built on [`scottyhardy/docker-wine`](https://github.com/scottyhardy/docker-wine).
- The QMT terminal and `xtquant` belong to the respective brokers / Thinktrader and
  are **not included in this repo** — obtain them yourself.
