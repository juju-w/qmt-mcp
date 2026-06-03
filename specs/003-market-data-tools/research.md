# Research: xtdata Tool Catalog

**Feature**: 003-market-data-tools
**Date**: 2026-06-03

## Sources Reviewed

- 迅投知识库 - XtQuant.XtData 行情模块: https://dict.thinktrader.net/nativeApi/xtdata.html
- 迅投知识库 - XtQuant 快速开始: https://dict.thinktrader.net/nativeApi/start_now.html

## Decisions

### Decision: Make history download explicit

Expose a separate `qmt_xtdata_download_history` tool instead of hiding downloads
inside bar reads.

**Rationale**: Official xtdata behavior distinguishes data download/cache
population from read APIs. Hidden downloads would make read calls unexpectedly
slow and hard to audit.

### Decision: Use bounded request shapes

Every tool must enforce max code count, date span, row count, and output-size
limits before calling xtdata.

**Rationale**: Xtdata can return pandas/numpy-heavy objects and large history
ranges. MCP responses must remain JSON-clean and bounded.

### Decision: Defer streaming subscriptions

Do not expose `subscribe_quote`, `subscribe_whole_quote`, or `run()` in this
feature.

**Rationale**: Official subscription APIs are callback/lifecycle oriented. MCP
streaming needs a separate design for sessions, unsubscribe, backpressure, and
resource cleanup.

### Decision: Treat Level2/投研特色 data as optional

Do not include Level2 or specialty data in the required MVP.

**Rationale**: These may require separate entitlement, product version, or data
permissions. The first tool family should work in a basic xtdata environment.
