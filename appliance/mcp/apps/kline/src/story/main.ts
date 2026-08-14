import {
  ArrowRight,
  BarChart3,
  Bot,
  ChartCandlestick,
  Check,
  ChevronDown,
  ChevronUp,
  CircleAlert,
  CircleCheck,
  ClipboardCheck,
  Eye,
  Globe2,
  Languages,
  ListChecks,
  LockKeyhole,
  Menu,
  MessageSquare,
  Monitor,
  Moon,
  Paperclip,
  PieChart,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Smartphone,
  Sun,
  TerminalSquare,
  TrendingUp,
  UserRound,
  WalletCards,
  Zap,
  createIcons,
} from "lucide";
import type { IChartApi } from "lightweight-charts";

import { renderKlineChart } from "./chart";
import { resolveSceneId, sceneById } from "./model";
import { renderSceneApp, type SceneUiState } from "./renderers";
import { storyScenes } from "./scenes";
import { localized, type PreviewMode, type StoryLocale, type StoryTheme } from "./types";
import "./style.css";

interface StoryState {
  sceneId: ReturnType<typeof resolveSceneId>;
  locale: StoryLocale;
  theme: StoryTheme;
  preview: PreviewMode;
  expandedTools: Set<number>;
  composerNotice: boolean;
  sceneUi: SceneUiState;
}

const query = new URLSearchParams(window.location.search);
const preferredLocale: StoryLocale = navigator.language.toLowerCase().startsWith("zh") ? "zh-CN" : "en";
const preferredTheme: StoryTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";

const state: StoryState = {
  sceneId: resolveSceneId(query.get("scene")),
  locale: query.get("locale") === "en" ? "en" : query.get("locale") === "zh-CN" ? "zh-CN" : preferredLocale,
  theme: query.get("theme") === "dark" ? "dark" : query.get("theme") === "light" ? "light" : preferredTheme,
  preview: query.get("preview") === "mobile" ? "mobile" : "desktop",
  expandedTools: new Set<number>(),
  composerNotice: false,
  sceneUi: {
    searchSelection: "600118.SH",
    searchExpanded: false,
    searchConfirmed: false,
    klinePeriod: "1d",
    etfRank: "liquidity",
    portfolioView: "sector",
    tradePreview: false,
    recoveryState: "error",
  },
};

let chart: IChartApi | null = null;
let recoveryTimer: number | null = null;

const rootElement = document.querySelector<HTMLElement>("#story-root");
if (!rootElement) throw new Error("Missing story root");
const root: HTMLElement = rootElement;

const copy = {
  "zh-CN": {
    storyboard: "App Storyboard",
    workspaceTitle: "QMT 行情研究",
    active: "进行中",
    market: "行情",
    ready: "已支持",
    trade: "交易",
    permission: "待权限",
    hostMenu: "打开宿主菜单",
    desktop: "桌面预览",
    mobile: "移动预览",
    light: "切换浅色模式",
    dark: "切换深色模式",
    language: "切换到英文",
    user: "用户",
    agent: "QMT 助手",
    toolSuccess: "调用成功",
    toolPermission: "权限受限",
    toolError: "需要恢复",
    expandTool: "展开工具详情",
    collapseTool: "收起工具详情",
    followup: "继续追问 QMT 行情...",
    attach: "添加附件",
    send: "发送消息",
    sent: "原型已记录这条追问，不会连接真实服务。",
    fixture: "预览模式（Fixture）",
    output: "输出格式",
    schema: "Schema",
    responseTime: "响应时间",
    previewApp: "MCP App 预览",
    proposed: "拟议能力",
    sceneNavigation: "故事场景",
    agentConversation: "Agent 对话",
    appPages: "MCP App 页面",
    systemStatus: "系统状态",
    inlineResult: "对话内确认结果",
  },
  en: {
    storyboard: "App Storyboard",
    workspaceTitle: "QMT Market Research",
    active: "Working",
    market: "Market data",
    ready: "Available",
    trade: "Trading",
    permission: "Permission pending",
    hostMenu: "Open host menu",
    desktop: "Desktop preview",
    mobile: "Mobile preview",
    light: "Switch to light mode",
    dark: "Switch to dark mode",
    language: "Switch to Chinese",
    user: "User",
    agent: "QMT assistant",
    toolSuccess: "Tool succeeded",
    toolPermission: "Permission restricted",
    toolError: "Recovery required",
    expandTool: "Expand tool details",
    collapseTool: "Collapse tool details",
    followup: "Ask a follow-up about QMT market data...",
    attach: "Add attachment",
    send: "Send message",
    sent: "The fixture recorded this follow-up without contacting a real service.",
    fixture: "Preview mode (Fixture)",
    output: "Output",
    schema: "Schema",
    responseTime: "Response time",
    previewApp: "MCP App preview",
    proposed: "Proposed capability",
    sceneNavigation: "Story scenes",
    agentConversation: "Agent conversation",
    appPages: "MCP App pages",
    systemStatus: "System status",
    inlineResult: "Inline confirmation result",
  },
} as const;

function t() {
  return copy[state.locale];
}

function icon(name: string): string {
  return `<i data-lucide="${name}" aria-hidden="true"></i>`;
}

function toolStateLabel(value: "success" | "permission" | "error"): string {
  if (value === "success") return t().toolSuccess;
  if (value === "permission") return t().toolPermission;
  return t().toolError;
}

function updateUrl(): void {
  const url = new URL(window.location.href);
  url.searchParams.set("scene", state.sceneId);
  url.searchParams.set("locale", state.locale);
  url.searchParams.set("theme", state.theme);
  url.searchParams.set("preview", state.preview);
  window.history.replaceState({}, "", url);
}

function renderSceneRail(): string {
  const renderItems = (ids: string[]) => storyScenes
    .filter((item) => ids.includes(item.id))
    .map(
      (item) => `<button type="button" class="scene-link ${item.id === state.sceneId ? "is-active" : ""}" data-scene="${item.id}" aria-current="${item.id === state.sceneId ? "page" : "false"}">
        <span class="scene-number">${item.order}</span>
        ${icon(item.icon)}
        <span>${localized(item.title, state.locale)}</span>
      </button>`,
    )
    .join("");
  return `<section class="scene-group"><h2>${t().agentConversation}</h2>${renderItems(["demand", "search"])}</section>
    <section class="scene-group is-app-group"><h2>${t().appPages}</h2>${renderItems(["kline", "etf", "portfolio", "trade"])}</section>
    <section class="scene-group"><h2>${t().systemStatus}</h2>${renderItems(["recovery"])}</section>`;
}

function renderToolRows(): string {
  const scene = sceneById(state.sceneId);
  return scene.tools
    .map((tool, index) => {
      const expanded = state.expandedTools.has(index);
      const disclosureLabel = expanded ? t().collapseTool : t().expandTool;
      return `<div class="tool-call is-${tool.state}">
        <button type="button" class="tool-summary" data-tool-index="${index}" aria-expanded="${expanded}" aria-label="${disclosureLabel}: ${tool.name}">
          ${icon(expanded ? "ChevronUp" : "ChevronDown")}
          <span class="tool-icon">${icon("TerminalSquare")}</span>
          <code>${tool.name}</code>
          ${tool.proposed ? `<em>${t().proposed}</em>` : ""}
          <span class="tool-result">${icon(tool.state === "success" ? "Check" : tool.state === "permission" ? "LockKeyhole" : "CircleAlert")}${localized(tool.summary, state.locale)}</span>
          <time>${index === 0 ? "10:21" : "10:22"}</time>
          <small>${index === 0 ? "612ms" : "1.24s"}</small>
        </button>
        ${expanded ? `<div class="tool-detail"><span>${toolStateLabel(tool.state)}</span><code>${localized(tool.detail, state.locale)}</code></div>` : ""}
      </div>`;
    })
    .join("");
}

function render(): void {
  chart?.remove();
  chart = null;
  const scene = sceneById(state.sceneId);
  const sceneTitle = localized(scene.title, state.locale);
  document.documentElement.dataset.theme = state.theme;
  document.documentElement.lang = state.locale;
  document.title = `${sceneTitle} · QMT-MCP App Storyboard`;

  root.innerHTML = `<main class="story-shell">
    <aside class="story-rail">
      <header class="story-brand"><span class="brand-symbol">${icon("TrendingUp")}</span><div><strong>QMT-MCP</strong><span>${t().storyboard}</span></div></header>
      <nav class="scene-nav" aria-label="${t().sceneNavigation}">${renderSceneRail()}</nav>
      <footer class="capability-legend">
        <div>${icon("TrendingUp")}<span>${t().market}</span><strong>${t().ready}</strong></div>
        <div>${icon("Zap")}<span>${t().trade}</span><strong class="is-pending">${t().permission}</strong></div>
      </footer>
    </aside>

    <section class="story-workspace">
      <header class="host-toolbar">
        <button type="button" class="toolbar-icon menu-control" aria-label="${t().hostMenu}">${icon("Menu")}</button>
        <strong>${t().workspaceTitle}</strong>
        <span class="host-status"><i></i>${t().active}${icon("ChevronDown")}</span>
        <div class="host-controls">
          <div class="preview-control" role="group" aria-label="Preview size">
            <button type="button" data-preview="desktop" aria-pressed="${state.preview === "desktop"}" aria-label="${t().desktop}">${icon("Monitor")}</button>
            <button type="button" data-preview="mobile" aria-pressed="${state.preview === "mobile"}" aria-label="${t().mobile}">${icon("Smartphone")}</button>
          </div>
          <button type="button" class="toolbar-icon" data-theme-toggle aria-label="${state.theme === "dark" ? t().light : t().dark}">${icon(state.theme === "dark" ? "Sun" : "Moon")}</button>
          <button type="button" class="language-control" data-locale-toggle aria-label="${t().language}">${icon("Globe2")}<span>${state.locale === "zh-CN" ? "中文" : "EN"}</span>${icon("ChevronDown")}</button>
        </div>
      </header>

      <div class="host-stage">
        <article class="host-frame is-${state.preview}" aria-label="${sceneTitle}">
          <div class="conversation-scroll">
            <section class="message user-message">
              <div class="message-bubble"><p>${localized(scene.userMessage, state.locale)}</p><time>10:21</time></div>
              <span class="person-avatar" aria-label="${t().user}">${icon("UserRound")}</span>
            </section>

            <section class="message assistant-message">
              <span class="agent-avatar" aria-label="${t().agent}">${icon("Bot")}</span>
              <div class="assistant-content"><p>${localized(scene.assistantLead, state.locale)}</p><time>10:21</time></div>
            </section>

            <section class="tool-stack" aria-label="Tool activity">${renderToolRows()}</section>

            ${scene.presentation === "conversation" ? "" : `<section class="${scene.presentation === "app" ? "app-attachment" : `inline-surface is-${scene.presentation}`}" aria-label="${scene.presentation === "app" ? t().previewApp : t().inlineResult}">${renderSceneApp(scene.renderer, state.locale, state.sceneUi)}</section>`}

            <section class="message assistant-message conclusion-message">
              <span class="agent-avatar" aria-label="${t().agent}">${icon("Bot")}</span>
              <div class="assistant-content"><p>${localized(scene.conclusion, state.locale)}</p><time>10:22</time><div class="response-actions"><button type="button" aria-label="Useful">${icon("CircleCheck")}</button><button type="button" aria-label="More details">${icon("MessageSquare")}</button></div></div>
            </section>
          </div>

          <form class="composer" data-composer>
            ${state.composerNotice ? `<p class="composer-notice" role="status">${icon("CircleCheck")}${t().sent}</p>` : ""}
            <div><button type="button" class="composer-icon" aria-label="${t().attach}">${icon("Paperclip")}</button><input name="message" autocomplete="off" placeholder="${t().followup}" aria-label="${t().followup}"><button type="submit" class="send-button" aria-label="${t().send}">${icon("Send")}</button></div>
          </form>
        </article>
      </div>
    </section>

    <footer class="reviewer-bar">
      <span>${icon("Eye")}<strong>${t().fixture}</strong></span>
      <span>${t().output}<code>structuredContent</code></span>
      <span>${t().schema}<code>${scene.schema}</code></span>
      <span>${t().responseTime}<b>${scene.renderer === "kline" ? "862ms" : "418ms"}</b>${icon("CircleCheck")}</span>
    </footer>
  </main>`;

  hydrateIcons();
  bindEvents();
  const chartContainer = root.querySelector<HTMLElement>("[data-story-chart]");
  if (chartContainer) chart = renderKlineChart(chartContainer, state.theme, state.sceneUi.klinePeriod);
  window.requestAnimationFrame(() => {
    const navigation = root.querySelector<HTMLElement>(".scene-nav");
    const activeScene = navigation?.querySelector<HTMLElement>(".scene-link.is-active");
    if (navigation && activeScene && navigation.scrollWidth > navigation.clientWidth) {
      navigation.scrollLeft = Math.max(0, activeScene.offsetLeft - navigation.clientWidth / 2 + activeScene.clientWidth / 2);
    }
  });
  updateUrl();
}

function resetTransientState(): void {
  state.expandedTools.clear();
  state.composerNotice = false;
}

function selectScene(id: ReturnType<typeof resolveSceneId>): void {
  if (id === state.sceneId) return;
  state.sceneId = id;
  resetTransientState();
  render();
}

function handleSceneAction(action: string): void {
  const [verb, value] = action.split(":", 2);
  if (verb === "next" && value) {
    selectScene(resolveSceneId(value));
    return;
  }
  if (verb === "select-search" && value) {
    state.sceneUi.searchSelection = value;
    state.sceneUi.searchExpanded = false;
    state.sceneUi.searchConfirmed = false;
  }
  if (verb === "search-toggle") state.sceneUi.searchExpanded = !state.sceneUi.searchExpanded;
  if (verb === "search-confirm") state.sceneUi.searchConfirmed = true;
  if (verb === "period" && (value === "1d" || value === "1w" || value === "1mon")) state.sceneUi.klinePeriod = value;
  if (verb === "etf-rank" && (value === "liquidity" || value === "cost" || value === "tracking")) state.sceneUi.etfRank = value;
  if (verb === "portfolio" && (value === "sector" || value === "position")) state.sceneUi.portfolioView = value;
  if (verb === "trade-preview") state.sceneUi.tradePreview = !state.sceneUi.tradePreview;
  if (verb === "recovery-retry") {
    state.sceneUi.recoveryState = "loading";
    render();
    if (recoveryTimer !== null) window.clearTimeout(recoveryTimer);
    recoveryTimer = window.setTimeout(() => {
      state.sceneUi.recoveryState = "ready";
      recoveryTimer = null;
      render();
    }, 650);
    return;
  }
  render();
}

function bindEvents(): void {
  root.querySelectorAll<HTMLButtonElement>("[data-scene]").forEach((button) => {
    button.addEventListener("click", () => selectScene(resolveSceneId(button.dataset.scene)));
  });
  root.querySelectorAll<HTMLButtonElement>("[data-tool-index]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.toolIndex);
      if (state.expandedTools.has(index)) state.expandedTools.delete(index);
      else state.expandedTools.add(index);
      render();
    });
  });
  root.querySelectorAll<HTMLButtonElement>("[data-scene-action]").forEach((button) => {
    button.addEventListener("click", () => handleSceneAction(button.dataset.sceneAction ?? ""));
  });
  root.querySelectorAll<HTMLButtonElement>("[data-preview]").forEach((button) => {
    button.addEventListener("click", () => {
      state.preview = button.dataset.preview === "mobile" ? "mobile" : "desktop";
      render();
    });
  });
  root.querySelector<HTMLButtonElement>("[data-theme-toggle]")?.addEventListener("click", () => {
    state.theme = state.theme === "light" ? "dark" : "light";
    render();
  });
  root.querySelector<HTMLButtonElement>("[data-locale-toggle]")?.addEventListener("click", () => {
    state.locale = state.locale === "zh-CN" ? "en" : "zh-CN";
    render();
  });
  root.querySelector<HTMLFormElement>("[data-composer]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement;
    const input = form.elements.namedItem("message") as HTMLInputElement | null;
    if (!input?.value.trim()) return;
    state.composerNotice = true;
    render();
  });
}

function hydrateIcons(): void {
  createIcons({
    icons: {
      ArrowRight,
      BarChart3,
      Bot,
      ChartCandlestick,
      Check,
      ChevronDown,
      ChevronUp,
      CircleAlert,
      CircleCheck,
      ClipboardCheck,
      Eye,
      Globe2,
      Languages,
      ListChecks,
      LockKeyhole,
      Menu,
      MessageSquare,
      Monitor,
      Moon,
      Paperclip,
      PieChart,
      RefreshCw,
      Search,
      Send,
      ShieldCheck,
      Smartphone,
      Sun,
      TerminalSquare,
      TrendingUp,
      UserRound,
      WalletCards,
      Zap,
    },
  });
}

render();
