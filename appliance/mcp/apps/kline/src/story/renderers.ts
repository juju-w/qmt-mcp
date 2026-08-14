import { successFixture } from "../fixtures";
import { formatCompact } from "../model";
import { rankEtfs, type EtfCandidate, type EtfRank } from "./model";
import type { StoryLocale, StoryRenderer } from "./types";

export interface SceneUiState {
  searchSelection: string;
  searchExpanded: boolean;
  searchConfirmed: boolean;
  klinePeriod: "1d" | "1w" | "1mon";
  etfRank: EtfRank;
  portfolioView: "sector" | "position";
  tradePreview: boolean;
  recoveryState: "error" | "loading" | "ready";
}

const etfs: EtfCandidate[] = [
  { code: "510500.SH", name: "中证500ETF南方", amount: 2_771_000_000, spread: 0.001, fee: 0.15, tracking: 0.032 },
  { code: "512500.SH", name: "中证500ETF华夏", amount: 578_000_000, spread: 0.001, fee: 0.15, tracking: 0.041 },
  { code: "159922.SZ", name: "中证500ETF嘉实", amount: 297_000_000, spread: 0.002, fee: 0.15, tracking: 0.029 },
  { code: "510580.SH", name: "中证500ETF易方达", amount: 200_000_000, spread: 0.001, fee: 0.15, tracking: 0.037 },
  { code: "510510.SH", name: "中证500ETF广发", amount: 81_000_000, spread: 0.002, fee: 0.15, tracking: 0.046 },
];

const zh = (locale: StoryLocale): boolean => locale === "zh-CN";

function actionButton(action: string, label: string, icon: string, active = false): string {
  return `<button type="button" class="compact-button ${active ? "is-active" : ""}" data-scene-action="${action}"><i data-lucide="${icon}"></i>${label}</button>`;
}

function renderDemand(locale: StoryLocale): string {
  const steps = zh(locale)
    ? [
        ["01", "识别对象", "中证500 · ETF"],
        ["02", "严格过滤", "排除标普500、增强策略与代码误召回"],
        ["03", "实时排序", "成交额、价差、跟踪误差"],
        ["04", "可视复核", "打开首选标的 K 线"],
      ]
    : [
        ["01", "Resolve", "CSI 500 · ETF"],
        ["02", "Strict filter", "Exclude S&P 500, enhanced funds, and code-only matches"],
        ["03", "Live ranking", "Turnover, spread, tracking error"],
        ["04", "Visual review", "Open the top candidate's K-line"],
      ];
  return `<section class="intent-app">
    <header class="embedded-header"><div><i data-lucide="ListChecks"></i><strong>${zh(locale) ? "Agent 执行计划" : "Agent execution plan"}</strong></div><span>${zh(locale) ? "只读行情" : "Read-only market data"}</span></header>
    <div class="intent-steps">${steps
      .map(([number, title, detail]) => `<div class="intent-row"><b>${number}</b><div><strong>${title}</strong><span>${detail}</span></div><i data-lucide="ArrowRight"></i></div>`)
      .join("")}</div>
    <footer class="embedded-footer">${actionButton("next:search", zh(locale) ? "进入标的搜索" : "Continue to search", "ArrowRight")}</footer>
  </section>`;
}

function renderSearch(locale: StoryLocale, state: SceneUiState): string {
  const results = [
    ["600118.SH", zh(locale) ? "中国卫星" : "China Spacesat", "98%", zh(locale) ? "拼音首字母" : "Pinyin initials"],
    ["600879.SH", zh(locale) ? "航天电子" : "Aerospace Electronics", "62%", zh(locale) ? "航天主题" : "Aerospace theme"],
    ["000901.SZ", zh(locale) ? "航天科技" : "Aerospace Hi-Tech", "58%", zh(locale) ? "航天主题" : "Aerospace theme"],
    ["601698.SH", zh(locale) ? "中国卫通" : "China Satcom", "51%", zh(locale) ? "名称相近" : "Similar name"],
  ];
  const selected = results.find(([code]) => code === state.searchSelection) ?? results[0]!;
  return `<section class="search-confirmation">
    <div class="search-match"><span class="match-icon"><i data-lucide="Search"></i></span><div><small>${zh(locale) ? "最可能的匹配" : "Most likely match"}</small><strong>${selected[1]} <code>${selected[0]}</code></strong><span>${selected[3]} · ${zh(locale) ? "置信度" : "confidence"} ${selected[2]}</span></div></div>
    ${state.searchConfirmed ? `<p class="search-confirmed" role="status"><i data-lucide="CircleCheck"></i>${zh(locale) ? "已确认，后续行情工具将使用这个代码。" : "Confirmed. Later market tools will use this code."}</p>` : `<div class="search-actions"><button type="button" class="primary-compact" data-scene-action="search-confirm"><i data-lucide="Check"></i>${zh(locale) ? "确认此标的" : "Confirm instrument"}</button><button type="button" class="text-compact" data-scene-action="search-toggle">${state.searchExpanded ? (zh(locale) ? "收起候选" : "Hide candidates") : zh(locale) ? "查看其他 3 个候选" : "Show 3 alternatives"}<i data-lucide="${state.searchExpanded ? "ChevronUp" : "ChevronDown"}"></i></button></div>`}
    ${state.searchExpanded && !state.searchConfirmed ? `<div class="candidate-list">${results
      .filter(([code]) => code !== state.searchSelection)
      .map(
        ([code, name, confidence, matched]) => `<button type="button" class="candidate-row" data-scene-action="select-search:${code}"><span><strong>${name}</strong><code>${code}</code></span><span>${matched}</span><b>${confidence}</b></button>`,
      )
      .join("")}</div>` : ""}
  </section>`;
}

function renderKline(locale: StoryLocale, state: SceneUiState): string {
  const payload = successFixture(state.klinePeriod);
  const latest = payload.bars.at(-1)!;
  const periodLabels: Record<string, [string, string]> = { "1d": ["日线", "Daily"], "1w": ["周线", "Weekly"], "1mon": ["月线", "Monthly"] };
  return `<section class="story-kline-app">
    <header class="quote-header"><div class="quote-identity"><i data-lucide="ChartCandlestick"></i><strong>${zh(locale) ? "天岳先进" : "Tianyue Advanced"}</strong><code>688234.SH</code></div><div class="quote-price"><b>136.42</b><span>+1.42</span><span>+1.05%</span></div><div class="quote-source"><i></i>${zh(locale) ? "QMT 行情" : "QMT market"}</div></header>
    <div class="kline-toolbar"><div class="period-buttons">${(["1d", "1w", "1mon"] as const)
      .map((period) => `<button type="button" data-scene-action="period:${period}" aria-pressed="${state.klinePeriod === period}">${periodLabels[period]![zh(locale) ? 0 : 1]}</button>`)
      .join("")}</div><button type="button" class="adjustment-button">${zh(locale) ? "前复权" : "Forward"}<i data-lucide="ChevronDown"></i></button></div>
    <div class="ohlc-strip"><b>2026-08-14</b><span>${zh(locale) ? "开" : "O"} <strong>${latest.open.toFixed(2)}</strong></span><span>${zh(locale) ? "高" : "H"} <strong class="up">${latest.high.toFixed(2)}</strong></span><span>${zh(locale) ? "低" : "L"} <strong class="down">${latest.low.toFixed(2)}</strong></span><span>${zh(locale) ? "收" : "C"} <strong>${latest.close.toFixed(2)}</strong></span><span>${zh(locale) ? "成交量" : "Volume"} <strong>${formatCompact(latest.volume, locale)}</strong></span></div>
    <div class="story-chart-wrap"><div class="story-ma"><span>MA5 <b>136.85</b></span><span>MA10 <b>136.49</b></span><span>MA20 <b>131.17</b></span></div><div class="story-chart" data-story-chart></div></div>
    <footer class="kline-status"><span><i></i>${zh(locale) ? "数据来源" : "Source"} <b>QMT xtdata</b></span><span>${zh(locale) ? "时间范围" : "Range"} <b>2026-03-16 - 2026-08-14</b></span><span>${zh(locale) ? "K线数量" : "Bars"} <b>110</b></span><span>${zh(locale) ? "状态" : "Status"} <b>${zh(locale) ? "正常" : "Ready"}</b></span></footer>
  </section>`;
}

function renderEtf(locale: StoryLocale, state: SceneUiState): string {
  const ranked = rankEtfs(etfs, state.etfRank);
  const rankLabels: Record<EtfRank, [string, string]> = { liquidity: ["流动性", "Liquidity"], cost: ["费率", "Cost"], tracking: ["跟踪误差", "Tracking"] };
  return `<section class="etf-app">
    <header class="embedded-header"><div><i data-lucide="BarChart3"></i><strong>${zh(locale) ? "中证500 ETF 比较" : "CSI 500 ETF comparison"}</strong></div><div class="rank-control">${(["liquidity", "cost", "tracking"] as EtfRank[])
      .map((rank) => `<button type="button" data-scene-action="etf-rank:${rank}" aria-pressed="${state.etfRank === rank}">${rankLabels[rank][zh(locale) ? 0 : 1]}</button>`)
      .join("")}</div></header>
    <div class="etf-table" role="table"><div class="etf-head" role="row"><span>#</span><span>ETF</span><span>${zh(locale) ? "成交额" : "Turnover"}</span><span>${zh(locale) ? "买卖价差" : "Spread"}</span><span>${zh(locale) ? "跟踪误差" : "Tracking"}</span></div>
      ${ranked
        .map(
          (item, index) => `<div class="etf-row ${index === 0 ? "is-best" : ""}" role="row"><span>${index + 1}</span><span><strong>${item.name}</strong><code>${item.code}</code></span><span><b>${formatCompact(item.amount, locale)}</b><i style="--bar:${Math.max(6, (item.amount / ranked[0]!.amount) * 100)}%"></i></span><span>${item.spread.toFixed(3)}</span><span>${item.tracking.toFixed(3)}%</span></div>`,
        )
        .join("")}
    </div>
    <footer class="embedded-footer"><span>${zh(locale) ? "严格排除标普500、增强 ETF 与代码误召回" : "Strictly excludes S&P 500, enhanced ETFs, and code-only matches"}</span><strong>510500.SH</strong></footer>
  </section>`;
}

function renderPortfolio(locale: StoryLocale, state: SceneUiState): string {
  const sector = state.portfolioView === "sector";
  return `<section class="portfolio-app">
    <header class="embedded-header"><div><i data-lucide="ShieldCheck"></i><strong>${zh(locale) ? "组合风险检查" : "Portfolio risk checks"}</strong><em>${zh(locale) ? "原型数据" : "Fixture data"}</em></div><div class="rank-control"><button type="button" data-scene-action="portfolio:sector" aria-pressed="${sector}">${zh(locale) ? "行业" : "Sector"}</button><button type="button" data-scene-action="portfolio:position" aria-pressed="${!sector}">${zh(locale) ? "持仓" : "Position"}</button></div></header>
    <div class="risk-summary"><div><span>${zh(locale) ? "组合市值" : "Market value"}</span><strong>¥ 486,320</strong></div><div><span>${zh(locale) ? "最大单一持仓" : "Largest position"}</span><strong class="warn">28.4%</strong></div><div><span>${zh(locale) ? "行业集中度" : "Sector concentration"}</span><strong class="warn">47.2%</strong></div><div><span>${zh(locale) ? "可用现金" : "Available cash"}</span><strong>18.6%</strong></div></div>
    <div class="risk-list">${(sector
      ? [[zh(locale) ? "半导体" : "Semiconductors", 47.2, "warn"], [zh(locale) ? "宽基指数" : "Broad market", 24.6, "ok"], [zh(locale) ? "消费" : "Consumer", 9.6, "ok"]]
      : [["688234.SH", 28.4, "warn"], ["510500.SH", 24.6, "ok"], ["600519.SH", 9.6, "ok"]])
      .map(([name, value, tone]) => `<div class="risk-row"><span><strong>${name}</strong><small>${tone === "warn" ? (zh(locale) ? "超过建议阈值" : "Above suggested limit") : zh(locale) ? "范围内" : "Within range"}</small></span><div><i style="--risk:${value}%" class="${tone}"></i><b>${value}%</b></div></div>`)
      .join("")}</div>
    <footer class="permission-footer"><i data-lucide="LockKeyhole"></i><span>${zh(locale) ? "真实账户结果需要券商开放只读 xttrade 权限" : "Real account results require broker-granted read-only xttrade access"}</span></footer>
  </section>`;
}

function renderTrade(locale: StoryLocale, state: SceneUiState): string {
  return `<section class="trade-app">
    <header class="embedded-header"><div><i data-lucide="ClipboardCheck"></i><strong>${zh(locale) ? "条件交易计划" : "Conditional trade plan"}</strong><em class="planned">${zh(locale) ? "产品原型" : "Product prototype"}</em></div><span class="permission-copy"><i data-lucide="LockKeyhole"></i>${zh(locale) ? "交易权限未开放" : "Trading permission unavailable"}</span></header>
    <div class="trade-form"><label><span>${zh(locale) ? "标的" : "Instrument"}</span><strong>510500.SH <small>${zh(locale) ? "中证500ETF南方" : "CSI 500 ETF"}</small></strong></label><label><span>${zh(locale) ? "触发条件" : "Trigger"}</span><strong>${zh(locale) ? "最新价 ≤ 8.20" : "Last price ≤ 8.20"}</strong></label><label><span>${zh(locale) ? "有效期" : "Expiry"}</span><strong>${zh(locale) ? "未来 2 个交易日" : "Next 2 trading days"}</strong></label><label><span>${zh(locale) ? "数量" : "Quantity"}</span><strong>${zh(locale) ? "1 手 · 100 份" : "1 lot · 100 units"}</strong></label><label><span>${zh(locale) ? "价格保护" : "Price guard"}</span><strong>${zh(locale) ? "最高不超过 8.22" : "Do not exceed 8.22"}</strong></label><label><span>${zh(locale) ? "最终确认" : "Final confirmation"}</span><strong>${zh(locale) ? "执行前必须人工确认" : "Human confirmation required"}</strong></label></div>
    ${state.tradePreview ? `<div class="trade-confirm" role="status"><i data-lucide="CircleCheck"></i><div><strong>${zh(locale) ? "计划校验完成" : "Plan validation complete"}</strong><span>${zh(locale) ? "未创建订单，也未连接真实账户。" : "No order was created and no real account was connected."}</span></div></div>` : ""}
    <footer class="embedded-footer"><span>${zh(locale) ? "账户白名单 · 审计 · 幂等键 · 人工确认" : "Account allowlist · audit · idempotency key · human confirmation"}</span>${actionButton("trade-preview", state.tradePreview ? (zh(locale) ? "收起预览" : "Hide preview") : zh(locale) ? "预览计划" : "Preview plan", state.tradePreview ? "ChevronUp" : "Eye")}</footer>
  </section>`;
}

function renderRecovery(locale: StoryLocale, state: SceneUiState): string {
  const ready = state.recoveryState === "ready";
  const loading = state.recoveryState === "loading";
  const rows = [
    ["MCP Server", "ready"],
    ["QMT Client", ready ? "ready" : "login"],
    ["xtdata", ready ? "ready" : "degraded"],
    ["xttrade", "permission"],
  ];
  return `<section class="recovery-app">
    <header class="embedded-header"><div><i data-lucide="RefreshCw"></i><strong>${zh(locale) ? "连接诊断" : "Connection diagnostics"}</strong></div><span>${ready ? (zh(locale) ? "行情已恢复" : "Market data restored") : zh(locale) ? "需要处理" : "Action required"}</span></header>
    <div class="health-list">${rows
      .map(([name, status]) => `<div class="health-row"><strong>${name}</strong><span class="health-state is-${status}"><i></i>${status === "ready" ? (zh(locale) ? "已就绪" : "Ready") : status === "login" ? (zh(locale) ? "等待人工登录" : "Awaiting sign-in") : status === "permission" ? (zh(locale) ? "未授权" : "Not authorized") : zh(locale) ? "降级" : "Degraded"}</span></div>`)
      .join("")}</div>
    <div class="recovery-guidance"><i data-lucide="CircleAlert"></i><div><strong>${ready ? (zh(locale) ? "恢复完成" : "Recovery complete") : zh(locale) ? "在 QMT 窗口完成人工登录" : "Sign in from the QMT window"}</strong><span>${ready ? (zh(locale) ? "下一次工具调用会重新读取 xtdata 行情。" : "The next tool call will read xtdata again.") : zh(locale) ? "MCP 服务本身正常，不需要重建容器或重新配置客户端。" : "The MCP server is healthy; no rebuild or client reconfiguration is needed."}</span></div></div>
    <footer class="embedded-footer"><span>${zh(locale) ? "先诊断，再恢复，不隐藏真实状态" : "Diagnose first, recover second, preserve truthful status"}</span><button type="button" class="compact-button ${loading ? "is-loading" : ""}" data-scene-action="recovery-retry" ${loading ? "disabled" : ""}><i data-lucide="RefreshCw"></i>${loading ? (zh(locale) ? "检查中" : "Checking") : ready ? (zh(locale) ? "再次检查" : "Check again") : zh(locale) ? "重试连接" : "Retry connection"}</button></footer>
  </section>`;
}

export function renderSceneApp(renderer: StoryRenderer, locale: StoryLocale, state: SceneUiState): string {
  switch (renderer) {
    case "demand":
      return renderDemand(locale);
    case "search":
      return renderSearch(locale, state);
    case "kline":
      return renderKline(locale, state);
    case "etf":
      return renderEtf(locale, state);
    case "portfolio":
      return renderPortfolio(locale, state);
    case "trade":
      return renderTrade(locale, state);
    case "recovery":
      return renderRecovery(locale, state);
  }
}
