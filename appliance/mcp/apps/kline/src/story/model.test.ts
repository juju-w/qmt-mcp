import { describe, expect, it } from "vitest";

import { storyScenes, visibleStoryScenes } from "./scenes";
import { rankEtfs, resolveSceneId, validateStoryScenes } from "./model";

describe("story fixture contract", () => {
  it("keeps seven ordered bilingual scenes", () => {
    expect(storyScenes).toHaveLength(7);
    expect(validateStoryScenes(storyScenes)).toEqual([]);
    expect(storyScenes.map((scene) => scene.order)).toEqual([1, 2, 3, 4, 5, 6, 7]);
    expect(storyScenes.filter((scene) => scene.presentation === "app").map((scene) => scene.id)).toEqual(["kline", "etf", "portfolio", "trade"]);
    expect(visibleStoryScenes.map((scene) => scene.id)).toEqual(["kline"]);
    expect(visibleStoryScenes.filter((scene) => scene.presentation === "app").map((scene) => scene.id)).toEqual(["kline"]);
  });

  it("uses a stable default for unknown and draft deep links", () => {
    expect(resolveSceneId("kline")).toBe("kline");
    expect(resolveSceneId("search")).toBe("kline");
    expect(resolveSceneId("trade")).toBe("kline");
    expect(resolveSceneId("unknown")).toBe("kline");
    expect(resolveSceneId(null)).toBe("kline");
  });
});

describe("ETF ranking", () => {
  const candidates = [
    { code: "A", name: "A", amount: 20, spread: 0.002, fee: 0.2, tracking: 0.03 },
    { code: "B", name: "B", amount: 50, spread: 0.001, fee: 0.5, tracking: 0.02 },
  ];

  it("ranks independently by the selected reviewer criterion", () => {
    expect(rankEtfs(candidates, "liquidity")[0]?.code).toBe("B");
    expect(rankEtfs(candidates, "cost")[0]?.code).toBe("A");
    expect(rankEtfs(candidates, "tracking")[0]?.code).toBe("B");
  });
});
