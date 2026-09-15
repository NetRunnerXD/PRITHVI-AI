import { create } from "zustand";
import type { ChatMsg, DashboardSnapshot, Density, Location, TabId, ThemeId, UiAction, UnitSys } from "@/types/dashboard";
import { resolveTab } from "@/types/dashboard";
import type { Locale } from "@/i18n/copy";

export type ReplyLocale = Locale | "auto";
import { fetchDashboard, reverseGeocode } from "./api";
import { fetchMe, logoutAccount, type AuthUser } from "./auth";
import { buildOptimisticSnapshot, fetchClientOmPack, type OmClientPack } from "./openMeteoClient";
import type { WxLayer } from "./weatherScale";

export type MapSessionState = {
  basemap: string;
  wxLayer: WxLayer | null;
  hour: number;
  particles: boolean;
  overlays: string[];
  highlights: string[];
  overlayOpacity: number;
  showPin: boolean;
  pastHours: number;
  minConfidence: number;
  state: string;
  sidebarTab: "maps" | "events";
  sidebarCollapsed: boolean;
  openSection: "weather" | "basemap" | "hazards" | "geomorph" | null;
};

export const DEFAULT_MAP_SESSION: MapSessionState = {
  basemap: "dark",
  wxLayer: null,
  hour: 0,
  particles: true,
  overlays: [],
  highlights: [],
  overlayOpacity: 0.7,
  showPin: true,
  pastHours: 6,
  minConfidence: 0,
  state: "India",
  sidebarTab: "maps",
  sidebarCollapsed: false,
  openSection: "weather",
};

async function loadOmPack(loc: Location | null | undefined, disabled: string[]): Promise<OmClientPack | undefined> {
  if (!loc || disabled.includes("open-meteo")) return undefined;
  try {
    const pack = await fetchClientOmPack(loc.lat, loc.lon, !disabled.includes("open-meteo-air"));
    return pack || undefined;
  } catch {
    return undefined;
  }
}

const FAV_KEY = "prithvi.favs";
const REC_KEY = "prithvi.recent";
const SET_KEY = "prithvi.settings";
const LOC_KEY = "prithvi.loc";
const SNAP_KEY = "prithvi.last_snap";

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
  llmProvider?: string;
  showEvidence?: boolean;
  displayNullValues?: boolean;
  showAdvancedTabs?: boolean;
  devDisabledProviders?: string[];
};

export const DEFAULT_SETTINGS: AppSettings = {
  theme: "midnight",
  units: "metric",
  density: "comfortable",
  reduceMotion: false,
  fontScale: 100,
  refreshSec: 600,
  defaultTab: "home",
  showHints: false,
  locale: "en",
  llmProvider: "local",
  showEvidence: false,
  displayNullValues: false,
  showAdvancedTabs: false,
  devDisabledProviders: ["nasa-power", "nasa-power-clim"],
};

export function readSettings(): AppSettings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    const raw = JSON.parse(window.localStorage.getItem(SET_KEY) || window.localStorage.getItem("rituchakra.settings") || "{}") as Partial<AppSettings>;
    const tab = resolveTab(raw.defaultTab) || DEFAULT_SETTINGS.defaultTab;
    const devDisabled = Array.isArray(raw.devDisabledProviders)
      ? raw.devDisabledProviders
      : DEFAULT_SETTINGS.devDisabledProviders;
    return { ...DEFAULT_SETTINGS, ...raw, defaultTab: tab, devDisabledProviders: devDisabled };
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

function readSavedLoc(): Location | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(LOC_KEY);
    return raw ? (JSON.parse(raw) as Location) : null;
  } catch {
    return null;
  }
}

function writeSavedLoc(loc: Location) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(LOC_KEY, JSON.stringify(loc));
}

function readCachedSnapshot(locId?: string): DashboardSnapshot | null {
  if (typeof window === "undefined") return null;
  try {
    const key = locId ? `${SNAP_KEY}.${locId}` : SNAP_KEY;
    const raw = window.localStorage.getItem(key) || window.localStorage.getItem(SNAP_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as DashboardSnapshot;
  } catch {
    return null;
  }
}

function writeCachedSnapshot(snap: DashboardSnapshot) {
  if (typeof window === "undefined") return;
  try {
    const serialized = JSON.stringify(snap);
    window.localStorage.setItem(SNAP_KEY, serialized);
    if (snap.location?.id) {
      window.localStorage.setItem(`${SNAP_KEY}.${snap.location.id}`, serialized);
    }
  } catch {
    // LocalStorage quota safety
  }
}

function askGps(): Promise<Location | null> {
  if (typeof navigator === "undefined" || !navigator.geolocation) return Promise.resolve(null);
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        void reverseGeocode(pos.coords.latitude, pos.coords.longitude)
          .then((loc) => resolve(loc))
          .catch(() => resolve(null));
      },
      () => resolve(null),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 },
    );
  });
}

type State = {
  locale: Locale;
  tab: TabId;
  location: Location | null;
  dashboard: DashboardSnapshot | null;
  status: "idle" | "loading" | "ready" | "error";
  syncStatus: "synced" | "syncing" | "direct" | "offline";
  error?: string;
  chat: ChatMsg[];
  streaming: boolean;
  conversationId: string;
  highlight: string | null;
  mapFocus: { center: [number, number]; zoom?: number } | null;
  windowPack: Record<string, unknown> | null;
  outputLocale: ReplyLocale;
  sidebarOpen: boolean;
  pendingAsk: string | null;
  floatChatOpen: boolean;
  favorites: Location[];
  recent: Location[];
  settings: AppSettings;
  viewMode: "detail" | "overview";
  setViewMode: (v: "detail" | "overview") => void;
  mapSession: MapSessionState;
  setMapSession: (p: Partial<MapSessionState> | ((prev: MapSessionState) => Partial<MapSessionState>)) => void;
  account: AuthUser | null;
  authModal: boolean;
  setAccount: (u: AuthUser | null) => void;
  setAuthModal: (v: boolean) => void;
  loadAccount: () => Promise<void>;
  signOut: () => void;
  setSettings: (p: Partial<AppSettings>) => void;
  resetSettings: () => void;
  setSidebarOpen: (v: boolean) => void;
  setPendingAsk: (q: string | null) => void;
  setFloatChatOpen: (v: boolean) => void;
  openFloatChat: (prompt?: string) => void;
  setLocale: (l: Locale) => void;
  setOutputLocale: (l: ReplyLocale) => void;
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
    district?: string;
    place?: string;
    lat?: number;
    lon?: number;
    center?: number[];
    zoom?: number;
  }) => void;
  applyWidgetPatch: (path: string, value: unknown) => void;
};

function newConversationId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `c-${Date.now()}`;
}

const TABS = new Set<TabId>(["home", "analytics", "data", "map", "model", "chat", "settings"]);

let dashAbort: AbortController | null = null;

export const useApp = create<State>((set, get) => ({
  locale: "en",
  tab: "home",
  settings: DEFAULT_SETTINGS,
  account: null,
  authModal: false,
  setAccount: (account) => set({ account }),
  setAuthModal: (authModal) => set({ authModal }),
  loadAccount: async () => {
    const account = await fetchMe();
    set({ account });
  },
  signOut: () => {
    logoutAccount();
    set({ account: null });
  },
  location: null,
  dashboard: null,
  status: "idle",
  syncStatus: "synced",
  chat: [],
  streaming: false,
  conversationId: newConversationId(),
  highlight: null,
  mapFocus: null,
  windowPack: null,
  outputLocale: "auto",
  sidebarOpen: true,
  pendingAsk: null,
  floatChatOpen: false,
  favorites: [],
  recent: [],
  viewMode: "detail",
  setViewMode: (viewMode) => set({ viewMode }),
  mapSession: DEFAULT_MAP_SESSION,
  setMapSession: (p) =>
    set((state) => ({
      mapSession: {
        ...state.mapSession,
        ...(typeof p === "function" ? p(state.mapSession) : p),
      },
    })),
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
  setFloatChatOpen: (floatChatOpen) => set({ floatChatOpen }),
  openFloatChat: (prompt) => {
    if (prompt) {
      set({ floatChatOpen: true, pendingAsk: prompt });
    } else {
      set({ floatChatOpen: true });
    }
  },
  setLocale: (locale) => {
    const settings = { ...get().settings, locale };
    if (typeof window !== "undefined") window.localStorage.setItem(SET_KEY, JSON.stringify(settings));
    applyTheme(settings, locale);
    const keepAuto = get().outputLocale === "auto";
    set({ locale, outputLocale: keepAuto ? "auto" : locale, settings });
  },
  setOutputLocale: (outputLocale) => set({ outputLocale }),
  setTab: (tab) => set({ tab }),
  applySnapshot: (dashboard) => {
    writeCachedSnapshot(dashboard);
    set({ dashboard, location: dashboard.location, status: "ready", syncStatus: "synced" });
  },
  toggleFavorite: (loc) => {
    const favs = get().favorites.length ? get().favorites : readList(FAV_KEY);
    const next = favs.some((f) => f.id === loc.id) ? favs.filter((f) => f.id !== loc.id) : [loc, ...favs];
    writeList(FAV_KEY, next);
    set({ favorites: next });
  },
  setLocation: async (location) => {
    writeSavedLoc(location);
    const rec = [location, ...readList(REC_KEY).filter((r) => r.id !== location.id && r.label !== location.label)];
    writeList(REC_KEY, rec);
    const ac = new AbortController();
    const prev = dashAbort;
    dashAbort = ac;
    prev?.abort();

    // 1. Check local storage cache for instant 0ms render
    const cached = readCachedSnapshot(location.id);
    if (cached) {
      set({
        location,
        dashboard: cached,
        status: "ready",
        syncStatus: "syncing",
        recent: rec,
        error: undefined,
      });
    } else {
      // Immediately wire new location to dashboard with a responsive optimistic shell
      const initialSnap = buildOptimisticSnapshot(location, {});
      set({
        location,
        dashboard: initialSnap,
        status: "ready",
        syncStatus: "syncing",
        recent: rec,
        error: undefined,
      });

    }

    // 3. Deep Hydration from Backend (POST client Open-Meteo so Render skips quota)
    try {
      const disabled = get().settings.devDisabledProviders || [];
      const omPack = await loadOmPack(location, disabled);
      if (dashAbort !== ac) return;
      if (omPack && get().syncStatus !== "synced") {
        const optSnap = buildOptimisticSnapshot(location, omPack.forecast, omPack.air);
        set({ dashboard: optSnap, location, status: "ready", syncStatus: "direct" });
      }
      const dashboard = await fetchDashboard(location, ac.signal, disabled, omPack);
      if (dashAbort !== ac) return;
      writeSavedLoc(dashboard.location);
      writeCachedSnapshot(dashboard);
      set({
        dashboard,
        location: dashboard.location,
        status: "ready",
        syncStatus: "synced",
        error: undefined,
        favorites: get().favorites.length ? get().favorites : readList(FAV_KEY),
      });
    } catch (e) {
      if (ac.signal.aborted || dashAbort !== ac) return;
      if (get().dashboard && get().dashboard?.location?.id === location.id) {
        set({ syncStatus: "direct", error: undefined });
      } else {
        set({ status: "error", syncStatus: "offline", error: e instanceof Error ? e.message : String(e) });
      }
    }
  },
  refresh: async () => {
    const ac = new AbortController();
    const prev = dashAbort;
    dashAbort = ac;
    prev?.abort();

    let loc = get().location || readSavedLoc();
    if (!loc) loc = await askGps();
    if (loc) writeSavedLoc(loc);

    // If we have an existing or cached dashboard, display it immediately without blanking
    const cached = loc ? readCachedSnapshot(loc.id) : readCachedSnapshot();
    const existing = (get().dashboard && (!loc || get().dashboard?.location?.id === loc.id))
      ? get().dashboard
      : cached;
    if (existing) {
      set({ dashboard: existing, location: loc || existing.location, status: "ready", syncStatus: "syncing" });
    } else if (loc) {
      const initialSnap = buildOptimisticSnapshot(loc, {});
      set({ dashboard: initialSnap, location: loc, status: "ready", syncStatus: "syncing" });
    } else {
      set({ status: "loading", syncStatus: "syncing" });
    }

    try {
      const disabled = get().settings.devDisabledProviders || [];
      const omPack = loc ? await loadOmPack(loc, disabled) : undefined;
      if (dashAbort !== ac) return;
      if (omPack && loc && get().syncStatus !== "synced") {
        const optSnap = buildOptimisticSnapshot(loc, omPack.forecast, omPack.air);
        set({ dashboard: optSnap, location: loc, status: "ready", syncStatus: "direct" });
      }
      const dashboard = await fetchDashboard(loc || undefined, ac.signal, disabled, omPack);
      if (dashAbort !== ac) return;
      writeSavedLoc(dashboard.location);
      writeCachedSnapshot(dashboard);
      set({
        dashboard,
        location: dashboard.location,
        status: "ready",
        syncStatus: "synced",
        favorites: get().favorites.length ? get().favorites : readList(FAV_KEY),
        recent: get().recent.length ? get().recent : readList(REC_KEY),
      });
    } catch (e) {
      if (ac.signal.aborted || dashAbort !== ac) return;
      if (get().dashboard) {
        set({ syncStatus: "direct" });
      } else {
        set({ status: "error", syncStatus: "offline", error: String(e) });
      }
    }
  },
  quietRefresh: async () => {
    const loc = get().location || readSavedLoc() || undefined;
    const locId = loc?.id;
    try {
      const disabled = get().settings.devDisabledProviders || [];
      const omPack = loc ? await loadOmPack(loc, disabled) : undefined;
      const dashboard = await fetchDashboard(loc, undefined, disabled, omPack);
      const cur = get().location;
      if (locId && cur && cur.id !== locId) return;
      if (loc && cur && (Math.abs(cur.lat - loc.lat) > 1e-3 || Math.abs(cur.lon - loc.lon) > 1e-3)) return;
      writeCachedSnapshot(dashboard);
      set({ dashboard, location: dashboard.location, status: "ready", syncStatus: "synced" });
    } catch {
      // Quiet background refresh failure shouldn't disrupt UI
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
    const nextTab = resolveTab(s.tab);
    if (nextTab && TABS.has(nextTab)) set({ tab: nextTab });
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
