import { describe, expect, it } from "vitest";

import { movingAverage, parseToolPayload, periodLabel, resolveLocale } from "./model";

describe("parseToolPayload", () => {
  it("normalizes, sorts, and deduplicates valid bars", () => {
    const result = parseToolPayload({
      ok: true,
      instrument: { code: "688234.SH", name: "天岳先进" },
      period: "1d",
      dividend_type: "front",
      source: "test",
      range: {},
      summary: {},
      bars: [
        { time: "20260814", open: 3, high: 4, low: 2, close: 3.5, volume: 2, amount: 7 },
        { time: "20260813", open: "2", high: "3", low: "1", close: "2.5" },
        { time: "20260814", open: 4, high: 5, low: 3, close: 4.5 },
        { time: "bad", open: 0, high: 0, low: 0, close: 0 },
        { time: "bad", open: 2, high: 3, low: 1, close: 2.5 },
        { time: "20260815", open: 4, high: 3, low: 2, close: 2.5 },
      ],
    });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.bars.map((bar) => bar.time)).toEqual(["20260813", "20260814"]);
    expect(result.bars[1]?.close).toBe(4.5);
  });

  it("returns a bounded error for malformed results", () => {
    expect(parseToolPayload(null)).toMatchObject({ ok: false, error_type: "invalid_result" });
  });
});

describe("movingAverage", () => {
  it("starts after the requested window", () => {
    const bars = [1, 2, 3, 4, 5].map((close, index) => ({
      time: `2026080${index + 1}`,
      open: close,
      high: close + 1,
      low: close - 0.5,
      close,
      volume: 0,
      amount: 0,
    }));
    expect(movingAverage(bars, 3).map((point) => point.value)).toEqual([2, 3, 4]);
  });
});

describe("localization helpers", () => {
  it("uses Chinese only for Chinese locales", () => {
    expect(resolveLocale("zh-Hans-CN")).toBe("zh-CN");
    expect(resolveLocale("en-US")).toBe("en");
    expect(periodLabel("1w", "zh-CN")).toBe("周线");
    expect(periodLabel("1w", "en")).toBe("Weekly");
  });
});
