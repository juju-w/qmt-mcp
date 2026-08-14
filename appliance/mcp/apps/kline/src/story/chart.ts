import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  createChart,
  type BusinessDay,
  type IChartApi,
  type Time,
} from "lightweight-charts";

import { successFixture } from "../fixtures";
import { movingAverage } from "../model";
import type { StoryTheme } from "./types";

function chartTime(value: string): BusinessDay {
  const digits = value.replace(/\D/g, "");
  return {
    year: Number(digits.slice(0, 4)),
    month: Number(digits.slice(4, 6)),
    day: Number(digits.slice(6, 8)),
  };
}

export function renderKlineChart(container: HTMLElement, theme: StoryTheme, period: string): IChartApi {
  const dark = theme === "dark";
  const surface = dark ? "#151817" : "#ffffff";
  const text = dark ? "#a8b0ac" : "#66706c";
  const border = dark ? "#343a37" : "#dfe5e2";
  const grid = dark ? "#282d2a" : "#edf0ee";
  const up = dark ? "#f05252" : "#df2f2f";
  const down = dark ? "#30a56f" : "#168657";
  const payload = successFixture(period);
  const chart = createChart(container, {
    autoSize: true,
    layout: {
      background: { type: ColorType.Solid, color: surface },
      textColor: text,
      attributionLogo: false,
      fontFamily: 'Inter, "Segoe UI", "PingFang SC", sans-serif',
      fontSize: 11,
      panes: { separatorColor: border, separatorHoverColor: "#238b63" },
    },
    grid: { vertLines: { color: grid }, horzLines: { color: grid } },
    rightPriceScale: { borderColor: border, scaleMargins: { top: 0.08, bottom: 0.05 } },
    timeScale: { borderColor: border, rightOffset: 2 },
    handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
    handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
  });
  const candles = chart.addSeries(CandlestickSeries, {
    upColor: up,
    downColor: down,
    wickUpColor: up,
    wickDownColor: down,
    borderVisible: false,
    priceLineVisible: true,
  });
  candles.setData(payload.bars.map((bar) => ({ time: chartTime(bar.time), open: bar.open, high: bar.high, low: bar.low, close: bar.close })));

  [
    { window: 5, color: "#2477e3" },
    { window: 10, color: "#ed7d31" },
    { window: 20, color: "#8c52d6" },
  ].forEach(({ window, color }) => {
    const series = chart.addSeries(LineSeries, {
      color,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    series.setData(movingAverage(payload.bars, window).map((point) => ({ time: chartTime(point.time), value: point.value })));
  });

  const volume = chart.addSeries(HistogramSeries, { priceScaleId: "volume", priceFormat: { type: "volume" }, priceLineVisible: false }, 1);
  volume.setData(
    payload.bars.map((bar) => ({
      time: chartTime(bar.time) as Time,
      value: bar.volume,
      color: `${bar.close >= bar.open ? up : down}b8`,
    })),
  );
  requestAnimationFrame(() => {
    const panes = chart.panes();
    const total = container.clientHeight;
    if (panes[0] && panes[1] && total > 260) {
      panes[0].setHeight(Math.round(total * 0.72));
      panes[1].setHeight(Math.round(total * 0.28));
    }
    chart.timeScale().fitContent();
  });
  return chart;
}
