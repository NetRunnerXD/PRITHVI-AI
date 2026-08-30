"use client";

import { useEffect, useMemo, useState } from "react";
import { COPY, type Locale } from "@/i18n/copy";
import type { DashboardSnapshot, Location } from "@/types/dashboard";
import { fetchRadarFrames, fetchStates, fetchStormMap, fetchWeatherGrid, reverseGeocode, type StormIncident, type StormMapPack } from "@/lib/api";
import { MapWrap } from "./MapWrap";
import { StormFeed } from "./StormFeed";
import { WX_LAYERS, legendStops, unitOf, type WeatherGrid, type WxLayer } from "@/lib/weatherScale";

const BASES = ["dark", "positron", "streets", "satellite", "terrain"] as const;
const HIGHLIGHT_IDS = [
  "past_lightning",
  "pred_lightning",
  "past_storm",
  "pred_storm",
  "lightning",
  "storm",
  "cloudburst",
  "downburst",
  "cloud",
] as const;

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
  const [wxLayer, setWxLayer] = useState<WxLayer>("wind");
  const [hour, setHour] = useState(0);
  const [particles, setParticles] = useState(true);
  const [grid, setGrid] = useState<WeatherGrid | null>(null);
  const [radarHost, setRadarHost] = useState("https://tilecache.rainviewer.com");
  const [radarPath, setRadarPath] = useState<string | null>(null);
  const [satPath, setSatPath] = useState<string | null>(null);
  const [zoom, setZoom] = useState(focus?.zoom || dash.map.zoom || 7);
  const [overlays, setOverlays] = useState<string[]>([]);
  const [highlights, setHighlights] = useState<string[]>([
    "past_lightning",
    "pred_lightning",
    "past_storm",
    "pred_storm",
    "lightning",
    "storm",
    "cloudburst",
    "downburst",
  ]);
  const [overlayOpacity, setOverlayOpacity] = useState(0.7);
  const [showPin, setShowPin] = useState(true);
  const [pastHours, setPastHours] = useState(6);
  const [minConfidence, setMinConfidence] = useState(0);
  const [fitNonce, setFitNonce] = useState(0);
  const [wide, setWide] = useState(true);
  const [copied, setCopied] = useState(false);
  const [states, setStates] = useState<string[]>([]);
  const [state, setState] = useState("India");
  const [storm, setStorm] = useState<StormMapPack | null>(null);
  const [selected, setSelected] = useState<StormIncident | null>(null);

  const nearby = dash.ogd?.nearby || [];
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
      const data = await fetchStormMap(state);
      if (!dead && data) setStorm(data);
    }
    void load();
    const id = window.setInterval(() => void load(), 90_000);
    return () => {
      dead = true;
      window.clearInterval(id);
    };
  }, [state]);

  const extraOverlays = overlays;
  const mapBasemap = basemap;

  const box = useMemo(
    () => (
      <MapWrap
        lat={focus?.center[0] ?? storm?.frame?.lat ?? dash.location.lat}
        lon={focus?.center[1] ?? storm?.frame?.lon ?? dash.location.lon}
        label={dash.location.label}
        rainMm={rain}
        zoom={focus?.zoom ?? zoom}
        basemap={mapBasemap}
        nearby={nearby}
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
        focusPin={selected ? { lat: selected.lat, lon: selected.lon, zoom: 8 } : focus ? { lat: focus.center[0], lon: focus.center[1], zoom: focus.zoom } : null}
        selectedId={selected?.id}
        tools={{ overlayOpacity, showPin, pastHours, minConfidence, fitNonce }}
        locale={locale}
        onPick={onPick}
      />
    ),
    [dash.location, rain, zoom, mapBasemap, nearby, extraOverlays, onPick, focus, storm, highlights, selected, overlayOpacity, showPin, pastHours, minConfidence, fitNonce, locale, wxLayer, grid, particles, radarHost, radarPath, satPath]
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

  const counts = storm?.counts || {};
  const hlLabel: Record<(typeof HIGHLIGHT_IDS)[number], string> = {
    past_lightning: t.hlPastLightning,
    pred_lightning: t.hlPredLightning,
    past_storm: t.hlPastStorm,
    pred_storm: t.hlPredStorm,
    lightning: t.hlLiveLightning,
    storm: t.hlLiveStorm,
    cloudburst: t.cloudburst,
    downburst: t.downburst,
    cloud: t.hlColdCloud,
  };

  function pickIncident(inc: StormIncident) {
    setSelected(inc);
  }

  return (
    <div className={`grid gap-3 ${wide && !compact ? "lg:grid-cols-[minmax(0,1fr)_18rem]" : "lg:grid-cols-1"}`}>
      <div className="neo p-2">
        <div className="mb-2 flex flex-wrap items-center gap-2 px-1">
          <label className="text-[11px] font-bold uppercase tracking-wide text-neo-muted" htmlFor="storm-state">
            {t.stormState || "State"}
          </label>
          <select
            id="storm-state"
            className="neo-in px-2 py-1 text-xs"
            value={state}
            aria-label={t.stormState || "Filter by state"}
            onChange={(e) => {
              setSelected(null);
              setState(e.target.value);
            }}
          >
            <option value="India">{t.stormAllIndia || "All India"}</option>
            {(states.length ? states : []).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <span className="text-[11px] text-neo-muted" role="status" aria-live="polite">
            past ⚡ {counts.past_lightning ?? 0} · pred ⚡ {counts.predicted ?? 0} · past storm {counts.past_storm ?? 0} · pred storm {counts.predicted_storm ?? 0}
          </span>
        </div>
        <div
          className={`w-full overflow-hidden rounded-[16px] ${compact ? "h-[min(420px,50vh)]" : wide ? "h-[min(640px,70vh)]" : "aspect-square max-h-[520px]"}`}
          role="region"
          aria-label={`${t.tabMap || "Map"} ${state}`}
        >
          {box}
        </div>
      </div>
      <div className="space-y-3">
        <section className="neo p-3">
          <p className="text-[11px] font-bold uppercase tracking-wide text-neo-muted">{t.layers}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {BASES.map((id) => (
              <button key={id} className={`neo-btn text-xs capitalize ${basemap === id ? "neo-btn-on" : ""}`} onClick={() => setBasemap(id)}>
                {id}
              </button>
            ))}
          </div>
        </section>
        <section className="neo p-3">
          <p className="text-[11px] font-bold uppercase tracking-wide text-neo-muted" id="storm-wx-label">
            {t.stormWeather || "Weather layers"}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5" role="group" aria-labelledby="storm-wx-label">
            {WX_LAYERS.map((id) => (
              <button
                key={id}
                type="button"
                className={`neo-btn text-xs ${wxLayer === id ? "neo-btn-on" : ""}`}
                onClick={() => setWxLayer(id)}
              >
                {t[`wx_${id}`] || id}
              </button>
            ))}
          </div>
          <label className="mt-2 flex items-center gap-2 text-[11px] text-neo-muted">
            <input type="checkbox" checked={particles} onChange={(e) => setParticles(e.target.checked)} />
            {t.wxParticles || "Wind particles"}
          </label>
          <label className="mt-2 block text-[11px] text-neo-muted" htmlFor="wx-hour">
            {t.wxHour || "Forecast hour"} +{hour}h
            {grid?.valid ? ` · ${String(grid.valid).slice(11, 16)} IST` : ""}
          </label>
          <input
            id="wx-hour"
            type="range"
            min={0}
            max={23}
            value={hour}
            className="mt-1 w-full"
            onChange={(e) => setHour(Number(e.target.value))}
          />
          <div className="mt-2">
            <p className="text-[10px] text-neo-muted">
              {t[`wx_${wxLayer}`] || wxLayer} {unitOf(wxLayer)}
            </p>
            <div className="mt-1 flex h-2 overflow-hidden rounded-full">
              {legendStops(wxLayer).map((s) => (
                <div key={s.v} className="flex-1" style={{ background: s.color }} title={String(s.v)} />
              ))}
            </div>
            <div className="mt-0.5 flex justify-between font-mono text-[9px] text-neo-muted">
              {legendStops(wxLayer).filter((_, i, a) => i === 0 || i === a.length - 1 || i === Math.floor(a.length / 2)).map((s) => (
                <span key={s.v}>{s.v}</span>
              ))}
            </div>
          </div>
          <p className="mt-1 text-[10px] text-neo-muted">{grid?.note || t.wxModelHint}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <button className={`neo-btn text-xs ${extraOverlays.includes("gibs_ir") ? "neo-btn-on" : ""}`} onClick={() => toggleOverlay("gibs_ir")}>
              {t.wxGibsIr || "Himawari IR"}
            </button>
            <button className={`neo-btn text-xs ${extraOverlays.includes("gibs_imerg") ? "neo-btn-on" : ""}`} onClick={() => toggleOverlay("gibs_imerg")}>
              IMERG
            </button>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <button type="button" className="neo-btn text-xs" aria-label="Zoom in" onClick={() => setZoom((z) => Math.min(14, z + 1))}>+</button>
            <button type="button" className="neo-btn text-xs" aria-label="Zoom out" onClick={() => setZoom((z) => Math.max(5, z - 1))}>−</button>
            <button className="neo-btn text-xs" onClick={() => setZoom(8)}>{t.reset}</button>
            <button className="neo-btn text-xs" onClick={() => setFitNonce((n) => n + 1)}>{t.stormFit || "Fit events"}</button>
            <button className="neo-btn text-xs" onClick={locate}>{t.locate}</button>
            <button className="neo-btn text-xs" onClick={() => setWide((v) => !v)}>{t.fullscreen}</button>
            <button className={`neo-btn text-xs ${showPin ? "neo-btn-on" : ""}`} onClick={() => setShowPin((v) => !v)}>
              {t.stormPin || "Forecast pin"}
            </button>
          </div>
          <label className="mt-2 block text-[11px] text-neo-muted" htmlFor="overlay-opacity">
            {t.stormOpacity || "Overlay opacity"} {Math.round(overlayOpacity * 100)}%
          </label>
          <input
            id="overlay-opacity"
            type="range"
            min={0.2}
            max={0.95}
            step={0.05}
            value={overlayOpacity}
            className="mt-1 w-full"
            onChange={(e) => setOverlayOpacity(Number(e.target.value))}
          />
          <p className="mt-2 text-[11px] font-bold uppercase tracking-wide text-neo-muted">{t.stormPastWindow || "Past window"}</p>
          <div className="mt-1 flex flex-wrap gap-1.5" role="group" aria-label={t.stormPastWindow || "Past window"}>
            {[1, 3, 6].map((h) => (
              <button key={h} type="button" className={`neo-btn text-xs ${pastHours === h ? "neo-btn-on" : ""}`} onClick={() => setPastHours(h)}>
                {h}h
              </button>
            ))}
          </div>
          <p className="mt-2 text-[11px] font-bold uppercase tracking-wide text-neo-muted">{t.stormConfidence || "Predicted confidence"}</p>
          <div className="mt-1 flex flex-wrap gap-1.5" role="group" aria-label={t.stormConfidence || "Predicted confidence"}>
            {[
              { v: 0, label: t.stormConfAll || "Any" },
              { v: 0.38, label: t.stormConfMed || "Medium+" },
              { v: 0.62, label: t.stormConfHigh || "High" },
            ].map((opt) => (
              <button key={opt.v} type="button" className={`neo-btn text-xs ${minConfidence === opt.v ? "neo-btn-on" : ""}`} onClick={() => setMinConfidence(opt.v)}>
                {opt.label}
              </button>
            ))}
          </div>
          <p className="mt-2 font-mono text-[11px] text-neo-muted">
            {dash.location.lat.toFixed(4)}, {dash.location.lon.toFixed(4)}
          </p>
          <button className="neo-btn mt-1 text-xs" onClick={copyCoords}>
            {copied ? t.copied : t.copyCoords}
          </button>
        </section>
        <section className="neo p-3">
          <p className="text-[11px] font-bold uppercase tracking-wide text-neo-muted" id="storm-hi-label">
            {t.stormHighlights || "Highlights"}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5" role="group" aria-labelledby="storm-hi-label">
            {HIGHLIGHT_IDS.map((id) => (
              <button
                key={id}
                type="button"
                className={`neo-btn text-xs ${highlights.includes(id) ? "neo-btn-on" : ""}`}
                aria-pressed={highlights.includes(id)}
                onClick={() => toggleHighlight(id)}
              >
                {hlLabel[id]}
              </button>
            ))}
          </div>
          <ul className="mt-2 space-y-0.5 text-[11px] text-neo-muted">
            <li>⚡ {t.hlPastLightning}</li>
            <li>⚡ {t.hlLiveLightning}</li>
            <li>✦ {t.hlPredLightning}</li>
            <li>◆ {t.hlPredStorm}</li>
          </ul>
        </section>
        <StormFeed storm={storm} locale={locale} selectedId={selected?.id} onSelect={pickIncident} />
        {selected ? (
          <section className="neo p-3" aria-live="polite">
            <p className="text-[11px] font-bold uppercase tracking-wide text-neo-muted">{t.details || "Details"}</p>
            <p className="mt-1 text-sm font-semibold">{selected.kind} · {selected.place}</p>
            <p className="mt-1 font-mono text-[11px] text-neo-muted">
              {selected.lat.toFixed(3)}, {selected.lon.toFixed(3)}
            </p>
            <p className="mt-1 text-xs capitalize text-neo-muted">{selected.phase || "live"}</p>
            {selected.phase === "predicted" || (selected.lead_min || 0) > 0 ? (
              <p className="mt-1 text-xs text-neo-accent">
                {t.stormPredicted || "Predicted"}
                {selected.lead_min ? ` +${selected.lead_min} min` : ""}
                {selected.confidence != null ? ` · ${t.stormConfidence || "confidence"} ${(selected.confidence * 100).toFixed(0)}% (${selected.confidence_band || "—"})` : ""}
              </p>
            ) : null}
            {selected.p_lightning != null ? (
              <p className="mt-1 text-xs">P(lightning) {(selected.p_lightning * 100).toFixed(0)}%</p>
            ) : null}
            {selected.p_cloudburst != null ? (
              <p className="text-xs">P(cloudburst) {(selected.p_cloudburst * 100).toFixed(0)}%</p>
            ) : null}
            {selected.rain_ir_mm_h != null ? <p className="text-xs">{selected.rain_ir_mm_h} mm/h IR</p> : null}
            <p className="mt-1 text-[11px] text-neo-muted">{selected.engine || "cv-nowcast"} · map focus only</p>
          </section>
        ) : null}
        <section className="neo p-3">
          <p className="text-[11px] font-bold uppercase tracking-wide text-neo-muted">{t.bhuvan}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <button className={`neo-btn text-xs ${overlays.includes("bhuvan_geomorph") ? "neo-btn-on" : ""}`} onClick={() => toggleOverlay("bhuvan_geomorph")}>
              WB
            </button>
            <button className={`neo-btn text-xs ${overlays.includes("bhuvan_geomorph_in") ? "neo-btn-on" : ""}`} onClick={() => toggleOverlay("bhuvan_geomorph_in")}>
              IN
            </button>
          </div>
        </section>
        <section className="neo p-3">
          <p className="text-[11px] font-bold uppercase tracking-wide text-neo-muted">{t.nearbyList}</p>
          <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto text-sm">
            {nearby.map((n) => (
              <li key={n.id}>
                <button className="w-full rounded-lg px-2 py-1 text-left hover:bg-neo-bg" onClick={() => onPick(n)}>
                  {n.district}
                  <span className="ml-2 font-mono text-[10px] text-neo-muted">{n.lat.toFixed(2)}, {n.lon.toFixed(2)}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
