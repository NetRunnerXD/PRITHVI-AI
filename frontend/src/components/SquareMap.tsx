"use client";

import { useEffect, useMemo, useState } from "react";
import { COPY, type Locale } from "@/i18n/copy";
import type { DashboardSnapshot, Location } from "@/types/dashboard";
import { fetchRadarFrames, fetchStates, fetchStormMap, fetchWeatherGrid, reverseGeocode, type StormIncident, type StormMapPack } from "@/lib/api";
import { MapWrap } from "./MapWrap";
import { StormFeed } from "./StormFeed";
import { WX_LAYERS, legendStops, unitOf, type WeatherGrid, type WxLayer } from "@/lib/weatherScale";

const BASES = ["dark", "streets", "satellite", "terrain"] as const;

const BASE_LABELS: Record<(typeof BASES)[number], { name: string; tag: string }> = {
  dark: { name: "Dark Matter", tag: "Dark" },
  streets: { name: "Streets", tag: "Vector" },
  satellite: { name: "Satellite", tag: "Imagery" },
  terrain: { name: "Terrain", tag: "Topo" },
};

const TIMELINE_LAYERS: WxLayer[] = [
  "wind",
  "temp",
  "precip",
  "pressure",
  "clouds",
  "humidity",
  "cape",
];

const WX_LAYER_OPTIONS: { id: WxLayer; label: string }[] = [
  { id: "wind", label: "Wind (Speed & Streamlines)" },
  { id: "temp", label: "Temperature (°C)" },
  { id: "precip", label: "Precipitation (Rain Rate)" },
  { id: "pressure", label: "Atmospheric Pressure (hPa)" },
  { id: "clouds", label: "Cloud Coverage (%)" },
  { id: "humidity", label: "Relative Humidity (%)" },
  { id: "cape", label: "CAPE Instability (J/kg)" },
  { id: "radar", label: "Doppler Weather Radar (Live)" },
  { id: "satellite", label: "Infrared Satellite (Live)" },
];

const HIGHLIGHT_IDS = [
  "lightning",
  "pred_lightning",
  "storm",
  "pred_storm",
  "cloudburst",
  "downburst",
  "fire",
  "landslide",
  "past_lightning",
  "past_storm",
  "cloud",
] as const;

const SAT_HIGHLIGHTS = new Set<string>([
  "lightning",
  "pred_lightning",
  "storm",
  "pred_storm",
  "cloudburst",
  "downburst",
  "cloud",
  "landslide",
]);

const HORIZON_H = [1, 3, 6, 12] as const;

export function SquareMap({
  dash,
  locale,
  onPick,
  focus,
  compact = false,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  onPick: (l: Location) => void;
  focus?: { center: [number, number]; zoom?: number } | null;
  compact?: boolean;
}) {
  const t = COPY[locale];
  const [basemap, setBasemap] = useState<string>("dark");
  const [wxLayer, setWxLayer] = useState<WxLayer | null>("wind");
  const [hour, setHour] = useState(0);
  const [particles, setParticles] = useState(true);
  const [grid, setGrid] = useState<WeatherGrid | null>(null);
  const [radarHost, setRadarHost] = useState("https://tilecache.rainviewer.com");
  const [radarPath, setRadarPath] = useState<string | null>(null);
  const [satPath, setSatPath] = useState<string | null>(null);
  const [zoom, setZoom] = useState(focus?.zoom || dash.map.zoom || 7);
  const [overlays, setOverlays] = useState<string[]>([]);
  const [highlights, setHighlights] = useState<string[]>([]);
  const [overlayOpacity, setOverlayOpacity] = useState(0.7);
  const [showPin, setShowPin] = useState(true);
  const [pastHours, setPastHours] = useState(6);
  const [minConfidence, setMinConfidence] = useState(0);
  const [fitNonce, setFitNonce] = useState(0);
  const [copied, setCopied] = useState(false);
  const [states, setStates] = useState<string[]>([]);
  const [state, setState] = useState("India");
  const [storm, setStorm] = useState<StormMapPack | null>(null);
  const [selected, setSelected] = useState<StormIncident | null>(null);
  const [sidebarTab, setSidebarTab] = useState<"maps" | "events">("maps");
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);

  // Collapsible Dropdown Sections inside Maps Tab
  const [openSection, setOpenSection] = useState<"weather" | "basemap" | "hazards" | "geomorph" | null>("weather");

  const rain = dash.predictive.precip_next_3d_mm;

  useEffect(() => {
    void fetchStates().then(setStates);
  }, []);

  useEffect(() => {
    let dead = false;
    void fetchWeatherGrid(hour).then((g) => {
      if (!dead && g) setGrid(g as WeatherGrid);
    });
    return () => {
      dead = true;
    };
  }, [hour]);

  useEffect(() => {
    let dead = false;
    void fetchRadarFrames().then((pack) => {
      if (dead || !pack?.ok) return;
      setRadarHost(pack.host || "https://tilecache.rainviewer.com");
      const last = pack.radar?.[pack.radar.length - 1];
      const sat = pack.satellite?.[pack.satellite.length - 1];
      setRadarPath(last?.path || null);
      setSatPath(sat?.path || null);
    });
    return () => {
      dead = true;
    };
  }, []);

  useEffect(() => {
    let dead = false;
    async function load() {
      const data = await fetchStormMap(state, pastHours);
      if (!dead && data) setStorm(data);
    }
    void load();
    const id = window.setInterval(() => void load(), 90_000);
    return () => {
      dead = true;
      window.clearInterval(id);
    };
  }, [state, pastHours]);

  const extraOverlays = overlays;
  const mapBasemap = basemap;
  const hazardEvents = useMemo(() => {
    const out: {
      id: string;
      kind: string;
      lat: number;
      lon: number;
      place?: string;
      phase?: string;
      title?: string;
      n?: number;
      frp_mw?: number;
      window_start?: string | null;
      window_end?: string | null;
    }[] = [];
    for (const w of dash.prescriptive?.warnings || []) {
      const k = String(w.kind || "").toLowerCase();
      if ((k !== "fire" && k !== "landslide") || w.lat == null || w.lon == null) continue;
      out.push({
        id: String(w.id),
        kind: k,
        lat: Number(w.lat),
        lon: Number(w.lon),
        place: w.title,
        title: w.title,
        phase: "live",
        window_start: w.window_start,
        window_end: w.window_end,
      });
    }
    return out;
  }, [dash.prescriptive?.warnings]);

  function pickIncident(inc: StormIncident) {
    setSelected(inc);
  }

  const box = useMemo(
    () => (
      <MapWrap
        lat={focus?.center[0] ?? dash.location.lat}
        lon={focus?.center[1] ?? dash.location.lon}
        label={dash.location.label}
        rainMm={rain}
        zoom={focus?.zoom ?? zoom}
        basemap={mapBasemap}
        nearby={dash.ogd?.nearby || []}
        overlays={extraOverlays}
        weatherLayer={wxLayer}
        weatherGrid={grid}
        particles={particles}
        radarUrl={
          wxLayer === "radar" && radarPath
            ? `${radarHost}${radarPath}/256/{z}/{x}/{y}/2/1_1.png`
            : wxLayer === "satellite" && satPath
              ? `${radarHost}${satPath}/256/{z}/{x}/{y}/0/0_0.png`
              : null
        }
        storm={storm}
        highlights={highlights}
        focusPin={focus ? { lat: focus.center[0], lon: focus.center[1], zoom: focus.zoom } : null}
        selectedId={selected?.id}
        tools={{ overlayOpacity, showPin, pastHours, minConfidence, fitNonce }}
        locale={locale}
        hazardEvents={hazardEvents}
        onPick={onPick}
        onSelectIncident={pickIncident}
      />
    ),
    [dash.location, rain, zoom, mapBasemap, dash.ogd?.nearby, extraOverlays, onPick, focus, storm, highlights, selected, overlayOpacity, showPin, pastHours, minConfidence, fitNonce, locale, wxLayer, grid, particles, radarHost, radarPath, satPath, hazardEvents]
  );

  function toggleOverlay(id: string) {
    setOverlays((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }

  function toggleHighlight(id: string) {
    setHighlights((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }

  function locate() {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(async (pos) => {
      try {
        const loc = await reverseGeocode(pos.coords.latitude, pos.coords.longitude);
        onPick(loc);
      } catch {
        window.alert(t.locateOutside || "That pin is outside India");
      }
    });
  }

  function copyCoords() {
    void navigator.clipboard.writeText(`${dash.location.lat.toFixed(4)}, ${dash.location.lon.toFixed(4)}`);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  const counts = (storm?.counts || {}) as Record<string, number | undefined>;
  const totalIncidents = (storm?.incidents?.length || 0) + (storm?.fires?.length || 0) + (storm?.landslides?.length || 0);

  const hlLabel: Record<(typeof HIGHLIGHT_IDS)[number], string> = {
    past_lightning: t.hlPastLightning,
    pred_lightning: t.hlPredLightning,
    past_storm: t.hlPastStorm,
    pred_storm: t.hlPredStorm,
    lightning: t.hlLiveLightning,
    storm: t.hlLiveStorm,
    cloudburst: t.cloudburst,
    downburst: t.downburst,
    fire: t.hlFire || "Forest fire",
    landslide: t.hlLandslide || "Landslide",
    cloud: t.hlColdCloud,
  };

  const processing = storm?.processing;
  const satBusy = processing?.ready === false;
  const analyzingMsg =
    processing?.message ||
    (satBusy ? t.analyzingSat || "Analyzing satellite data" : "");

  const isSidebarVisible = !sidebarCollapsed && !compact;

  // Percentage calculations for ultra-smooth custom range sliders
  const hourPct = Math.max(0, Math.min(100, ((hour + 12) / 24) * 100));
  const opacityPct = Math.max(0, Math.min(100, ((overlayOpacity - 0.2) / (0.95 - 0.2)) * 100));

  return (
    <div
      className={`grid gap-3 transition-all duration-300 ${
        isSidebarVisible
          ? "lg:grid-cols-[minmax(0,1fr)_18.5rem] xl:grid-cols-[minmax(0,1fr)_20.5rem] lg:h-[calc(100vh-11.5rem)] lg:min-h-[620px]"
          : "lg:grid-cols-1 lg:h-[calc(100vh-11.5rem)] lg:min-h-[620px]"
      }`}
    >
      {/* ── Main Map Canvas Container ── */}
      <div className="neo p-2.5 flex flex-col h-full overflow-hidden rounded-2xl border border-[var(--line)] shadow-sm bg-[var(--card)]">
        {/* Top Floating Control Toolbar */}
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2 px-1 flex-shrink-0">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1.5 bg-[color-mix(in_srgb,var(--card)_80%,transparent)] px-2.5 py-1 rounded-xl border border-[var(--line)] shadow-inner">
              <span className="text-[10px] font-black uppercase tracking-wider text-neo-muted">
                {t.stormState || "Region"}:
              </span>
              <select
                id="storm-state"
                className="bg-transparent text-xs font-bold text-neo-text outline-none cursor-pointer"
                value={state}
                aria-label={t.stormState || "Filter by state"}
                onChange={(e) => {
                  setSelected(null);
                  setState(e.target.value);
                }}
              >
                <option value="India" className="bg-[var(--card)] text-neo-text">{t.stormAllIndia || "All India"}</option>
                {(states.length ? states : []).map((s) => (
                  <option key={s} value={s} className="bg-[var(--card)] text-neo-text">
                    {s}
                  </option>
                ))}
              </select>
            </div>

            {/* Quick Map Action Pills */}
            <div className="flex items-center gap-1">
              <button
                type="button"
                className="neo-btn px-2.5 py-1 text-[11px] font-bold flex items-center gap-1 rounded-lg text-neo-text hover:border-neo-accent transition-all cursor-pointer"
                title="Fit all current hazards in view"
                onClick={() => setFitNonce((n) => n + 1)}
              >
                <span>🎯</span>
                <span className="hidden sm:inline">{t.stormFit || "Fit"}</span>
              </button>
              <button
                type="button"
                className="neo-btn px-2.5 py-1 text-[11px] font-bold flex items-center gap-1 rounded-lg text-neo-text hover:border-neo-accent transition-all cursor-pointer"
                title="Use device GPS location"
                onClick={locate}
              >
                <span>📍</span>
                <span className="hidden sm:inline">{t.locate || "Locate"}</span>
              </button>

              {/* Toggle Sidebar Button when Collapsed */}
              {sidebarCollapsed && (
                <button
                  type="button"
                  className="neo-btn px-3 py-1 text-[11px] font-black rounded-lg bg-neo-accent text-white shadow-md flex items-center gap-1.5 hover:opacity-90 animate-in fade-in duration-200 cursor-pointer ring-1 ring-white/20"
                  title="Expand Map Control Sidebar"
                  onClick={() => setSidebarCollapsed(false)}
                >
                  <span>☰</span>
                  <span>Open Tools</span>
                </button>
              )}
            </div>
          </div>

          {/* Real-time Threat Counter Chips */}
          <div className="flex items-center gap-1.5 overflow-x-auto text-[10px] font-mono font-bold text-neo-muted py-0.5">
            <span className="px-2 py-0.5 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 shadow-xs flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500 inline-block" />
              <span>Ltn: {counts.lightning ?? 0}</span>
            </span>
            <span className="px-2 py-0.5 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20 shadow-xs flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-500 inline-block" />
              <span>Pred ⚡ {counts.predicted ?? 0}</span>
            </span>
            <span className="px-2 py-0.5 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20 shadow-xs flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-purple-500 inline-block" />
              <span>Pred storm {counts.predicted_storm ?? 0}</span>
            </span>
            <span className="px-2 py-0.5 rounded-lg bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20 shadow-xs flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-rose-500 inline-block" />
              <span>Fire: {counts.fire ?? storm?.fires?.length ?? 0}</span>
            </span>
            <span className="px-2 py-0.5 rounded-lg bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/20 shadow-xs flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-teal-500 inline-block" />
              <span>Slide: {counts.landslide ?? storm?.landslides?.length ?? 0}</span>
            </span>
          </div>
        </div>

        {/* Map Viewport */}
        <div
          className="w-full flex-1 min-h-[380px] sm:min-h-[460px] overflow-hidden rounded-[18px] border border-[var(--line)] shadow-inner relative"
          role="region"
          aria-label={`${t.tabMap || "Map"} ${state}`}
        >
          {satBusy ? (
            <div className="absolute top-2 left-2 right-2 z-[700] rounded-lg bg-slate-900/80 text-amber-100 text-[11px] font-semibold px-3 py-2 pointer-events-none">
              {analyzingMsg}
            </div>
          ) : null}
          {box}
          <div className="absolute bottom-8 left-2 z-[700] rounded-md bg-slate-950/80 text-[10px] text-slate-100 px-2 py-1.5 space-y-0.5 pointer-events-none">
            {highlights.includes("lightning") ? <div>⚡ {t.hlLiveLightning}</div> : null}
            {highlights.includes("pred_lightning") ? <div>✦ {t.hlPredLightning}</div> : null}
            {highlights.includes("storm") ? <div>☁ {t.hlLiveStorm}</div> : null}
            {highlights.includes("pred_storm") ? <div>◆ {t.hlPredStorm}</div> : null}
            {highlights.includes("pred_storm") ? <div>┄ {t.hlPredStorm} area (+30 min)</div> : null}
            {highlights.includes("past_lightning") ? <div>⚡ {t.hlPastLightning}</div> : null}
            {highlights.includes("past_storm") ? <div>☁ {t.hlPastStorm}</div> : null}
            {highlights.includes("cloud") ? <div>☁ {t.hlColdCloud}</div> : null}
            {highlights.includes("cloudburst") ? <div>💧 {t.cloudburst}</div> : null}
            {highlights.includes("downburst") ? <div>↘ {t.downburst}</div> : null}
            {highlights.includes("fire") ? <div>🔥 {t.hlFire}</div> : null}
            {highlights.includes("landslide") ? <div>⛰ {t.hlLandslide}</div> : null}
          </div>
        </div>
      </div>

      {/* ── Ultra-Premium Collapsible Right Sidebar ── */}
      {isSidebarVisible && (
        <aside className="neo flex flex-col h-full max-h-[85vh] lg:max-h-full overflow-hidden rounded-2xl border border-[color-mix(in_srgb,var(--line)_70%,var(--accent)_30%)] shadow-xl bg-gradient-to-b from-[var(--card)] to-[color-mix(in_srgb,var(--card)_90%,var(--bg))] animate-in fade-in slide-in-from-right-3 duration-300">
          {/* Sidebar Sticky Header & Navigation Tabs */}
          <div className="shrink-0 p-3 border-b border-[var(--line)] bg-[color-mix(in_srgb,var(--card)_80%,var(--bg))] space-y-2.5 backdrop-blur-md">
            {/* Quick Location & Coords Status Strip + Collapse Button */}
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.9)]"></span>
                </span>
                <p className="text-xs font-black uppercase tracking-wider text-neo-text truncate" title={dash.location.label}>
                  {dash.location.district || dash.location.label}
                </p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  type="button"
                  onClick={copyCoords}
                  className="font-mono text-[10px] px-2 py-1 rounded-lg neo-btn text-neo-text hover:text-neo-accent hover:border-neo-accent transition-all flex items-center gap-1 bg-[var(--card)] shadow-xs cursor-pointer"
                  title="Copy Lat/Lon Coordinates"
                >
                  <span>{copied ? "✓ Copied" : `${dash.location.lat.toFixed(2)}, ${dash.location.lon.toFixed(2)}`}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setSidebarCollapsed(true)}
                  className="p-1 rounded-lg neo-btn text-neo-muted hover:text-rose-500 hover:border-rose-500/40 text-xs flex items-center justify-center h-7 w-7 transition-all cursor-pointer bg-[var(--card)]"
                  title="Collapse sidebar"
                  aria-label="Collapse sidebar"
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Segmented Category Tabs (Maps & Events) */}
            <div className="grid grid-cols-2 gap-1.5 p-1 rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] border border-[var(--line)] shadow-inner">
              <button
                type="button"
                onClick={() => setSidebarTab("maps")}
                className={`py-2 px-2 rounded-lg text-[11px] font-black uppercase tracking-wider flex items-center justify-center gap-2 transition-all cursor-pointer ${
                  sidebarTab === "maps"
                    ? "bg-neo-accent text-white shadow-md ring-1 ring-white/20"
                    : "text-neo-muted hover:text-neo-text"
                }`}
              >
                <span>Maps &amp; Layers</span>
              </button>

              <button
                type="button"
                onClick={() => setSidebarTab("events")}
                className={`relative py-2 px-2 rounded-lg text-[11px] font-black uppercase tracking-wider flex items-center justify-center gap-2 transition-all cursor-pointer ${
                  sidebarTab === "events"
                    ? "bg-neo-accent text-white shadow-md ring-1 ring-white/20"
                    : "text-neo-muted hover:text-neo-text"
                }`}
              >
                <span>Events</span>
                {totalIncidents > 0 && (
                  <span className="rounded-full bg-rose-500 text-white px-2 text-[9px] font-black leading-tight shadow-xs">
                    {totalIncidents}
                  </span>
                )}
              </button>
            </div>
          </div>



          {/* Scrollable Tab Content Area */}
          <div className="flex-1 overflow-y-auto p-3.5 space-y-3.5 modal-scrollbar">
            {/* ══════════════ TAB 1: MAPS & LAYERS ══════════════ */}
            {sidebarTab === "maps" && (
              <div className="space-y-3.5 animate-in fade-in duration-200">
                {/* 1. Grouped Weather Layers & Integrated Compact Live Stream */}
                <section className="p-3.5 rounded-2xl bg-[var(--card)] border border-[color-mix(in_srgb,var(--line)_70%,var(--accent)_30%)] space-y-3 shadow-sm">
                  {/* Weather Layer Header & Dropdown */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label htmlFor="weather-layer-select" className="text-[11px] font-black uppercase tracking-wider text-neo-text flex items-center gap-1.5 cursor-pointer">
                        <span className="h-2 w-2 rounded-full bg-sky-400 inline-block shadow-[0_0_6px_#38bdf8]" />
                        <span>{t.stormWeather || "Weather Layers"}</span>
                      </label>
                      {wxLayer && (
                        <button
                          type="button"
                          onClick={() => setWxLayer(null)}
                          className="text-[10px] font-bold text-rose-500 hover:underline cursor-pointer"
                        >
                          Clear Layer
                        </button>
                      )}
                    </div>

                    <div className="relative">
                      <select
                        id="weather-layer-select"
                        value={wxLayer || ""}
                        onChange={(e) => setWxLayer(e.target.value ? (e.target.value as WxLayer) : null)}
                        className="w-full neo-in p-2.5 pr-8 rounded-xl text-xs font-bold text-neo-text bg-[var(--card)] border border-[var(--line)] cursor-pointer outline-none focus:border-neo-accent transition-all appearance-none shadow-xs"
                      >
                        <option value="" className="bg-[var(--card)] text-neo-muted">
                          None (Clear Overlay)
                        </option>
                        {WX_LAYER_OPTIONS.map((opt) => (
                          <option key={opt.id} value={opt.id} className="bg-[var(--card)] text-neo-text py-1">
                            {opt.label}
                          </option>
                        ))}
                      </select>
                      <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2.5 text-neo-muted text-xs">
                        ▼
                      </div>
                    </div>
                    {/* Wind Particles Toggle */}
                    <div className="flex items-center justify-between pt-2 border-t border-[var(--line)]">
                      <span className="text-[11px] font-bold text-neo-text flex items-center gap-1.5">
                        <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 inline-block" />
                        <span>{t.windParticles || "Wind Particles"}</span>
                      </span>
                      <button
                        type="button"
                        onClick={() => setParticles((p) => !p)}
                        className={`text-[11px] px-3 py-1 rounded-lg font-black border cursor-pointer transition-all ${
                          particles
                            ? "bg-neo-accent text-white border-neo-accent shadow-xs"
                            : "bg-[var(--card)] text-neo-text hover:text-neo-accent"
                        }`}
                      >
                        {particles ? "Enabled" : "Disabled"}
                      </button>
                    </div>
                  </div>

                  {/* Compact Integrated Live Stream Scrubber (Only for timeline-supported layers) */}
                  {wxLayer && TIMELINE_LAYERS.includes(wxLayer) ? (
                    <div className="pt-3 border-t border-[var(--line)] space-y-3 animate-in fade-in duration-200">
                      {/* Compact Live Stream Status & Clock Bar */}
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          {hour === 0 ? (
                            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-[10px] font-black tracking-wider uppercase shadow-[0_0_10px_rgba(16,185,129,0.2)]">
                              <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                              </span>
                              <span>Live Stream</span>
                            </div>
                          ) : hour < 0 ? (
                            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-600 dark:text-amber-400 text-[10px] font-black tracking-wider uppercase shadow-xs">
                              <span>Replay ({hour}h)</span>
                            </div>
                          ) : (
                            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-indigo-500/15 border border-indigo-500/30 text-indigo-600 dark:text-indigo-400 text-[10px] font-black tracking-wider uppercase shadow-xs">
                              <span>Nowcast (+{hour}h)</span>
                            </div>
                          )}
                        </div>

                        <div className="font-mono text-[11px] font-black tracking-tight text-sky-400 bg-black/40 dark:bg-black/70 px-2.5 py-0.5 rounded-lg border border-sky-500/30 backdrop-blur-md shadow-inner flex items-center gap-1.5">
                          <span className="text-[9px] font-bold text-sky-400/60">IST</span>
                          <span>
                            {(() => {
                              if (grid?.valid) {
                                const iso = String(grid.valid).endsWith("Z") ? String(grid.valid) : `${String(grid.valid)}:00Z`;
                                const d = new Date(iso);
                                if (!Number.isNaN(d.getTime())) {
                                  return d.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });
                                }
                                return String(grid.valid).slice(11, 16);
                              }
                              const target = new Date(Date.now() + hour * 3600_000);
                              return target.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });
                            })()}
                          </span>
                        </div>
                      </div>

                      {/* Compact Timeline Range Slider */}
                      <div className="space-y-1.5">
                        <div className="relative h-5 flex items-center select-none group">
                          <div className="w-full h-2 rounded-full bg-slate-900/60 dark:bg-black/60 border border-slate-700/60 dark:border-white/10 shadow-inner relative overflow-hidden">
                            <div className="absolute left-0 top-0 bottom-0 w-[50%] bg-amber-500/20 border-r border-amber-500/30" />
                            <div className="absolute left-[50%] right-0 top-0 bottom-0 bg-sky-500/15" />
                            <div
                              className="absolute top-0 bottom-0 left-0 transition-all duration-75 rounded-full"
                              style={{
                                width: `${hourPct}%`,
                                background:
                                  hour === 0
                                    ? "linear-gradient(90deg, #f59e0b, #10b981)"
                                    : hour < 0
                                      ? "linear-gradient(90deg, #ef4444, #f59e0b)"
                                      : "linear-gradient(90deg, #10b981, #06b6d4, #6366f1)",
                              }}
                            />
                          </div>

                          <div
                            className="absolute h-4.5 w-4.5 -ml-2 rounded-full bg-white shadow-[0_0_12px_rgba(56,189,248,0.9)] border-2 border-sky-500 flex items-center justify-center pointer-events-none transition-transform group-hover:scale-110 z-10"
                            style={{ left: `${hourPct}%` }}
                          >
                            <div className="h-1.5 w-1.5 rounded-full bg-sky-500" />
                          </div>

                          <input
                            id="wx-hour"
                            type="range"
                            min={-12}
                            max={12}
                            step={1}
                            value={hour}
                            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-20"
                            onChange={(e) => setHour(Number(e.target.value))}
                            aria-label="Timeline scrubber"
                          />
                        </div>

                        {/* Compact Ticks */}
                        <div className="flex justify-between text-[9px] font-mono text-neo-muted px-0.5">
                          <button type="button" className="hover:text-neo-text transition-colors cursor-pointer" onClick={() => setHour(-12)}>-12h</button>
                          <button type="button" className="hover:text-neo-text transition-colors cursor-pointer" onClick={() => setHour(-6)}>-6h</button>
                          <button
                            type="button"
                            className={`font-black tracking-wider transition-colors cursor-pointer ${
                              hour === 0 ? "text-emerald-500 underline underline-offset-2" : "text-amber-500 hover:text-amber-400"
                            }`}
                            onClick={() => setHour(0)}
                          >
                            LIVE
                          </button>
                          <button type="button" className="hover:text-neo-text transition-colors cursor-pointer" onClick={() => setHour(6)}>+6h</button>
                          <button type="button" className="hover:text-neo-text transition-colors cursor-pointer" onClick={() => setHour(12)}>+12h</button>
                        </div>
                      </div>

                      {/* Compact Scale Bar */}
                      <div className="pt-2 border-t border-[var(--line)]">
                        <div className="flex justify-between items-center text-[10px] text-neo-text mb-1 font-bold">
                          <span className="uppercase tracking-wider text-neo-muted text-[8px] font-black">
                            {t[`wx_${wxLayer}`] || wxLayer} Scale
                          </span>
                          <span className="font-mono text-[9px] font-black text-sky-400 bg-sky-500/15 px-1.5 py-0.2 rounded border border-sky-500/30">
                            {unitOf(wxLayer)}
                          </span>
                        </div>
                        <div className="flex h-2.5 overflow-hidden rounded-full shadow-inner border border-black/20 dark:border-white/10">
                          {legendStops(wxLayer).map((s) => (
                            <div key={s.v} className="flex-1" style={{ background: s.color }} title={String(s.v)} />
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : wxLayer === "radar" || wxLayer === "satellite" ? (
                    <div className="pt-2.5 border-t border-[var(--line)] flex items-center justify-between text-xs animate-in fade-in duration-200">
                      <span className="inline-flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-bold text-[10px] uppercase">
                        <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                        <span>{wxLayer === "radar" ? "Doppler Radar Active" : "Infrared Sat Active"}</span>
                      </span>
                      <span className="text-[10px] text-neo-muted font-mono">
                        {wxLayer === "radar" ? "RainViewer Tile Feed" : "NASA GIBS Himawari"}
                      </span>
                    </div>
                  ) : null}
                </section>

                {/* 2. Basemap Style Section (Direct 4-chip selector without redundant dropdown) */}
                <section className="rounded-2xl bg-[var(--card)] border border-[var(--line)] shadow-sm overflow-hidden transition-all">
                  <button
                    type="button"
                    onClick={() => setOpenSection((s) => (s === "basemap" ? null : "basemap"))}
                    className="w-full p-3.5 flex items-center justify-between text-left hover:bg-[color-mix(in_srgb,var(--card)_80%,var(--bg))] transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-emerald-400 inline-block shadow-[0_0_6px_#34d399]" />
                      <span className="text-[11px] font-black uppercase tracking-wider text-neo-text">
                        {t.layers || "Basemap Style"}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs font-bold text-neo-accent">
                      <span className="text-[11px] font-black text-neo-text capitalize">{BASE_LABELS[basemap as keyof typeof BASE_LABELS]?.name || basemap}</span>
                      <span>{openSection === "basemap" ? "▲" : "▼"}</span>
                    </div>
                  </button>

                  {openSection === "basemap" && (
                    <div className="p-3.5 pt-1 border-t border-[var(--line)] space-y-2 animate-in fade-in duration-200">
                      {/* 4 Direct Basemap Chips with High Contrast Typography */}
                      <div className="grid grid-cols-2 gap-2">
                        {BASES.map((id) => {
                          const active = basemap === id;
                          return (
                            <button
                              key={id}
                              type="button"
                              className={`p-2.5 rounded-xl text-xs font-black flex items-center justify-center gap-1.5 transition-all border cursor-pointer ${
                                active
                                  ? "bg-neo-accent text-white border-neo-accent shadow-md ring-1 ring-white/30"
                                  : "bg-[var(--card)] text-neo-text hover:text-neo-accent hover:border-neo-accent"
                              }`}
                              onClick={() => setBasemap(id)}
                            >
                              <span>{BASE_LABELS[id].name}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </section>

                {/* 3. Hazard Filters & Timeline Section */}
                <section className="rounded-2xl bg-[var(--card)] border border-[var(--line)] shadow-sm overflow-hidden transition-all">
                  <button
                    type="button"
                    onClick={() => setOpenSection((s) => (s === "hazards" ? null : "hazards"))}
                    className="w-full p-3.5 flex items-center justify-between text-left hover:bg-[color-mix(in_srgb,var(--card)_80%,var(--bg))] transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-amber-400 inline-block shadow-[0_0_6px_#fbbf24]" />
                      <span className="text-[11px] font-black uppercase tracking-wider text-neo-text">
                        {t.stormHighlights || "Hazard Filters & Timeline"}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs font-bold text-neo-accent">
                      <span className="text-[10px] font-bold text-neo-muted">{highlights.length} active</span>
                      <span>{openSection === "hazards" ? "▲" : "▼"}</span>
                    </div>
                  </button>

                  {openSection === "hazards" && (
                    <div className="p-3.5 pt-1 border-t border-[var(--line)] space-y-3.5 animate-in fade-in duration-200">
                      {/* Highlight Chips with Crystal Clear Active Typography */}
                      <div>
                        <p className="text-[10px] font-black uppercase tracking-wider text-neo-text mb-1.5">
                          Active Hazard Markers
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {HIGHLIGHT_IDS.map((id) => {
                            const active = highlights.includes(id);
                            const blocked = satBusy && SAT_HIGHLIGHTS.has(id);
                            return (
                              <button
                                key={id}
                                type="button"
                                disabled={blocked}
                                title={blocked ? analyzingMsg : undefined}
                                className={`text-[11px] px-2.5 py-1.5 rounded-xl font-black transition-all border ${
                                  blocked
                                    ? "opacity-40 cursor-not-allowed bg-[var(--card)] text-neo-muted"
                                    : active
                                    ? "bg-neo-accent text-white border-neo-accent shadow-xs cursor-pointer"
                                    : "bg-[var(--card)] text-neo-text hover:text-neo-accent hover:border-[var(--line)] cursor-pointer"
                                }`}
                                aria-pressed={active}
                                onClick={() => {
                                  if (!blocked) toggleHighlight(id);
                                }}
                              >
                                {hlLabel[id]}
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      {/* Past Window & Confidence */}
                      <div className="pt-2 border-t border-[var(--line)] space-y-2.5">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-black uppercase tracking-wider text-neo-text">
                            {t.stormPastWindow || "Past Horizon"}
                          </span>
                          <div className="flex gap-1">
                            {HORIZON_H.map((h) => {
                              const active = pastHours === h;
                              return (
                                <button
                                  key={h}
                                  type="button"
                                  className={`text-[10px] px-2.5 py-1 rounded-lg font-mono font-black border cursor-pointer transition-all ${
                                    active
                                      ? "bg-neo-accent text-white border-neo-accent shadow-xs"
                                      : "bg-[var(--card)] text-neo-text hover:text-neo-accent"
                                  }`}
                                  onClick={() => setPastHours(h)}
                                >
                                  {h}h
                                </button>
                              );
                            })}
                          </div>
                        </div>

                        <div className="flex items-center justify-between pt-1.5 border-t border-[var(--line)]">
                          <span className="text-[10px] font-black uppercase tracking-wider text-neo-text">
                            {t.stormConfidence || "Confidence"}
                          </span>
                          <div className="flex gap-1">
                            {[
                              { v: 0, label: "All" },
                              { v: 0.38, label: "Med+" },
                              { v: 0.62, label: "High" },
                            ].map((opt) => {
                              const active = minConfidence === opt.v;
                              return (
                                <button
                                  key={opt.v}
                                  type="button"
                                  className={`text-[10px] px-2.5 py-1 rounded-lg font-black border cursor-pointer transition-all ${
                                    active
                                      ? "bg-neo-accent text-white border-neo-accent shadow-xs"
                                      : "bg-[var(--card)] text-neo-text hover:text-neo-accent"
                                  }`}
                                  onClick={() => setMinConfidence(opt.v)}
                                >
                                  {opt.label}
                                </button>
                              );
                            })}
                          </div>
                        </div>

                        <div className="flex items-center justify-between pt-1.5 border-t border-[var(--line)]">
                          <span className="text-[11px] font-bold text-neo-text">{t.stormPin || "Forecast Pin Marker"}</span>
                          <button
                            type="button"
                            className={`text-[11px] px-3 py-1 rounded-lg font-black border cursor-pointer transition-all ${
                              showPin
                                ? "bg-neo-accent text-white border-neo-accent shadow-xs"
                                : "bg-[var(--card)] text-neo-text hover:text-neo-accent"
                            }`}
                            onClick={() => setShowPin((v) => !v)}
                          >
                            {showPin ? "Visible" : "Hidden"}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </section>

                {/* 4. Overlays & Geomorphology Section */}
                <section className="rounded-2xl bg-[var(--card)] border border-[var(--line)] shadow-sm overflow-hidden transition-all">
                  <button
                    type="button"
                    onClick={() => setOpenSection((s) => (s === "geomorph" ? null : "geomorph"))}
                    className="w-full p-3.5 flex items-center justify-between text-left hover:bg-[color-mix(in_srgb,var(--card)_80%,var(--bg))] transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-purple-400 inline-block shadow-[0_0_6px_#c084fc]" />
                      <span className="text-[11px] font-black uppercase tracking-wider text-neo-text">
                        Overlays &amp; Geomorphology
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs font-bold text-neo-accent">
                      <span>{openSection === "geomorph" ? "▲" : "▼"}</span>
                    </div>
                  </button>

                  {openSection === "geomorph" && (
                    <div className="p-3.5 pt-1 border-t border-[var(--line)] space-y-3 animate-in fade-in duration-200">
                      {/* Satellite Overlays */}
                      <div>
                        <p className="text-[10px] font-black uppercase tracking-wider text-neo-text mb-1.5">
                          Satellite Overlays
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          <button
                            type="button"
                            className={`text-xs px-3 py-1.5 rounded-xl font-black cursor-pointer transition-all border ${
                              extraOverlays.includes("gibs_ir")
                                ? "bg-sky-500 text-white border-sky-400 shadow-sm"
                                : "bg-[var(--card)] text-neo-text hover:text-sky-400"
                            }`}
                            onClick={() => toggleOverlay("gibs_ir")}
                          >
                            Himawari IR
                          </button>
                          <button
                            type="button"
                            className={`text-xs px-3 py-1.5 rounded-xl font-black cursor-pointer transition-all border ${
                              extraOverlays.includes("gibs_imerg")
                                ? "bg-sky-500 text-white border-sky-400 shadow-sm"
                                : "bg-[var(--card)] text-neo-text hover:text-sky-400"
                            }`}
                            onClick={() => toggleOverlay("gibs_imerg")}
                          >
                            IMERG Rain
                          </button>
                        </div>
                      </div>

                      {/* Bhuvan Geomorphology */}
                      <div className="pt-2 border-t border-[var(--line)]">
                        <p className="text-[10px] font-black uppercase tracking-wider text-neo-text mb-1.5">
                          Bhuvan Geomorphology
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          <button
                            type="button"
                            className={`text-xs px-3 py-1.5 rounded-xl font-black border cursor-pointer transition-all ${
                              overlays.includes("bhuvan_geomorph")
                                ? "bg-neo-accent text-white border-neo-accent shadow-xs"
                                : "bg-[var(--card)] text-neo-text hover:text-neo-accent"
                            }`}
                            onClick={() => toggleOverlay("bhuvan_geomorph")}
                          >
                            West Bengal Basin
                          </button>
                          <button
                            type="button"
                            className={`text-xs px-3 py-1.5 rounded-xl font-black border cursor-pointer transition-all ${
                              overlays.includes("bhuvan_geomorph_in")
                                ? "bg-neo-accent text-white border-neo-accent shadow-xs"
                                : "bg-[var(--card)] text-neo-text hover:text-neo-accent"
                            }`}
                            onClick={() => toggleOverlay("bhuvan_geomorph_in")}
                          >
                            All India Geomorph
                          </button>
                        </div>
                      </div>

                      {/* Opacity Slider */}
                      <div className="pt-2 border-t border-[var(--line)] space-y-2">
                        <div className="flex items-center justify-between text-[10px] text-neo-text font-bold">
                          <span className="uppercase tracking-wider text-neo-muted text-[9px] font-black">
                            {t.stormOpacity || "Overlay Opacity"}
                          </span>
                          <span className="font-mono text-[10px] font-black text-neo-accent bg-[color-mix(in_srgb,var(--accent)_15%,transparent)] px-2 py-0.5 rounded-md border border-[color-mix(in_srgb,var(--accent)_30%,transparent)]">
                            {Math.round(overlayOpacity * 100)}%
                          </span>
                        </div>

                        <div className="relative h-5 flex items-center select-none group">
                          <div className="w-full h-2 rounded-full bg-slate-900/60 dark:bg-black/60 border border-slate-700/60 dark:border-white/10 shadow-inner relative overflow-hidden">
                            <div
                              className="absolute top-0 bottom-0 left-0 bg-gradient-to-r from-sky-500 to-indigo-500 rounded-full transition-all duration-75"
                              style={{ width: `${opacityPct}%` }}
                            />
                          </div>
                          <div
                            className="absolute h-4 w-4 -ml-2 rounded-full bg-white shadow-[0_0_10px_rgba(56,189,248,0.8)] border-2 border-sky-500 flex items-center justify-center pointer-events-none transition-transform group-hover:scale-110 z-10"
                            style={{ left: `${opacityPct}%` }}
                          />
                          <input
                            id="overlay-opacity"
                            type="range"
                            min={0.2}
                            max={0.95}
                            step={0.05}
                            value={overlayOpacity}
                            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-20"
                            onChange={(e) => setOverlayOpacity(Number(e.target.value))}
                            aria-label="Overlay opacity"
                          />
                        </div>
                      </div>
                    </div>
                  )}
                </section>
              </div>
            )}

            {/* ══════════════ TAB 2: EVENTS (LIVE STORM & INCIDENTS) ══════════════ */}
            {sidebarTab === "events" && (
              <div className="space-y-3.5 animate-in fade-in duration-200">
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-center shadow-xs">
                    <span className="text-xl font-black text-amber-500 block">{counts.lightning ?? 0}</span>
                    <span className="text-[10px] font-bold text-amber-700 dark:text-amber-300 uppercase tracking-wider">Lightning</span>
                  </div>
                  <div className="p-3 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-center shadow-xs">
                    <span className="text-xl font-black text-indigo-500 block">{counts.predicted ?? 0}</span>
                    <span className="text-[10px] font-bold text-indigo-700 dark:text-indigo-300 uppercase tracking-wider">Predicted</span>
                  </div>
                </div>

                {storm?.stale || (storm && !storm.ok && !(storm.incidents || []).length) ? (
                  <p className="text-[11px] text-amber-700 dark:text-amber-300">
                    Waiting for ingest
                    {storm.ingest_age_s != null ? ` (age ${Math.round(storm.ingest_age_s / 60)} min)` : ""}. Last-good pack shown if cached.
                  </p>
                ) : null}
                {storm?.need_second_frame ? (
                  <p className="text-[11px] text-neo-muted">Downburst needs a second IR frame (ingest ~15 min).</p>
                ) : null}

                <StormFeed
                  storm={storm}
                  locale={locale}
                  selectedId={selected?.id}
                  onSelect={pickIncident}
                  pastHours={pastHours}
                />
              </div>
            )}
          </div>
        </aside>
      )}
    </div>
  );
}
