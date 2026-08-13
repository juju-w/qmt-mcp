import type { KLineError, KLinePayload } from "./model";

function dateKey(date: Date): string {
  return `${date.getUTCFullYear()}${String(date.getUTCMonth() + 1).padStart(2, "0")}${String(date.getUTCDate()).padStart(2, "0")}`;
}

export function successFixture(period = "1d", dividendType = "front"): KLinePayload {
  const bars = [];
  let close = 84.2;
  const cursor = new Date(Date.UTC(2026, 2, 16));
  for (let index = 0; bars.length < 110; index += 1) {
    const date = new Date(cursor.getTime() + index * 86_400_000);
    const weekday = date.getUTCDay();
    if (weekday === 0 || weekday === 6) continue;
    const trend = 0.45 + Math.sin(index / 5.1) * 1.1 + Math.cos(index / 12) * 0.5;
    const open = close + Math.sin(index * 1.7) * 1.35;
    close = Math.max(72, open + trend);
    const high = Math.max(open, close) + 1.2 + Math.abs(Math.sin(index)) * 1.8;
    const low = Math.min(open, close) - 1.0 - Math.abs(Math.cos(index)) * 1.5;
    const volume = 3_800_000 + Math.round((Math.sin(index / 4) + 1.4) * 2_300_000 + (index % 9) * 160_000);
    bars.push({
      time: dateKey(date),
      open: Number(open.toFixed(2)),
      high: Number(high.toFixed(2)),
      low: Number(low.toFixed(2)),
      close: Number(close.toFixed(2)),
      volume,
      amount: Number((volume * close).toFixed(2)),
    });
  }
  const previous = bars.at(-2)!;
  Object.assign(previous, {
    open: 134.46,
    high: 136.12,
    low: 133.72,
    close: 135,
    volume: 7_940_000,
    amount: 1_071_900_000,
  });
  const latest = bars.at(-1)!;
  Object.assign(latest, {
    open: 134.88,
    high: 137.26,
    low: 134.31,
    close: 136.42,
    volume: 8_260_000,
    amount: 1_126_829_200,
  });
  const change = latest.close - previous.close;
  return {
    ok: true,
    schema_version: "1",
    instrument: { code: "688234.SH", name: "天岳先进" },
    period,
    dividend_type: dividendType,
    source: "QMT xtdata",
    range: { start: bars[0]!.time, end: latest.time, bar_count: bars.length },
    summary: {
      latest_close: latest.close,
      previous_close: previous.close,
      change,
      change_percent: (change / previous.close) * 100,
      high: Math.max(...bars.map((bar) => bar.high)),
      low: Math.min(...bars.map((bar) => bar.low)),
    },
    bars,
  };
}

export const emptyFixture: KLinePayload = {
  ok: true,
  schema_version: "1",
  instrument: { code: "688234.SH", name: "天岳先进" },
  period: "1d",
  dividend_type: "front",
  source: "QMT xtdata",
  range: { start: "", end: "", bar_count: 0 },
  summary: { latest_close: null, previous_close: null, change: null, change_percent: null, high: null, low: null },
  bars: [],
};

export const errorFixture: KLineError = {
  ok: false,
  error_type: "not_ready",
  error: "QMT 行情尚未就绪，请确认客户端已登录。",
};
