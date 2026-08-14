import { visibleStoryScenes } from "./scenes";
import type { StoryScene, StorySceneId } from "./types";

export interface EtfCandidate {
  code: string;
  name: string;
  amount: number;
  spread: number;
  fee: number;
  tracking: number;
}

export type EtfRank = "liquidity" | "cost" | "tracking";

export function resolveSceneId(value: string | null | undefined): StorySceneId {
  return visibleStoryScenes.some((scene) => scene.id === value) ? (value as StorySceneId) : "kline";
}

export function sceneById(id: StorySceneId): StoryScene {
  return visibleStoryScenes.find((scene) => scene.id === id) ?? visibleStoryScenes.find((scene) => scene.id === "kline")!;
}

export function rankEtfs(candidates: EtfCandidate[], rank: EtfRank): EtfCandidate[] {
  return [...candidates].sort((left, right) => {
    if (rank === "liquidity") return right.amount - left.amount || left.spread - right.spread;
    if (rank === "cost") return left.fee - right.fee || right.amount - left.amount;
    return left.tracking - right.tracking || right.amount - left.amount;
  });
}

export function validateStoryScenes(scenes: StoryScene[]): string[] {
  const issues: string[] = [];
  const ids = new Set<string>();
  scenes.forEach((scene, index) => {
    if (ids.has(scene.id)) issues.push(`duplicate scene id: ${scene.id}`);
    ids.add(scene.id);
    if (scene.order !== index + 1) issues.push(`non-contiguous order: ${scene.id}`);
    if (!scene.title["zh-CN"] || !scene.title.en) issues.push(`missing title locale: ${scene.id}`);
    if (scene.availability === "permission" && scene.tools.some((tool) => tool.state === "success" && tool.proposed)) {
      issues.push(`permission scene exposes successful proposed tool: ${scene.id}`);
    }
  });
  return issues;
}
