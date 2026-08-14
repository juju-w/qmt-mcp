export type StoryLocale = "zh-CN" | "en";
export type StoryTheme = "light" | "dark";
export type PreviewMode = "desktop" | "mobile";
export type Availability = "ready" | "permission" | "recovery";
export type ToolState = "success" | "permission" | "error";
export type StoryRenderer = "demand" | "search" | "kline" | "etf" | "portfolio" | "trade" | "recovery";
export type StorySceneId = StoryRenderer;
export type StoryPresentation = "conversation" | "confirmation" | "app" | "status";
export type StoryVisibility = "public" | "draft";

export interface LocalizedText {
  "zh-CN": string;
  en: string;
}

export interface StoryToolActivity {
  name: string;
  state: ToolState;
  summary: LocalizedText;
  detail: LocalizedText;
  proposed?: boolean;
}

export interface StoryScene {
  id: StorySceneId;
  order: number;
  visibility: StoryVisibility;
  icon: string;
  availability: Availability;
  title: LocalizedText;
  userMessage: LocalizedText;
  assistantLead: LocalizedText;
  tools: StoryToolActivity[];
  conclusion: LocalizedText;
  schema: string;
  renderer: StoryRenderer;
  presentation: StoryPresentation;
}

export function localized(value: LocalizedText, locale: StoryLocale): string {
  return value[locale];
}
