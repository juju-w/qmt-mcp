# Research: Official XtQuant APIs And MCP Tool Shape

**Feature**: 002-mcp-server-core
**Date**: 2026-06-03

## Sources Reviewed

- 迅投知识库 - XtQuant 快速开始: https://dict.thinktrader.net/nativeApi/start_now.html
- 迅投知识库 - XtQuant.XtData 行情模块: https://dict.thinktrader.net/nativeApi/xtdata.html
- 迅投知识库 - XtQuant.Xttrade 交易模块: https://dict.thinktrader.net/nativeApi/xttrader.html

## Decisions

### Decision: MCP is capability-gated, not package-pass-through

The MCP server core exposes a small allow-listed set of tool contracts. It MUST
never mount every function from `xtdata` or `xttrader` just because the package
imports successfully.

**Rationale**: Official XtQuant modules contain a broad surface: synchronous data
fetches, callback subscriptions, downloads, formula/model calls, account queries,
orders, cancels, fund transfers, and other broker-specific functions. An agent
needs stable, safe tools, not raw SDK access.

**Alternatives considered**:
- Mount vendored MCP tools wholesale: rejected because it leaks accidental tools,
  exposes inconsistent schemas, and makes read-only safety brittle.
- One generic `call_xtquant(function, args)` tool: rejected because it bypasses
  validation, audit semantics, and capability gating.

### Decision: 002 defines the framework; 003 owns the xtdata tool catalog

Feature 002 owns authentication, audit, health shape, worker execution, uniform
errors, and the tool contract format. The first real tool family should be
feature 003: `xtdata`, because the current environment appears to have market
data access while `xttrade` account/trading permission is not enabled.

**Rationale**: The official docs describe `xtdata` as the行情 module for
historical/realtime K-line, tick, financial, instrument, sector, industry, and
calendar data. It is useful without account-level trading permission. `xttrade`
requires a successful MiniQMT trader connection and account permissions; in the
current environment it should remain blocked/disabled.

**Alternatives considered**:
- Put all tools in 002: rejected because 002 becomes too wide and mixes service
  infrastructure with business API design.
- Implement `xttrade` read-only queries before `xtdata`: deferred because local
  successful-path validation is not possible yet. The feature remains planned as
  004 for permissioned deployments.

### Decision: Start with request/response tools, defer streaming subscriptions

The xtdata MCP catalog should prioritize synchronous request/response tools:
snapshot, local/historical bars, data download, instrument detail, sectors,
calendars, finance, IPO/CB/ETF metadata.

**Rationale**: Official xtdata subscription APIs use callbacks and `run()` blocks
the current thread to keep callbacks alive. MCP transports can carry server
events, but turning market subscriptions into a durable stream requires session
ownership, backpressure, unsubscribe semantics, and resource limits. That is a
separate feature.

**Alternatives considered**:
- Expose `subscribe_quote` immediately: deferred because long-running callbacks
  require lifecycle design.
- Poll `get_full_tick` as a pseudo-stream: acceptable later as a bounded helper,
  but not part of the first xtdata tool set.

### Decision: Health reports capability state separately for xtdata and xttrade

The health contract should expose at least:

- `server`: live/degraded
- `broker_config`: loaded/error
- `xtquant_import`: ok/error
- `xtdata`: available/not-ready/error
- `xttrade`: disabled/not-authorized/not-ready/connected/error
- `tool_families`: enabled/disabled reason per family

**Rationale**: The operator needs to see that xtdata works while xttrade is not
authorized, instead of treating the whole MCP as failed.

**Alternatives considered**:
- One `qmt_ready` boolean: rejected because it hides the important distinction
  between market-data readiness and trader/account permission.

### Decision: Account-query tools are planned, opt-in, and locally untestable until permission is available

Feature 004 should implement read-only account-query contracts for users who
have broker permission, but the default runtime behavior remains no xttrade tools
registered unless the operator explicitly enables the family, configures an
account allow-list, and the connector proves authorization.

**Rationale**: Official xttrade includes both read-only queries and write-capable
operations. Even read-only queries depend on `XtQuantTrader(path, session_id)`,
`connect()`, and a `StockAccount`. The current broker account reportedly lacks
the required permission, so local validation can only prove not-authorized and
disabled behavior. The feature is still important for permissioned users and
should remain on the roadmap.

**Alternatives considered**:
- Register query tools unconditionally and let them fail: rejected; agents should
  see disabled/not-authorized capability state unless the operator opted in.

### Decision: Do not require Postgres for the 002/003 MVP

The MCP core stores audit records in append-only JSONL by default. Postgres is a
future optional persistence backend for long-term audit search, task state, and
market-data warehousing, but it is not required for the 002 core or 003 xtdata
MVP.

**Rationale**: The most important near-term risk is the QMT/Wine/xtdata/MCP
runtime chain. Making Postgres mandatory would add migrations, backup, health,
networking, credentials, pooling, and deployment complexity before the first
market-data tools are proven. xtdata already maintains its own local cache, so
duplicating historical data into a database should be a separate data-warehouse
feature.

**Alternatives considered**:
- Mandatory Postgres from 002: rejected because it widens the core feature and
  slows down validation of the broker/runtime integration.
- No persistence at all: rejected because trading-adjacent MCP calls need an
  audit trail from the first production-ish version.

## MCP Tool Design Principles

- Use domain tools, not SDK wrappers.
- Validate stock codes as `code.market` or market codes only where the tool
  explicitly permits market-wide input.
- Use bounded enums for period, dividend type, market, account type, and output
  format.
- Return JSON-clean structured models; never return pandas/numpy/SDK objects.
- Separate download/cache-population tools from read tools, because official
  docs state historical reads may require prior data download.
- Put all blocking SDK calls through the 002 worker executor.
- Audit every accepted call, including disabled-capability refusals.
- Keep persistence pluggable: JSONL first, optional database later.

## Proposed Feature Split

- **002 MCP Server Core**: auth, health shape, audit, errors, worker pool, tool
  registration framework, capability gating.
- **003 Market-Data Tools**: xtdata request/response tools, enabled first.
- **004 Account-Query Tools**: xttrade read-only queries, opt-in and enabled for
  permissioned accounts; locally validated as disabled/not-authorized until a
  permissioned account is available.
- **005 Supervision/Readiness**: autostart, process supervision, xtdata/trader
  readiness probes and reconnection.
- **006+ Persistence/Observability**: optional Postgres audit/query store,
  market-data warehouse, dashboards, and longer-term retention policies.
