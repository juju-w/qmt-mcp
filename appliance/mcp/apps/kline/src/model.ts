export type Locale = "zh-CN" | "en";
export type Theme = "light" | "dark";

export interface Instrument {
  code: string;
  name: string;
}

export interface KLineBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
}

export interface KLineSummary {
  latest_close: number | null;
  previous_close: number | null;
  change: number | null;
  change_percent: number | null;
  high: number | null;
  low: number | null;
}

export interface KLinePayload {
  ok: true;
  schema_version: "1";
  instrument: Instrument;
  period: string;
  dividend_type: string;
  source: string;
  range: {
    start: string;
    end: string;
    bar_count: number;
  };
  summary: KLineSummary;
  bars: KLineBar[];
}

export interface KLineError {
  ok: false;
  error_type: string;
  error: string;
  details?: Record<string, unknown>;
}

export type ToolPayload = KLinePayload | KLineError;

export interface ChartPoint {
  time: string;
  value: number;
}

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const finiteNumber = (value: unknown): number | null => {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const nullableNumber = (value: unknown): number | null =>
  value === null || value === undefined ? null : finiteNumber(value);

function parseBar(value: unknown): KLineBar | null {
  if (!isObject(value)) return null;
  const rawTime = typeof value.time === "string" ? value.time.trim() : String(value.time ?? "").trim();
  const time = rawTime.replace(/\D/g, "");
  const open = finiteNumber(value.open);
  const high = finiteNumber(value.high);
  const low = finiteNumber(value.low);
  const close = finiteNumber(value.close);
  const volume = finiteNumber(value.volume) ?? 0;
  const amount = finiteNumber(value.amount) ?? 0;
  if (![8, 12, 14].includes(time.length) || open === null || high === null || low === null || close === null) return null;
  if (open <= 0 || high <= 0 || low <= 0 || close <= 0 || high < Math.max(open, close) || low > Math.min(open, close)) {
    return null;
  }
  return { time, open, high, low, close, volume: Math.max(0, volume), amount: Math.max(0, amount) };
}

export function parseToolPayload(value: unknown): ToolPayload {
  if (!isObject(value) || typeof value.ok !== "boolean") {
    return { ok: false, error_type: "invalid_result", error: "Invalid K-line tool result" };
  }
  if (!value.ok) {
    return {
      ok: false,
      error_type: typeof value.error_type === "string" ? value.error_type : "unknown",
      error: typeof value.error === "string" ? value.error : "K-line request failed",
      details: isObject(value.details) ? value.details : {},
    };
  }

  const instrument = isObject(value.instrument) ? value.instrument : {};
  const range = isObject(value.range) ? value.range : {};
  const summary = isObject(value.summary) ? value.summary : {};
  const rows = Array.isArray(value.bars) ? value.bars : [];
  const byTime = new Map<string, KLineBar>();
  for (const row of rows) {
    const parsed = parseBar(row);
    if (parsed) byTime.set(parsed.time, parsed);
  }
  const bars = [...byTime.values()].sort((a, b) => a.time.localeCompare(b.time));

  return {
    ok: true,
    schema_version: "1",
    instrument: {
      code: typeof instrument.code === "string" ? instrument.code : "",
      name: typeof instrument.name === "string" ? instrument.name : "",
    },
    period: typeof value.period === "string" ? value.period : "1d",
    dividend_type: typeof value.dividend_type === "string" ? value.dividend_type : "none",
    source: typeof value.source === "string" ? value.source : "QMT xtdata",
    range: {
      start: typeof range.start === "string" ? range.start : (bars[0]?.time ?? ""),
      end: typeof range.end === "string" ? range.end : (bars.at(-1)?.time ?? ""),
      bar_count: finiteNumber(range.bar_count) ?? bars.length,
    },
    summary: {
      latest_close: nullableNumber(summary.latest_close),
      previous_close: nullableNumber(summary.previous_close),
      change: nullableNumber(summary.change),
      change_percent: nullableNumber(summary.change_percent),
      high: nullableNumber(summary.high),
      low: nullableNumber(summary.low),
    },
    bars,
  };
}

export function movingAverage(bars: KLineBar[], window: number): ChartPoint[] {
  if (window < 1) return [];
  const points: ChartPoint[] = [];
  let sum = 0;
  for (let index = 0; index < bars.length; index += 1) {
    const bar = bars[index];
    if (!bar) continue;
    sum += bar.close;
    const dropped = bars[index - window];
    if (dropped) sum -= dropped.close;
    if (index >= window - 1) points.push({ time: bar.time, value: sum / window });
  }
  return points;
}

export function resolveLocale(value?: string): Locale {
  return value?.toLowerCase().startsWith("zh") ? "zh-CN" : "en";
}

export function formatDate(value: string, includeTime = false): string {
  const digits = value.replace(/\D/g, "");
  if (digits.length < 8) return value;
  const date = `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6, 8)}`;
  if (!includeTime || digits.length < 12) return date;
  return `${date} ${digits.slice(8, 10)}:${digits.slice(10, 12)}`;
}

export function formatCompact(value: number | null, locale: Locale): string {
  if (value === null || !Number.isFinite(value)) return "--";
  if (locale === "zh-CN") {
    if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(2)}亿`;
    if (value >= 10_000) return `${(value / 10_000).toFixed(2)}万`;
    return value.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
  }
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(2)}K`;
  return value.toLocaleString("en", { maximumFractionDigits: 0 });
}

export function periodLabel(period: string, locale: Locale): string {
  const labels: Record<string, [string, string]> = {
    "1d": ["日线", "Daily"],
    "1w": ["周线", "Weekly"],
    "1mon": ["月线", "Monthly"],
    "1h": ["小时线", "Hourly"],
    "30m": ["30分钟", "30 min"],
    "15m": ["15分钟", "15 min"],
    "5m": ["5分钟", "5 min"],
    "1m": ["1分钟", "1 min"],
  };
  const label = labels[period];
  return label ? label[locale === "zh-CN" ? 0 : 1] : period;
}
