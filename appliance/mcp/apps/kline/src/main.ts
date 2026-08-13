import { App } from "@modelcontextprotocol/ext-apps";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  createChart,
  type BusinessDay,
  type CandlestickData,
  type ChartOptions,
  type DeepPartial,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import { ChartCandlestick, Maximize2, Minimize2, RefreshCw, createIcons } from "lucide";

import { emptyFixture, errorFixture, successFixture } from "./fixtures";
import {
  formatCompact,
  formatDate,
  movingAverage,
  parseToolPayload,
  periodLabel,
  resolveLocale,
  type KLineBar,
  type KLinePayload,
  type Locale,
  type Theme,
  type ToolPayload,
} from "./model";
import "./style.css";

const TOOL_NAME = "qmt_xtdata_kline_chart";
const PERIODS = ["1d", "1w", "1mon"] as const;
const DIVIDENDS = ["none", "front", "back", "front_ratio", "back_ratio"] as const;

const translations = {
  "zh-CN": {
    loading: "正在读取 QMT 行情",
    empty: "所选区间暂无 K 线数据",
    error: "行情加载失败",
    retry: "重试",
    open: "开",
    high: "高",
    low: "低",
    close: "收",
    change: "涨跌",
    volume: "成交量",
    amount: "成交额",
    updated: "更新",
    live: "QMT 行情",
    source: "数据来源",
    range: "时间范围",
    bars: "K线数量",
    status: "状态",
    normal: "正常",
    refreshing: "刷新中",
    fullscreen: "全屏查看",
    exitFullscreen: "退出全屏",
    adjustment: "复权方式",
    dividend: {
      none: "不复权",
      front: "前复权",
      back: "后复权",
      front_ratio: "等比前复权",
      back_ratio: "等比后复权",
    },
  },
  en: {
    loading: "Loading QMT market data",
    empty: "No K-line data in this range",
    error: "Market data unavailable",
    retry: "Retry",
    open: "O",
    high: "H",
    low: "L",
    close: "C",
    change: "Change",
    volume: "Volume",
    amount: "Amount",
    updated: "Updated",
    live: "QMT market data",
    source: "Source",
    range: "Range",
    bars: "Bars",
    status: "Status",
    normal: "Ready",
    refreshing: "Refreshing",
    fullscreen: "View fullscreen",
    exitFullscreen: "Exit fullscreen",
    adjustment: "Adjustment",
    dividend: {
      none: "Unadjusted",
      front: "Forward",
      back: "Backward",
      front_ratio: "Forward ratio",
      back_ratio: "Backward ratio",
    },
  },
} as const;

type Period = (typeof PERIODS)[number];
type Dividend = (typeof DIVIDENDS)[number];

interface State {
  payload: ToolPayload | null;
  previousSuccess: KLinePayload | null;
  input: Record<string, unknown>;
  locale: Locale;
  theme: Theme;
  connected: boolean;
  refreshing: boolean;
  fullscreen: boolean;
}

const query = new URLSearchParams(window.location.search);
const fixtureMode = query.get("fixture");
const browserTheme: Theme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
const forcedTheme = query.get("theme");
const forcedLocale = query.get("locale");
const state: State = {
  payload: null,
  previousSuccess: null,
  input: {},
  locale: resolveLocale(forcedLocale ?? navigator.language),
  theme: forcedTheme === "dark" ? "dark" : forcedTheme === "light" ? "light" : browserTheme,
  connected: false,
  refreshing: false,
  fullscreen: false,
};

let chart: IChartApi | null = null;
let candleSeries: ISeriesApi<"Candlestick"> | null = null;
let app: App | null = null;
let lastRenderedBar: KLineBar | null = null;

const rootElement = document.querySelector<HTMLElement>("#app");
if (!rootElement) throw new Error("Missing app root");
const root: HTMLElement = rootElement;

function t() {
  return translations[state.locale];
}

function icon(name: "ChartCandlestick" | "Maximize2" | "Minimize2" | "RefreshCw"): string {
  return `<i data-lucide="${name}" aria-hidden="true"></i>`;
}

function formatPrice(value: number | null | undefined): string {
  return value === null || value === undefined || !Number.isFinite(value) ? "--" : value.toFixed(2);
}

function formatChange(value: number | null | undefined, suffix = ""): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}${suffix}`;
}

function changeClass(value: number | null | undefined): string {
  if (!value) return "is-flat";
  return value > 0 ? "is-up" : "is-down";
}

function activePayload(): ToolPayload | null {
  if (state.payload?.ok === false && state.previousSuccess) return state.previousSuccess;
  return state.payload;
}

function selectedPeriod(payload: KLinePayload): Period {
  return PERIODS.includes(payload.period as Period) ? (payload.period as Period) : "1d";
}

function selectedDividend(payload: KLinePayload): Dividend {
  return DIVIDENDS.includes(payload.dividend_type as Dividend) ? (payload.dividend_type as Dividend) : "none";
}

function renderShell(): void {
  document.documentElement.dataset.theme = state.theme;
  document.documentElement.lang = state.locale;
  const payload = activePayload();
  if (!payload) {
    root.innerHTML = `<section class="state-screen"><span class="spinner" aria-hidden="true"></span><p>${t().loading}</p></section>`;
    return;
  }
  if (!payload.ok) {
    const canRetry = fixtureMode !== null || Boolean(app?.getHostCapabilities()?.serverTools);
    root.innerHTML = `
      <section class="state-screen error-state" role="alert">
        ${icon("ChartCandlestick")}
        <strong>${t().error}</strong>
        <p>${escapeHtml(payload.error)}</p>
        ${canRetry ? `<button type="button" class="retry-button" data-retry>${icon("RefreshCw")}${t().retry}</button>` : ""}
      </section>`;
    hydrateIcons();
    root.querySelector<HTMLButtonElement>("[data-retry]")?.addEventListener("click", () => void retryLastRequest());
    return;
  }

  const latest = payload.bars.at(-1) ?? null;
  const summary = payload.summary;
  const change = summary.change;
  const period = selectedPeriod(payload);
  const dividend = selectedDividend(payload);
  const fullscreenAvailable = fixtureMode !== null || app?.getHostContext()?.availableDisplayModes?.includes("fullscreen");
  const warning = state.payload?.ok === false ? `<div class="inline-error" role="alert">${escapeHtml(state.payload.error)}</div>` : "";
  const canRefresh = fixtureMode !== null || Boolean(app?.getHostCapabilities()?.serverTools);
  const maValues = [5, 10, 20].map((window) => ({ window, value: movingAverage(payload.bars, window).at(-1)?.value }));

  root.innerHTML = `
    <section class="kline-app ${state.fullscreen ? "is-fullscreen" : ""}">
      <header class="instrument-header">
        <div class="instrument-identity">
          <span class="brand-mark">${icon("ChartCandlestick")}</span>
          <h1>${escapeHtml(payload.instrument.name || payload.instrument.code)}</h1>
          <span class="instrument-code">${escapeHtml(payload.instrument.code)}</span>
        </div>
        <div class="quote-summary ${changeClass(change)}">
          <strong>${formatPrice(summary.latest_close)}</strong>
          <span>${formatChange(change)}</span>
          <span>${formatChange(summary.change_percent, "%")}</span>
        </div>
        <div class="update-meta">
          <span>${t().updated} ${formatDate(payload.range.end, true)}</span>
          <span class="source-state"><i></i>${t().live}</span>
        </div>
      </header>

      <div class="toolbar">
        <div class="period-control" role="group" aria-label="${periodLabel(period, state.locale)}">
          ${PERIODS.map(
            (value) =>
              `<button type="button" data-period="${value}" aria-pressed="${value === period}" ${state.refreshing || !canRefresh ? "disabled" : ""}>${periodLabel(value, state.locale)}</button>`,
          ).join("")}
        </div>
        <div class="toolbar-actions">
          <label class="adjustment-select">
            <span class="sr-only">${t().adjustment}</span>
            <select data-adjustment ${state.refreshing || !canRefresh ? "disabled" : ""}>
              ${DIVIDENDS.map(
                (value) => `<option value="${value}" ${value === dividend ? "selected" : ""}>${t().dividend[value]}</option>`,
              ).join("")}
            </select>
          </label>
          ${
            fullscreenAvailable
              ? `<button type="button" class="icon-button" data-fullscreen title="${state.fullscreen ? t().exitFullscreen : t().fullscreen}" aria-label="${state.fullscreen ? t().exitFullscreen : t().fullscreen}">${icon(state.fullscreen ? "Minimize2" : "Maximize2")}</button>`
              : ""
          }
        </div>
      </div>

      ${warning}
      <div class="data-strip" data-data-strip></div>

      <div class="chart-stage">
        <div class="ma-legend">
          ${maValues.map(({ window, value }, index) => `<span class="ma-${index}">MA${window} <strong>${formatPrice(value)}</strong></span>`).join("")}
        </div>
        <div class="chart-canvas" data-chart></div>
        ${
          payload.bars.length === 0
            ? `<div class="chart-empty">${icon("ChartCandlestick")}<span>${t().empty}</span></div>`
            : ""
        }
        ${state.refreshing ? `<div class="refresh-mask"><span class="spinner"></span><span>${t().refreshing}</span></div>` : ""}
      </div>

      <footer class="status-bar">
        <span><i class="status-dot"></i>${t().source} <strong>${escapeHtml(payload.source)}</strong></span>
        <span>${t().range} <strong>${formatDate(payload.range.start)} - ${formatDate(payload.range.end)}</strong></span>
        <span>${t().bars} <strong>${payload.range.bar_count}</strong></span>
        <span>${t().status} <strong>${t().normal}</strong></span>
      </footer>
    </section>`;

  hydrateIcons();
  bindControls(payload);
  renderDataStrip(payload, latest);
  renderChart(payload);
}

function hydrateIcons(): void {
  createIcons({ icons: { ChartCandlestick, Maximize2, Minimize2, RefreshCw } });
}

function renderDataStrip(payload: KLinePayload, bar: KLineBar | null): void {
  const strip = root.querySelector<HTMLElement>("[data-data-strip]");
  if (!strip) return;
  lastRenderedBar = bar;
  if (!bar) {
    strip.innerHTML = `<span class="strip-date">${periodLabel(payload.period, state.locale)}</span>`;
    return;
  }
  const previousIndex = payload.bars.indexOf(bar) - 1;
  const previous = previousIndex >= 0 ? payload.bars[previousIndex] : null;
  const change = previous ? bar.close - previous.close : null;
  const percent = previous && previous.close ? (change! / previous.close) * 100 : null;
  strip.innerHTML = `
    <span class="strip-date">${formatDate(bar.time, true)}</span>
    <span>${t().open} <strong>${formatPrice(bar.open)}</strong></span>
    <span>${t().high} <strong class="is-up">${formatPrice(bar.high)}</strong></span>
    <span>${t().low} <strong class="is-down">${formatPrice(bar.low)}</strong></span>
    <span>${t().close} <strong>${formatPrice(bar.close)}</strong></span>
    <span>${t().change} <strong class="${changeClass(change)}">${formatChange(change)} (${formatChange(percent, "%")})</strong></span>
    <span>${t().volume} <strong>${formatCompact(bar.volume, state.locale)}</strong></span>
    <span>${t().amount} <strong>${formatCompact(bar.amount, state.locale)}</strong></span>`;
}

function parseChartTime(value: string): Time {
  const digits = value.replace(/\D/g, "");
  if (digits.length >= 12) {
    return Math.floor(
      Date.UTC(
        Number(digits.slice(0, 4)),
        Number(digits.slice(4, 6)) - 1,
        Number(digits.slice(6, 8)),
        Number(digits.slice(8, 10)),
        Number(digits.slice(10, 12)),
        Number(digits.slice(12, 14) || "0"),
      ) / 1000,
    ) as UTCTimestamp;
  }
  return {
    year: Number(digits.slice(0, 4)),
    month: Number(digits.slice(4, 6)),
    day: Number(digits.slice(6, 8)),
  } satisfies BusinessDay;
}

function timeKey(value: Time | null): string {
  if (value === null) return "";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  return `${value.year}${String(value.month).padStart(2, "0")}${String(value.day).padStart(2, "0")}`;
}

function formatChartTick(value: Time): string {
  if (typeof value === "number") {
    const date = new Date(value * 1000);
    return `${String(date.getUTCMonth() + 1).padStart(2, "0")}-${String(date.getUTCDate()).padStart(2, "0")}`;
  }
  if (typeof value === "string") return value;
  return `${String(value.month).padStart(2, "0")}-${String(value.day).padStart(2, "0")}`;
}

function chartOptions(): DeepPartial<ChartOptions> {
  const styles = getComputedStyle(document.documentElement);
  return {
    autoSize: true,
    layout: {
      background: { type: ColorType.Solid, color: styles.getPropertyValue("--surface").trim() },
      textColor: styles.getPropertyValue("--text-muted").trim(),
      attributionLogo: false,
      fontFamily: styles.getPropertyValue("--font").trim(),
      fontSize: 12,
      panes: { separatorColor: styles.getPropertyValue("--border").trim(), separatorHoverColor: "#2d966b" },
    },
    grid: {
      vertLines: { color: styles.getPropertyValue("--grid").trim() },
      horzLines: { color: styles.getPropertyValue("--grid").trim() },
    },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: { color: styles.getPropertyValue("--crosshair").trim(), labelBackgroundColor: "#30363f" },
      horzLine: { color: styles.getPropertyValue("--crosshair").trim(), labelBackgroundColor: "#30363f" },
    },
    rightPriceScale: { borderColor: styles.getPropertyValue("--border").trim(), scaleMargins: { top: 0.08, bottom: 0.05 } },
    timeScale: {
      borderColor: styles.getPropertyValue("--border").trim(),
      timeVisible: true,
      secondsVisible: false,
      rightOffset: 2,
      tickMarkFormatter: formatChartTick,
    },
    localization: { locale: state.locale },
    handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
    handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
  };
}

function renderChart(payload: KLinePayload): void {
  chart?.remove();
  chart = null;
  candleSeries = null;
  if (!payload.bars.length) return;
  const container = root.querySelector<HTMLElement>("[data-chart]");
  if (!container) return;
  const styles = getComputedStyle(document.documentElement);
  const up = styles.getPropertyValue("--up").trim();
  const down = styles.getPropertyValue("--down").trim();
  chart = createChart(container, chartOptions());
  candleSeries = chart.addSeries(CandlestickSeries, {
    upColor: up,
    downColor: down,
    wickUpColor: up,
    wickDownColor: down,
    borderVisible: false,
    priceLineVisible: true,
    lastValueVisible: true,
  });
  const indexed = new Map<string, KLineBar>();
  const candles: CandlestickData<Time>[] = payload.bars.map((bar) => {
    const time = parseChartTime(bar.time);
    indexed.set(timeKey(time), bar);
    return { time, open: bar.open, high: bar.high, low: bar.low, close: bar.close };
  });
  candleSeries.setData(candles);

  const colors = ["#2477e3", "#ed7d31", "#8c52d6"];
  [5, 10, 20].forEach((window, index) => {
    const series = chart!.addSeries(LineSeries, {
      color: colors[index],
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    series.setData(movingAverage(payload.bars, window).map((point) => ({ time: parseChartTime(point.time), value: point.value })));
  });

  const volumeSeries = chart.addSeries(
    HistogramSeries,
    { priceFormat: { type: "volume" }, priceScaleId: "volume", priceLineVisible: false, lastValueVisible: false },
    1,
  );
  volumeSeries.setData(
    payload.bars.map((bar) => ({
      time: parseChartTime(bar.time),
      value: bar.volume,
      color: `${bar.close >= bar.open ? up : down}b8`,
    })),
  );
  requestAnimationFrame(() => {
    const panes = chart?.panes();
    const total = container.clientHeight;
    if (panes?.[0] && panes[1] && total > 280) {
      panes[0].setHeight(Math.round(total * 0.72));
      panes[1].setHeight(Math.round(total * 0.28));
    }
    chart?.timeScale().fitContent();
  });
  chart.subscribeCrosshairMove((param) => {
    const selected = indexed.get(timeKey(param.time ?? null));
    if (selected && selected !== lastRenderedBar) renderDataStrip(payload, selected);
    if (!param.time && lastRenderedBar !== payload.bars.at(-1)) renderDataStrip(payload, payload.bars.at(-1) ?? null);
  });
}

function bindControls(payload: KLinePayload): void {
  root.querySelectorAll<HTMLButtonElement>("[data-period]").forEach((button) => {
    button.addEventListener("click", () => {
      const period = button.dataset.period as Period | undefined;
      if (period && period !== payload.period) void refresh(payload, { period });
    });
  });
  root.querySelector<HTMLSelectElement>("[data-adjustment]")?.addEventListener("change", (event) => {
    const dividend_type = (event.currentTarget as HTMLSelectElement).value as Dividend;
    if (dividend_type !== payload.dividend_type) void refresh(payload, { dividend_type });
  });
  root.querySelector<HTMLButtonElement>("[data-fullscreen]")?.addEventListener("click", () => void toggleFullscreen());
}

async function refresh(payload: KLinePayload, overrides: Record<string, unknown>): Promise<void> {
  state.refreshing = true;
  renderShell();
  const arguments_ = {
    code: payload.instrument.code,
    period: payload.period,
    start_time: state.input.start_time ?? "",
    end_time: state.input.end_time ?? "",
    count: state.input.count ?? Math.min(Math.max(payload.range.bar_count, 120), 1000),
    dividend_type: payload.dividend_type,
    ...overrides,
  };
  try {
    if (fixtureMode !== null) {
      await new Promise((resolve) => window.setTimeout(resolve, 250));
      acceptPayload(successFixture(String(arguments_.period), String(arguments_.dividend_type)));
    } else if (app?.getHostCapabilities()?.serverTools) {
      const result = await app.callServerTool({ name: TOOL_NAME, arguments: arguments_ });
      acceptPayload(parseToolPayload(result.structuredContent));
    }
  } catch (error) {
    state.payload = {
      ok: false,
      error_type: "host_call",
      error: error instanceof Error ? error.message : String(error),
    };
  } finally {
    state.input = arguments_;
    state.refreshing = false;
    renderShell();
  }
}

async function retryLastRequest(): Promise<void> {
  state.payload = null;
  renderShell();
  try {
    if (fixtureMode !== null) {
      await new Promise((resolve) => window.setTimeout(resolve, 250));
      acceptPayload(successFixture());
    } else if (app?.getHostCapabilities()?.serverTools) {
      const result = await app.callServerTool({ name: TOOL_NAME, arguments: state.input });
      acceptPayload(parseToolPayload(result.structuredContent));
    }
  } catch (error) {
    state.payload = {
      ok: false,
      error_type: "host_call",
      error: error instanceof Error ? error.message : String(error),
    };
  } finally {
    renderShell();
  }
}

async function toggleFullscreen(): Promise<void> {
  if (fixtureMode !== null) {
    state.fullscreen = !state.fullscreen;
  } else if (app) {
    const result = await app.requestDisplayMode({ mode: state.fullscreen ? "inline" : "fullscreen" });
    state.fullscreen = result.mode === "fullscreen";
  }
  renderShell();
}

function acceptPayload(payload: ToolPayload): void {
  state.payload = payload;
  if (payload.ok) state.previousSuccess = payload;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => {
    const entities: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" };
    return entities[character] ?? character;
  });
}

function fixturePayload(): ToolPayload {
  if (fixtureMode === "empty") return emptyFixture;
  if (fixtureMode === "error") return errorFixture;
  return successFixture();
}

async function connect(): Promise<void> {
  if (fixtureMode !== null) {
    acceptPayload(fixturePayload());
    state.connected = true;
    renderShell();
    return;
  }

  app = new App({ name: "QMT K-Line", version: "1.0.0" }, {});
  app.ontoolinput = ({ arguments: arguments_ }) => {
    state.input = arguments_ ?? {};
  };
  app.ontoolresult = (result) => {
    acceptPayload(parseToolPayload(result.structuredContent));
    renderShell();
  };
  app.onhostcontextchanged = (context) => {
    if (context.theme) state.theme = context.theme;
    if (context.locale) state.locale = resolveLocale(context.locale);
    state.fullscreen = context.displayMode === "fullscreen";
    renderShell();
  };
  await app.connect();
  const context = app.getHostContext();
  if (context?.theme) state.theme = context.theme;
  if (context?.locale) state.locale = resolveLocale(context.locale);
  state.fullscreen = context?.displayMode === "fullscreen";
  state.connected = true;
  renderShell();
}

renderShell();
void connect().catch((error: unknown) => {
  acceptPayload({ ok: false, error_type: "host_connection", error: error instanceof Error ? error.message : String(error) });
  renderShell();
});
