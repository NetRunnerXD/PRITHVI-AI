import { create } from "zustand";
import type { ChatMsg, DashboardSnapshot, Density, Location, TabId, ThemeId, UiAction, UnitSys } from "@/types/dashboard";
import type { Locale } from "@/i18n/copy";
import { fetchDashboard } from "./api";

const FAV_KEY = "rituchakra.favs";
const REC_KEY = "rituchakra.recent";
const SET_KEY = "rituchakra.settings";

export type AppSettings = {
  theme: ThemeId;
  units: UnitSys;
  density: Density;
  reduceMotion: boolean;
  fontScale: number;
  refreshSec: number;
  defaultTab: TabId;
  showHints: boolean;
  locale?: Locale;
};

export const DEFAULT_SETTINGS: AppSettings = {
  theme: "sand",
  units: "metric",
  density: "comfortable",
  reduceMotion: false,
  fontScale: 100,
  refreshSec: 60,
  defaultTab: "overview",
  showHints: false,
  locale: "en",
};

export function readSettings(): AppSettings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    return { ...DEFAULT_SETTINGS, ...(JSON.parse(window.localStorage.getItem(SET_KEY) || "{}") as Partial<AppSettings>) };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function applyTheme(s: AppSettings, locale?: Locale) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.dataset.theme = s.theme;
  root.dataset.density = s.density;
  root.dataset.motion = s.reduceMotion ? "off" : "on";
  root.style.fontSize = `${s.fontScale}%`;
  const lang = locale || s.locale || "en";
  root.lang = lang;
}

function readList(key: string): Location[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as Location[]) : [];
  } catch {
    return [];
  }
}

function writeList(key: string, rows: Location[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, JSON.stringify(rows.slice(0, 8)));
}

type State = {
  locale: Locale;
  tab: TabId;
  location: Location | null;
  dashboard: DashboardSnapshot | null;
  status: "idle" | "loading" | "ready" | "error";
  error?: string;
  chat: ChatMsg[];
  streaming: boolean;
  conversationId: string;
  highlight: string | null;
  mapFocus: { center: [number, number]; zoom?: number } | null;
  windowPack: Record<string, unknown> | null;
  outputLocale: Locale;
  sidebarOpen: boolean;
  pendingAsk: string | null;
  favorites: Location[];
  recent: Location[];
  settings: AppSettings;
  setSettings: (p: Partial<AppSettings>) => void;
  resetSettings: () => void;
  setSidebarOpen: (v: boolean) => void;
  setPendingAsk: (q: string | null) => void;
  setLocale: (l: Locale) => void;
  setOutputLocale: (l: Locale) => void;
  setTab: (t: TabId) => void;
  setLocation: (l: Location) => Promise<void>;
  toggleFavorite: (l: Location) => void;
  refresh: () => Promise<void>;
  quietRefresh: () => Promise<void>;
  applySnapshot: (d: DashboardSnapshot) => void;
  addChat: (m: ChatMsg) => void;
  replaceLastAssistant: (m: ChatMsg) => void;
  patchLastUser: (p: Partial<ChatMsg>) => void;
  clearChat: () => void;
  setStreaming: (v: boolean) => void;
  applyUi: (actions: UiAction[]) => void;
  applySuggestion: (s: {
    tab?: string;
    window?: Record<string, unknown>;
    location?: Location;
    center?: number[];
    zoom?: number;
  }) => void;
  applyWidgetPatch: (path: string, value: unknown) => void;
};

function newConversationId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `c-${Date.now()}`;
}

const TABS = new Set<TabId>([
  "overview",
  "nowcast",
  "alerts",
  "map",
  "forecast",
  "predicted",
  "risks",
  "market",
  "advisor",
  "settings",
]);

export const useApp = create<State>((set, get) => ({
  locale: "en",
  tab: "overview",
  settings: DEFAULT_SETTINGS,
  location: null,
  dashboard: null,
  status: "idle",
  chat: [],
  streaming: false,
  conversationId: newConversationId(),
  highlight: null,
  mapFocus: null,
  windowPack: null,
  outputLocale: "en",
  sidebarOpen: true,
  pendingAsk: null,
  favorites: [],
  recent: [],
  setSettings: (p) => {
    const settings = { ...get().settings, ...p };
    if (typeof window !== "undefined") window.localStorage.setItem(SET_KEY, JSON.stringify(settings));
    applyTheme(settings);
    set({ settings });
  },
  resetSettings: () => {
    if (typeof window !== "undefined") window.localStorage.setItem(SET_KEY, JSON.stringify(DEFAULT_SETTINGS));
    applyTheme(DEFAULT_SETTINGS);
    set({ settings: DEFAULT_SETTINGS });
  },
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  setPendingAsk: (pendingAsk) => set({ pendingAsk }),
  setLocale: (locale) => {
    const settings = { ...get().settings, locale };
    if (typeof window !== "undefined") window.localStorage.setItem(SET_KEY, JSON.stringify(settings));
    applyTheme(settings, locale);
    set({ locale, outputLocale: locale, settings });
  },
  setOutputLocale: (outputLocale) => set({ outputLocale }),
  setTab: (tab) => set({ tab }),
  applySnapshot: (dashboard) =>
    set({ dashboard, location: dashboard.location, status: "ready" }),
  toggleFavorite: (loc) => {
    const favs = get().favorites.length ? get().favorites : readList(FAV_KEY);
    const next = favs.some((f) => f.id === loc.id) ? favs.filter((f) => f.id !== loc.id) : [loc, ...favs];
    writeList(FAV_KEY, next);
    set({ favorites: next });
  },
  setLocation: async (location) => {
    set({ location, status: "loading" });
    try {
      const dashboard = await fetchDashboard(location);
      const rec = [dashboard.location, ...readList(REC_KEY).filter((r) => r.id !== dashboard.location.id)];
      writeList(REC_KEY, rec);
      set({
        dashboard,
        location: dashboard.location,
        status: "ready",
        recent: rec,
        favorites: get().favorites.length ? get().favorites : readList(FAV_KEY),
      });
    } catch (e) {
      set({ status: "error", error: String(e) });
    }
  },
  refresh: async () => {
    set({ status: "loading" });
    try {
      const dashboard = await fetchDashboard(get().location || undefined);
      set({
        dashboard,
        location: dashboard.location,
        status: "ready",
        favorites: get().favorites.length ? get().favorites : readList(FAV_KEY),
        recent: get().recent.length ? get().recent : readList(REC_KEY),
      });
    } catch (e) {
      set({ status: "error", error: String(e) });
    }
  },
  quietRefresh: async () => {
    try {
      const dashboard = await fetchDashboard(get().location || undefined);
      set({ dashboard, location: dashboard.location, status: "ready" });
    } catch (e) {
      if (!get().dashboard) set({ status: "error", error: String(e) });
    }
  },
  addChat: (m) => set({ chat: [...get().chat, m] }),
  replaceLastAssistant: (m) => {
    const chat = [...get().chat];
    for (let i = chat.length - 1; i >= 0; i--) {
      if (chat[i].role === "assistant") {
        chat[i] = m;
        break;
      }
    }
    set({ chat });
  },
  patchLastUser: (p) => {
    const chat = [...get().chat];
    for (let i = chat.length - 1; i >= 0; i--) {
      if (chat[i].role === "user") {
        chat[i] = { ...chat[i], ...p };
        break;
      }
    }
    set({ chat });
  },
  clearChat: () => set({ chat: [], conversationId: newConversationId(), highlight: null, windowPack: null }),
  setStreaming: (streaming) => set({ streaming }),
  applyUi: (actions) => {
    for (const a of actions || []) {
      if (a.op === "highlight" && a.target) set({ highlight: a.target });
      if (a.op === "patch" && a.path === "window" && a.value && typeof a.value === "object") {
        set({ windowPack: a.value as Record<string, unknown> });
      }
    }
  },
  applySuggestion: (s: {
    tab?: string;
    window?: Record<string, unknown>;
    location?: Location;
    center?: number[];
    zoom?: number;
  }) => {
    const loc = s.location;
    const center = Array.isArray(s.center) && s.center.length >= 2
      ? ([Number(s.center[0]), Number(s.center[1])] as [number, number])
      : loc && typeof loc.lat === "number" && typeof loc.lon === "number"
        ? ([loc.lat, loc.lon] as [number, number])
        : null;
    if (s.window) set({ windowPack: s.window });
    if (center) set({ mapFocus: { center, zoom: s.zoom ?? 10 } });
    // Chip click with an explicit tab is an open-tab action. Location-only suggestions do not switch tabs.
    if (s.tab && TABS.has(s.tab as TabId)) set({ tab: s.tab as TabId });
    if (loc && typeof loc.lat === "number" && typeof loc.lon === "number") {
      const cur = get().location;
      const same =
        cur &&
        Math.abs(cur.lat - loc.lat) < 1e-4 &&
        Math.abs(cur.lon - loc.lon) < 1e-4;
      if (!same) void get().setLocation(loc);
    }
  },
  applyWidgetPatch: (path, value) => {
    if (path === "dashboard" && value && typeof value === "object") {
      get().applySnapshot(value as DashboardSnapshot);
      return;
    }
    if (path === "window" && value && typeof value === "object") {
      set({ windowPack: value as Record<string, unknown> });
    }
  },
}));
