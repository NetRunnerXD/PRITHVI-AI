"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardSnapshot } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";
import { useApp } from "@/lib/store";
import { dist, rain, rainUnit, speed, temp, tempUnit } from "@/lib/units";

function hhmm(t: string) {
  const i = t.indexOf("T");
  return i >= 0 ? t.slice(i + 1, i + 6) : t.slice(-5);
}

function weekday(iso?: string) {
  if (!iso) return "—";
  const d = new Date(iso.includes("T") ? iso : `${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso.slice(5) : d.toLocaleDateString("en-IN", { weekday: "short" });
}

function feelsLikeC(tempC?: number | null, rh?: number | null) {
  if (tempC == null) return null;
  const t = Number(tempC);
  const h = Number(rh ?? 50);
  if (t < 26) return t;
  const hi =
    -8.784695 +
    1.61139411 * t +
    2.338549 * h -
    0.14611605 * t * h -
    0.012308094 * t * t -
    0.016424828 * h * h +
    0.002211732 * t * t * h +
    0.00072546 * t * h * h -
    0.000003582 * t * t * h * h;
  return Math.round(hi * 10) / 10;
}

const tip = {
  background: "var(--card)",
  border: "1px solid var(--line)",
  borderRadius: 12,
  fontSize: 12,
  color: "var(--text)",
};

// ── Suggestion severity helper ──────────────────────────────────────
function suggestionLevel(id: string, v: string): "ok" | "watch" | "alert" | "danger" {
  const val = v.toLowerCase().trim();
  if (val === "quiet" || val === "0" || val === "—") return "ok";
  if (val === "watch") return "watch";
  if (val === "warning" || val === "alert") return "alert";
  if (val === "danger" || val === "extreme") return "danger";
  // numeric heuristics
  const num = parseFloat(val);
  if (!isNaN(num)) {
    if (id === "flood" || id === "drought" || id === "heat") {
      if (num >= 75) return "danger";
      if (num >= 50) return "alert";
      if (num >= 25) return "watch";
      return "ok";
    }
    if (id === "uv") {
      if (num >= 11) return "danger";
      if (num >= 8) return "alert";
      if (num >= 3) return "watch";
      return "ok";
    }
    if (id === "fish") {
      if (num > 3) return "danger";
      if (num > 2) return "alert";
      if (num > 1) return "watch";
      return "ok";
    }
    if (num > 0) return "watch";
  }
  return "watch"; // non-empty, non-quiet = watch
}

const suggLevel: Record<string, { bg: string; text: string; dot: string }> = {
  ok: { bg: "bg-[color-mix(in_srgb,var(--accent)_10%,transparent)]", text: "text-neo-accent", dot: "bg-[var(--accent)]" },
  watch: { bg: "bg-[color-mix(in_srgb,var(--warn)_12%,transparent)]", text: "text-neo-warn", dot: "bg-[var(--warn)]" },
  alert: { bg: "bg-[color-mix(in_srgb,var(--accent2)_12%,transparent)]", text: "text-neo-accent2", dot: "bg-[var(--accent2)]" },
  danger: { bg: "bg-[color-mix(in_srgb,var(--danger)_12%,transparent)]", text: "text-neo-danger", dot: "bg-[var(--danger)]" },
};

// Alert severity colors for the sidebar panel
const alertTone: Record<string, string> = {
  extreme: "border-l-[var(--danger)] bg-[color-mix(in_srgb,var(--danger)_7%,transparent)]",
  warning: "border-l-[var(--warn)]   bg-[color-mix(in_srgb,var(--warn)_7%,transparent)]",
  alert: "border-l-[var(--accent2)] bg-[color-mix(in_srgb,var(--accent2)_6%,transparent)]",
  watch: "border-l-[var(--accent)]  bg-[color-mix(in_srgb,var(--accent)_6%,transparent)]",
};
const alertDot: Record<string, string> = {
  extreme: "text-neo-danger",
  warning: "text-neo-warn",
  alert: "text-neo-accent2",
  watch: "text-neo-accent",
};

export function OverviewLive({ dash, locale, onNavigateData }: { dash: DashboardSnapshot; locale: Locale; onNavigateData?: (subTab: string) => void }) {
  const t = COPY[locale];
  const units = useApp((s) => s.settings.units);
  const live = dash.live;
  const sky = live?.sky || {};
  const wind = live?.wind || {};
  const rose = wind.rose || [];
  const cur = dash.descriptive.current;
  const series = dash.descriptive.series;

  const todayRain =
    dash.predictive.outlook_days?.[0]?.precip_mm ??
    series.precip_daily?.[0]?.value ??
    sky.precip_1h_mm ??
    null;
  const feels = feelsLikeC(sky.temp_c ?? cur.temp_c, sky.humidity_pct ?? cur.humidity_pct);

  const hourly = (series.temp_hourly || []).slice(0, 18).map((p, i) => ({
    t: hhmm(p.t),
    temp: p.value,
    rain: series.precip_hourly?.[i]?.value ?? 0,
    wind: series.wind_hourly?.[i]?.value ?? 0,
  }));
  const days = (dash.predictive.outlook_days || []).slice(0, 7);

  const sixHour = (dash.predictive.hourly || []).slice(0, 6).map((h) => ({
    t: h.hour || hhmm(h.t),
    rain: h.precip_mm ?? 0,
    temp: h.temp_c ?? 0,
    wind: h.wind_kmh ?? 0,
  }));
  const sixFromSeries = hourly.slice(0, 6);
  const six = sixHour.length ? sixHour : sixFromSeries;

  const allAlerts = (() => {
    const raw = dash.prescriptive.warnings || [];
    const seen = new Set<string>();
    const out: typeof raw = [];

    for (const w of raw) {
      const lowTitle = (w.title || "").toLowerCase().trim();
      const lowBody = (w.body || "").toLowerCase().trim();
      const combined = `${lowTitle} ${lowBody}`;

      // Filter out negative non-threat bulletins
      if (w.hazard === "tsunami" && /no threat|does not exist|all clear|nil/.test(combined)) continue;
      if (w.hazard === "seismic" && /no damage|no threat|all clear/.test(combined)) continue;
      if (!["extreme", "warning", "alert", "watch"].includes(w.severity)) continue;

      // Normalize key for deduplication
      const normTitle = lowTitle.replace(/[^a-z0-9]/g, "");
      const normBody = lowBody.slice(0, 40).replace(/[^a-z0-9]/g, "");
      const key = `${w.hazard || "gen"}_${normTitle}_${normBody}`;

      if (seen.has(key) || seen.has(normTitle)) continue;
      seen.add(key);
      seen.add(normTitle);

      // Clean up body so it doesn't just duplicate the title verbatim
      let cleanBody = (w.body || "").trim();
      if (cleanBody.toLowerCase() === lowTitle || cleanBody.length < 3) {
        cleanBody = "";
      }

      out.push({
        ...w,
        body: cleanBody,
      });
    }

    return out.slice(0, 24);
  })();

  return (
    <div className="space-y-3">
      {/* ── Row 1: Sky and Rainfall — merged full width ── */}
      <section
        className="neo sky-card relative overflow-hidden p-5 cursor-pointer hover:ring-2 hover:ring-[var(--accent)] transition-all"
        onClick={() => onNavigateData?.('meteorology')}
      >
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Sky and Rainfall</p>
        <div className="mt-3 grid gap-5 lg:grid-cols-12">
          {/* Sky side */}
          <div className="lg:col-span-7">
            <div className="flex items-center gap-4">
              <SkyGlyph kind={sky.kind || cur.sky_kind || "cloud"} day={sky.is_day !== false} />
              <div className="min-w-0">
                <p className="text-2xl font-extrabold leading-tight">{sky.label || cur.sky_label || "—"}</p>
                <p className="mt-1 font-mono text-4xl font-bold text-neo-accent">
                  {temp(sky.temp_c ?? cur.temp_c, units)}
                </p>
                <p className="mt-1 text-xs text-neo-muted">
                  {sky.is_day ? t.day : t.night}
                  {feels != null ? ` · feels ${temp(feels, units)}` : ""}
                  {sky.place ? ` · ${sky.place}` : ""}
                </p>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <Stat k={`${t.humidity}`} v={sky.humidity_pct != null ? `${Math.round(Number(sky.humidity_pct))} %` : "—"} />
              <Stat k={t.cloud} v={sky.cloud_cover_pct != null ? `${Math.round(Number(sky.cloud_cover_pct))} %` : "—"} />
              <Stat k={t.visibility} v={sky.visibility_km != null ? dist(sky.visibility_km, units) : "—"} />
              <Stat k={t.lastHourRain} v={rain(sky.precip_1h_mm, units)} />
            </div>
          </div>
          {/* Divider */}
          <div className="hidden lg:block lg:col-span-1 border-l border-[var(--line)] self-stretch mx-auto" />
          {/* Rainfall side */}
          <div className="lg:col-span-4">
            <p className="text-[10px] uppercase tracking-widest text-neo-muted">{t.rainToday}</p>
            <p className="mt-1 font-mono text-4xl font-extrabold text-neo-accent">
              {todayRain != null ? rain(todayRain, units) : "—"}
            </p>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <Stat k={t.rain3} v={rain(dash.predictive.precip_next_3d_mm, units)} />
              <Stat k={t.rain7} v={rain(dash.predictive.precip_7d_mm, units)} />
              <RainOdds
                k={t.chanceOfRain}
                pct={(dash.predictive.precip_probability_pct || []).slice(0, 3)}
                days={[t.day1, t.day2, t.day3]}
              />
              <Stat k={t.balance} v={rain(dash.predictive.water_balance_7d_mm, units)} />
            </div>
          </div>
        </div>
      </section>

      {/* ── Row 2: (Wind + Next 6h + 7-day forecast) on left & Alerts on right ── */}
      <div className="grid gap-3 lg:grid-cols-12 items-stretch">
        {/* Left column: Wind + 6h row & 7-day forecast */}
        <div className="space-y-3 lg:col-span-8 flex flex-col justify-between">
          {/* Wind + Next 6h */}
          <div className="grid gap-3 sm:grid-cols-12">
            {/* Wind panel */}
            <section 
              className="neo p-4 sm:col-span-5 cursor-pointer hover:ring-2 hover:ring-[var(--accent)] transition-all"
              onClick={() => onNavigateData?.('meteorology')}
            >
              <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.windProfile}</p>
              <div className="flex items-center gap-3">
                <WindRose
                  fromDeg={wind.direction_deg ?? null}
                  flowDeg={wind.flow_deg ?? null}
                  rose={rose}
                  compass={wind.compass || "—"}
                  flow={wind.flow_compass || "—"}
                />
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div>
                    <p className="text-[10px] uppercase tracking-widest text-neo-muted">Speed</p>
                    <p className="font-mono text-2xl font-bold text-neo-accent">{speed(wind.speed_kmh, units)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-widest text-neo-muted">Direction</p>
                    <p className="text-sm font-semibold">
                      {wind.compass || "—"}
                      <span className="mx-1 text-neo-muted">→</span>
                      {wind.flow_compass || "—"}
                    </p>
                  </div>
                  {wind.direction_deg != null && (
                    <div className="flex items-center gap-1.5">
                      <span
                        className="inline-block h-3.5 w-3.5 rounded-full border-2 border-[var(--accent)] bg-[color-mix(in_srgb,var(--accent)_15%,transparent)]"
                        style={{ transform: `rotate(${wind.direction_deg}deg)` }}
                        aria-hidden
                      />
                      <span className="text-[11px] text-neo-muted">{wind.direction_deg}°</span>
                    </div>
                  )}
                </div>
              </div>
              {wind.hourly && wind.hourly.length > 0 && (
                <div className="mt-3 h-14">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={wind.hourly.slice(0, 8).map((h) => ({ t: hhmm(h.t), v: units === "imperial" ? h.speed * 0.621 : h.speed }))}>
                      <XAxis dataKey="t" stroke="var(--muted)" fontSize={8} />
                      <Tooltip contentStyle={tip} />
                      <Bar dataKey="v" fill="var(--accent)" radius={[3, 3, 0, 0]} opacity={0.75} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </section>

            {/* Next 6h */}
            <section className="neo p-4 sm:col-span-7 flex flex-col justify-between">
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.next6h}</p>
              {six.length ? (
                <div className="mt-2 grid grid-cols-6 gap-1">
                  {six.map((h) => (
                    <div key={h.t} className="neo-in flex flex-col items-center gap-0.5 rounded-xl py-1.5 text-center">
                      <p className="text-[9px] font-semibold text-neo-muted">{h.t}</p>
                      <p className="font-mono text-xs font-bold text-neo-accent">{temp(h.temp, units)}</p>
                      <p className="text-[10px] font-mono text-neo-rain">{rain(h.rain, units)}</p>
                      <p className="text-[9px] text-neo-muted">{speed(h.wind, units)}</p>
                    </div>
                  ))}
                </div>
              ) : null}
              <div className="mt-2 h-20">
                {six.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={six}>
                      <CartesianGrid stroke="var(--line)" vertical={false} />
                      <XAxis dataKey="t" stroke="var(--muted)" fontSize={8} />
                      <YAxis stroke="var(--muted)" fontSize={8} width={20} />
                      <Tooltip contentStyle={tip} />
                      <Bar dataKey="rain" fill="var(--rain)" radius={[3, 3, 0, 0]} name="Rain" />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="flex h-full items-center justify-center text-xs text-neo-muted">—</p>
                )}
              </div>
            </section>
          </div>

          {/* 7-day Forecast */}
          <section className="neo p-4">
            <p className="mb-2.5 text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.forecast7}</p>
            <div className="grid grid-cols-4 gap-1.5 sm:grid-cols-7">
              {days.map((d) => (
                <div key={d.date} className="neo-in flex flex-col items-center gap-0.5 rounded-xl py-2 text-center">
                  <p className="text-[10px] font-bold">{weekday(d.date)}</p>
                  <p className="mt-0.5 font-mono text-xs font-extrabold">{temp(d.temp_max_c, units)}</p>
                  <p className="text-[9px] text-neo-muted">{temp(d.temp_min_c, units)}</p>
                  <div className="my-0.5 h-px w-6 rounded-full bg-[var(--line)]" />
                  <p className="font-mono text-[10px] font-semibold text-neo-rain">{rain(d.precip_mm, units)}</p>
                  <p className="text-[9px] text-neo-muted">{d.precip_prob_pct ?? 0}%</p>
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* Alerts sidebar — expanded height with scrollable list */}
        <aside 
          className="neo flex flex-col lg:col-span-4 lg:h-[25.5rem] lg:max-h-[25.5rem] overflow-hidden cursor-pointer hover:ring-2 hover:ring-[var(--danger)] transition-all"
          onClick={() => onNavigateData?.('risks')}
        >
          {/* Header */}
          <div className="flex shrink-0 items-center gap-2 border-b border-[var(--line)] px-3.5 py-2.5">
            <span className="live-dot" aria-hidden />
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.alertsPanel}</p>
            {allAlerts.length > 0 && (
              <span className="ml-auto rounded-full bg-[color-mix(in_srgb,var(--danger)_15%,transparent)] px-2 py-0.5 text-[10px] font-bold text-neo-danger">
                {allAlerts.length}
              </span>
            )}
          </div>
          {/* Scrollable list */}
          <ul className="min-h-0 flex-1 space-y-2 overflow-y-auto p-2.5">
            {allAlerts.length === 0 ? (
              <li className="flex h-full items-center justify-center text-sm text-neo-muted">{t.allClear}</li>
            ) : (
              allAlerts.map((w) => (
                <li
                  key={w.id}
                  className={`rounded-xl border-l-[3px] px-2.5 py-2 ${alertTone[w.severity] ?? "border-l-[var(--line)]"}`}
                >
                  <div className="flex items-center gap-2">
                    <p className={`text-[9px] font-bold uppercase tracking-widest ${alertDot[w.severity] ?? "text-neo-muted"}`}>
                      {w.severity}
                    </p>
                    {w.scope === "india" ? (
                      <span className="chip ml-auto text-[9px] px-1.5 py-0">India</span>
                    ) : w.hazard ? (
                      <span className="chip ml-auto text-[9px] px-1.5 py-0 capitalize">
                        {w.hazard === "seismic" ? "Earthquake" : w.hazard === "air" ? "Air Quality" : w.hazard}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-0.5 text-xs font-semibold leading-snug">{w.title}</p>
                  {w.body ? (
                    <p className="mt-0.5 line-clamp-2 text-[10px] leading-snug text-neo-muted">{w.body}</p>
                  ) : null}
                </li>
              ))
            )}
          </ul>
        </aside>
      </div>

      <HomeHazardStrip dash={dash} locale={locale} onNavigateData={onNavigateData} />
    </div>
  );
}

function AlertStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="neo-in rounded-xl px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-widest text-neo-muted">{label}</p>
      <p className="mt-0.5 truncate font-mono text-xs font-semibold">{value}</p>
    </div>
  );
}

function HomeHazardStrip({ dash, locale, onNavigateData }: { dash: DashboardSnapshot; locale: Locale; onNavigateData?: (subTab: string) => void }) {
  const t = COPY[locale];
  const q = dash.quality || {};
  const air = (q.air || {}) as Record<string, unknown>;
  const climate = (q.climate || {}) as Record<string, unknown>;
  const marine = (q.marine || {}) as Record<string, unknown>;
  const pollen = ((air.pollen || {}) as Record<string, unknown>);
  const flood = (q.flood || {}) as Record<string, unknown>;
  const seismic = (q.seismic || dash.live?.quakes || []) as Record<string, unknown>[];
  const tsunami = (q.tsunami || dash.live?.tsunami || []) as Record<string, unknown>[];
  const gdacs = (q.gdacs || []) as Record<string, unknown>[];
  const conv = dash.science?.nowcast?.convective;
  const vera = dash.predictions?.vera;
  const risk = (id: string) => dash.risks.find((r) => r.id === id);

  const aqiNum = dash.descriptive.current.aqi ?? air.us_aqi;
  const aqiQuality =
    aqiNum == null
      ? "—"
      : Number(aqiNum) <= 50
        ? "Good"
        : Number(aqiNum) <= 100
          ? "Moderate"
          : Number(aqiNum) <= 200
            ? "Unhealthy"
            : "Very Poor";

  const cards = [
    {
      title: "Air",
      rows: [
        ["AQI", String(aqiNum ?? "—")],
        ["Quality", aqiQuality],
        ["PM2.5", String(air.pm2_5 ?? "—")],
        ["Grass Pollen", String(pollen.grass ?? "—")],
        ["Ragweed Pollen", String(pollen.ragweed ?? "—")],
      ],
    },
    {
      title: t.landWeather,
      rows: [
        ["Maximum Temperature", String(climate.temp_max ?? "—")],
        ["Relative Humidity", String(climate.rh_now ?? "—")],
        ["Soil Moisture", String(climate.soil_m_0_1 ?? dash.descriptive.current.soil_moisture_m3m3 ?? "—")],
      ],
    },
    {
      title: t.marineWeather,
      rows: [
        ["Wave Height", String(marine.wave_height_m ?? "—")],
        ["Sea Surface Temperature", String(marine.sst_c ?? "—")],
        ["Swell", String(marine.swell_height_m ?? "—")],
      ],
    },
  ];

  const aqiVal = dash.descriptive.current.aqi ?? air.us_aqi;
  const floodPct = Number(risk("flood")?.score_pct ?? flood.score_pct ?? 0);
  const droughtPct = Number(risk("drought")?.score_pct ?? 0);
  const heatLvl = String(vera?.extremes?.heat_wave?.level ?? "");
  const tmax = climate.temp_max ?? dash.descriptive.current.temp_c;
  const vis = dash.descriptive.current.visibility_km;
  const uv = Number(air.uv_index ?? climate.uv_index_max ?? climate.uv_index ?? 0);
  const waveM = Number(marine.wave_height_m);
  const pond = dash.science?.nowcast?.ponding?.mm_60;
  const light = conv?.lightning;
  const suggestions: { id: string; label: string; status: string; metric: string; raw: string; tab: string }[] = [
    {
      id: "lightning",
      label: "Lightning",
      status: String(light?.level || "quiet") === "quiet" ? "All clear" : Number(light?.score_pct) >= 50 ? "Active storm" : "Isolated strikes",
      metric: light?.score_pct != null ? `${light.score_pct}% of recent cells` : "No strikes scored",
      raw: String(light?.level ?? light?.score_pct ?? "quiet"),
      tab: "meteorology",
    },
    {
      id: "cloudburst",
      label: "Cloudburst",
      status: String(conv?.cloudburst?.level ?? "quiet") === "quiet" ? "Unlikely" : "Watch this hour",
      metric: conv?.cloudburst?.score_pct != null ? `${conv.cloudburst.score_pct}% nowcast score` : "Local nowcast",
      raw: String(conv?.cloudburst?.level ?? "quiet"),
      tab: "meteorology",
    },
    {
      id: "cyclone",
      label: "Cyclone",
      status: gdacs.some((g) => String(g.event_type) === "TC") ? "System in basin" : "No cyclone",
      metric: gdacs.filter((g) => String(g.event_type) === "TC")[0]
        ? String(gdacs.filter((g) => String(g.event_type) === "TC")[0]?.title || "GDACS")
        : "Bay / Arabian Sea quiet",
      raw: gdacs.some((g) => String(g.event_type) === "TC") ? "watch" : "quiet",
      tab: "hydrology",
    },
    {
      id: "flood",
      label: "Flood",
      status: floodPct >= 70 ? "High risk" : floodPct >= 40 ? "Rising" : "Low risk",
      metric: `${Number.isFinite(floodPct) ? Math.round(floodPct) : "—"}% model score`,
      raw: String(floodPct),
      tab: "hydrology",
    },
    {
      id: "drought",
      label: "Drought",
      status: droughtPct >= 60 ? "Dry spell" : droughtPct >= 35 ? "Below normal" : "Soil OK",
      metric: `${Number.isFinite(droughtPct) ? Math.round(droughtPct) : "—"}% deficit score`,
      raw: String(droughtPct),
      tab: "risks",
    },
    {
      id: "heat",
      label: "Heat",
      status: /warning|watch/i.test(heatLvl) ? heatLvl : Number(tmax) >= 40 ? "Heat stress" : "Comfortable",
      metric: tmax != null ? `Tmax ${Number(tmax).toFixed(0)}°C` : "No heat wave flag",
      raw: heatLvl || String(tmax ?? "quiet"),
      tab: "risks",
    },
    {
      id: "aqi",
      label: "Air quality",
      status:
        aqiVal == null
          ? "No reading"
          : Number(aqiVal) <= 50
            ? "Good"
            : Number(aqiVal) <= 100
              ? "Moderate"
              : Number(aqiVal) <= 200
                ? "Unhealthy"
                : "Very poor",
      metric: aqiVal != null ? `AQI ${aqiVal}` : "CPCB / Open-Meteo",
      raw: String(aqiVal ?? "—"),
      tab: "environment",
    },
    {
      id: "tsunami",
      label: "Tsunami",
      status: tsunami.some((x) => x.threat) ? "Threat bulletin" : "No threat",
      metric: String((tsunami[0] as { title?: string } | undefined)?.title ?? "INCOIS ITEWS quiet"),
      raw: tsunami.some((x) => x.threat) ? "alert" : "quiet",
      tab: "hydrology",
    },
    {
      id: "quake",
      label: "Earthquake",
      status: seismic[0]?.mag != null && Number(seismic[0].mag) >= 4.5 ? "Recent quake" : "Quiet",
      metric: seismic[0]?.mag != null ? `M${seismic[0].mag} · ${seismic[0].place || "region"}` : "No nearby event",
      raw: String(seismic[0]?.mag ?? "quiet"),
      tab: "seismology",
    },
    {
      id: "fire",
      label: "Forest fire",
      status: climate.temp_max != null && Number(climate.temp_max) >= 38 && Number(climate.rh_now || 50) < 30 ? "Dry-hot" : "Low risk",
      metric: tmax != null ? `${Number(tmax).toFixed(0)}°C · RH ${climate.rh_now ?? "—"}%` : "—",
      raw: climate.temp_max != null && Number(climate.temp_max) >= 38 && Number(climate.rh_now || 50) < 30 ? "watch" : "quiet",
      tab: "risks",
    },
    {
      id: "slide",
      label: "Landslide",
      status: Number(dash.predictive.precip_next_3d_mm) > 80 ? "Wet-slope watch" : "Stable",
      metric: `Next 3 days ${Number(dash.predictive.precip_next_3d_mm).toFixed(0)} mm`,
      raw: Number(dash.predictive.precip_next_3d_mm) > 80 ? "watch" : "quiet",
      tab: "risks",
    },
    {
      id: "heavy",
      label: "Heavy rain",
      status: /warning|watch/i.test(String(vera?.extremes?.heavy_rain?.level)) ? String(vera?.extremes?.heavy_rain?.level) : "No heavy rain",
      metric:
        vera?.extremes?.heavy_rain?.next_24h_mm != null
          ? `${vera.extremes.heavy_rain.next_24h_mm} mm / 24 h`
          : `${dash.predictive.precip_next_3d_mm} mm / 3 d`,
      raw: String(vera?.extremes?.heavy_rain?.level ?? "quiet"),
      tab: "meteorology",
    },
    {
      id: "uv",
      label: "UV",
      status: uv >= 8 ? "Very high" : uv >= 3 ? "Moderate" : "Low",
      metric: `Index ${uv || "—"}`,
      raw: String(uv),
      tab: "environment",
    },
    {
      id: "fog",
      label: "Visibility",
      status: vis != null && Number(vis) < 1 ? "Dense fog" : vis != null && Number(vis) < 4 ? "Haze" : "Clear",
      metric: vis != null ? `${Number(vis).toFixed(1)} km` : "—",
      raw: vis != null && Number(vis) < 1 ? "watch" : "quiet",
      tab: "meteorology",
    },
    {
      id: "urban",
      label: "Street flooding",
      status: pond != null && Number(pond) >= 5 ? "Ponding" : "Dry streets",
      metric: pond != null ? `${Number(pond).toFixed(1)} mm / 60 min` : "No ponding",
      raw: String(pond ?? "0"),
      tab: "hydrology",
    },
    {
      id: "aviation",
      label: "Aviation",
      status: dash.science?.nowcast?.squall?.watch ? "Squall watch" : vis != null && Number(vis) < 3 ? "Low vis" : "Open",
      metric: vis != null ? `Vis ${Number(vis).toFixed(1)} km` : "No squall flag",
      raw: dash.science?.nowcast?.squall?.watch ? "alert" : "quiet",
      tab: "meteorology",
    },
    {
      id: "fish",
      label: "Fishing",
      status: !Number.isFinite(waveM) ? "Inland" : waveM >= 2.5 ? "Stay in harbour" : waveM >= 1.5 ? "Choppy" : "Calm seas",
      metric: Number.isFinite(waveM) ? `${waveM.toFixed(1)} m waves` : "No marine grid",
      raw: Number.isFinite(waveM) ? String(waveM) : "quiet",
      tab: "hydrology",
    },
    {
      id: "agri",
      label: "Farm",
      status: dash.prescriptive.actions[0]?.action ? "Action listed" : "No field action",
      metric: dash.prescriptive.actions[0]?.action || "Hold irrigation if rain is coming",
      raw: dash.prescriptive.actions[0]?.action || "quiet",
      tab: "agriculture",
    },
  ];

  return (
    <div className="space-y-3">
      {/* Hazard info cards */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((c) => (
          <section 
            key={c.title} 
            className="neo p-3 cursor-pointer hover:ring-2 hover:ring-[var(--accent)] transition-all"
            onClick={() => {
              if (c.title === "Air") onNavigateData?.('environment');
              else if (c.title === t.landWeather) onNavigateData?.('meteorology');
              else if (c.title === t.marineWeather) onNavigateData?.('hydrology');
            }}
          >
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{c.title}</p>
            <dl className="mt-2 space-y-1.5 text-sm">
              {c.rows.map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2">
                  <dt className="text-neo-muted">{k}</dt>
                  <dd className="truncate font-mono font-semibold">{v}</dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
      </div>


    </div>
  );
}

export function OverviewPlots({ dash, locale }: { dash: DashboardSnapshot; locale: Locale }) {
  const t = COPY[locale];
  const units = useApp((s) => s.settings.units);
  const live = dash.live;
  const series = dash.descriptive.series;
  const rainH = (series.precip_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: units === "imperial" ? p.value / 25.4 : p.value }));
  const tempH = (series.temp_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: units === "imperial" ? (p.value * 9) / 5 + 32 : p.value }));
  const wspd = (series.wind_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: units === "imperial" ? p.value * 0.621 : p.value }));
  const aqi = (series.aqi_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const aqiHist = (series.aqi_history || []).slice(-24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const wave = (series.wave_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: units === "imperial" ? p.value * 3.281 : p.value }));
  const discharge = (live?.flood?.discharge || dash.predictive.river_discharge || []).map((v, i) => ({
    t: `d+${i}`,
    v,
  }));
  const rh = (series.rh_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const soil = (series.soil_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const cloud = (series.cloud_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const dust = (series.dust_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const sst = (series.sst_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const swell = (series.swell_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: units === "imperial" ? p.value * 3.281 : p.value }));
  const rainD = (series.precip_daily || []).slice(0, 7).map((p) => ({ t: (p.t || "").slice(5), v: p.value }));
  const tmax = (series.tmax_daily || []).slice(0, 7).map((p) => ({ t: (p.t || "").slice(5), v: units === "imperial" ? (p.value * 9) / 5 + 32 : p.value }));
  const et0 = (series.et0_daily || []).slice(0, 7).map((p) => ({ t: (p.t || "").slice(5), v: p.value }));
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      <Spark title={`${t.tabForecast} · 24h`} data={rainH} color="var(--rain)" unit={rainUnit(units)} kind="bar" />
      <Spark title="Temperature · 24h" data={tempH} color="var(--gold)" unit={tempUnit(units)} />
      <Spark title={t.windSpeed} data={wspd} color="var(--accent)" unit={units === "imperial" ? "mph" : "km/h"} />
      <Spark title={t.humidity} data={rh} color="var(--accent)" unit="%" />
      <Spark title={t.cloud} data={cloud} color="#7aa2a8" unit="%" />
      <Spark title="SOIL MOISTURE" data={soil} color="#8d6e63" unit="m³/m³" />
      <Spark title={t.discharge} data={discharge} color="var(--flood)" unit="m³/s" />
      <Spark title="AQI" data={aqi} color="var(--accent2)" unit="" />
      <Spark title="PM10" data={(series.pm10_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }))} color="var(--accent2)" unit="µg/m³" />
      <Spark title="Dust" data={dust} color="#a1887f" unit="µg/m³" />
      <Spark title="UV" data={(series.uv_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }))} color="var(--gold)" unit="UV" />
      <Spark title={t.waves} data={wave} color="var(--rain)" unit={units === "imperial" ? "ft" : "m"} />
      <Spark title="Swell" data={swell} color="#1565c0" unit={units === "imperial" ? "ft" : "m"} />
      <Spark title="Sea surface" data={sst} color="#00838f" unit={tempUnit(units)} />
      <Spark title="Daily rain" data={rainD} color="var(--rain)" unit={rainUnit(units)} kind="bar" />
      <Spark title="Daily Tmax" data={tmax} color="var(--gold)" unit={tempUnit(units)} />
      <Spark title="EVATRANSPIRATION" data={et0} color="#5d8a66" unit="mm" />
    </div>
  );
}

function Stat({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-widest text-neo-muted">{k}</p>
      <p className="font-mono text-lg font-semibold">{v}</p>
    </div>
  );
}

function RainOdds({ k, pct, days }: { k: string; pct: number[]; days: string[] }) {
  if (!pct.length) {
    return <Stat k={k} v="—" />;
  }
  return (
    <div>
      <p className="text-[10px] uppercase tracking-widest text-neo-muted">{k}</p>
      <div className="mt-0.5 grid grid-cols-3 gap-1">
        {pct.map((p, i) => (
          <div key={days[i] || i} className="text-center">
            <p className="font-mono text-lg font-semibold">{p}%</p>
            <p className="text-[10px] uppercase tracking-widest text-neo-muted">{days[i] || `DAY${i + 1}`}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function Spark({
  title,
  data,
  color,
  unit,
  kind = "area",
}: {
  title: string;
  data: { t: string; v: number }[];
  color: string;
  unit: string;
  kind?: "area" | "bar";
}) {
  return (
    <section className="neo p-3">
      <div className="mb-1 flex items-baseline justify-between">
        <h3 className="text-[11px] font-bold uppercase tracking-[0.14em] text-neo-accent">{title}</h3>
        <span className="text-[10px] text-neo-muted">{unit}</span>
      </div>
      <div className="h-32">
        {data.length === 0 ? (
          <p className="flex h-full items-center justify-center text-xs text-neo-muted">—</p>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            {kind === "bar" ? (
              <BarChart data={data}>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="t" stroke="var(--muted)" fontSize={9} interval={3} />
                <YAxis stroke="var(--muted)" fontSize={9} width={28} />
                <Tooltip contentStyle={tip} />
                <Bar dataKey="v" fill={color} radius={[4, 4, 0, 0]} />
              </BarChart>
            ) : (
              <AreaChart data={data}>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="t" stroke="var(--muted)" fontSize={9} interval={3} />
                <YAxis stroke="var(--muted)" fontSize={9} width={28} />
                <Tooltip contentStyle={tip} />
                <Area type="monotone" dataKey="v" stroke={color} fill={color} fillOpacity={0.18} strokeWidth={2} />
              </AreaChart>
            )}
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}

function WindRose({
  fromDeg,
  flowDeg,
  rose,
  compass,
  flow,
}: {
  fromDeg: number | null;
  flowDeg: number | null;
  rose: { dir: string; count: number; avg_speed: number }[];
  compass: string;
  flow: string;
}) {
  const max = Math.max(1, ...rose.map((r) => r.count));
  return (
    <svg viewBox="0 0 200 200" className="h-20 w-20 shrink-0 sm:h-24 sm:w-24">
      <circle cx="100" cy="100" r="86" fill="var(--bg)" stroke="var(--line)" />
      <circle cx="100" cy="100" r="58" fill="none" stroke="var(--line)" strokeDasharray="3 4" />
      {["N", "E", "S", "W"].map((lab, i) => {
        const ang = (i * 90 - 90) * (Math.PI / 180);
        const x = 100 + Math.cos(ang) * 74;
        const y = 100 + Math.sin(ang) * 74;
        return (
          <text key={lab} x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontSize="10" fill="var(--muted)">
            {lab}
          </text>
        );
      })}
      {rose.map((b, i) => {
        const ang = i * 22.5;
        const len = 12 + (b.count / max) * 28;
        return (
          <line
            key={b.dir}
            x1="100"
            y1="100"
            x2="100"
            y2={100 - len}
            stroke="var(--rain)"
            strokeWidth={b.count ? 4 : 1}
            strokeLinecap="round"
            opacity={b.count ? 0.7 : 0.2}
            transform={`rotate(${ang} 100 100)`}
          />
        );
      })}
      {fromDeg != null ? (
        <g transform={`rotate(${fromDeg} 100 100)`}>
          <polygon points="100,22 108,70 100,62 92,70" fill="var(--accent2)" />
        </g>
      ) : null}
      {flowDeg != null ? (
        <g transform={`rotate(${flowDeg} 100 100)`}>
          <polygon points="100,34 106,78 100,72 94,78" fill="var(--accent)" />
        </g>
      ) : null}
      <circle cx="100" cy="100" r="18" fill="var(--card)" stroke="var(--line)" />
      <text x="100" y="98" textAnchor="middle" fontSize="9" fill="var(--accent)" fontWeight="700">
        {compass}
      </text>
      <text x="100" y="110" textAnchor="middle" fontSize="8" fill="var(--muted)">
        →{flow}
      </text>
    </svg>
  );
}

function SkyGlyph({ kind, day }: { kind: string; day: boolean }) {
  const sun = day ? "#e9b44c" : "#9aa6b2";
  return (
    <svg viewBox="0 0 88 88" className={`h-24 w-24 shrink-0 sky-glyph sky-${kind}`}>
      {kind === "clear" || kind === "partly" ? (
        <g className={day ? "sky-sun" : ""}>
          <circle cx={kind === "partly" ? 30 : 44} cy={kind === "partly" ? 30 : 40} r="14" fill={sun} />
          {day
            ? [0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
              <line
                key={a}
                x1={kind === "partly" ? 30 : 44}
                y1={kind === "partly" ? 30 : 40}
                x2={kind === "partly" ? 30 : 44}
                y2={kind === "partly" ? 8 : 16}
                stroke={sun}
                strokeWidth="2"
                transform={`rotate(${a} ${kind === "partly" ? 30 : 44} ${kind === "partly" ? 30 : 40})`}
              />
            ))
            : null}
        </g>
      ) : null}
      {kind !== "clear" ? (
        <g className="sky-cloud">
          <ellipse cx="40" cy="50" rx="22" ry="14" fill="#8fa3ad" opacity="0.85" />
          <ellipse cx="56" cy="52" rx="16" ry="12" fill="#7d929c" opacity="0.85" />
          <ellipse cx="28" cy="54" rx="14" ry="10" fill="#a8b8c0" opacity="0.9" />
        </g>
      ) : null}
      {kind === "rain" || kind === "storm" ? (
        <g className="sky-drops">
          <line x1="32" y1="66" x2="28" y2="80" stroke="var(--rain)" strokeWidth="2" />
          <line x1="44" y1="68" x2="40" y2="82" stroke="var(--rain)" strokeWidth="2" />
          <line x1="56" y1="66" x2="52" y2="80" stroke="var(--rain)" strokeWidth="2" />
        </g>
      ) : null}
      {kind === "storm" ? <polygon points="48,48 40,64 46,64 38,78 58,60 50,60 56,48" fill="var(--accent2)" /> : null}
      {kind === "fog" ? (
        <g>
          <line x1="18" y1="62" x2="70" y2="62" stroke="var(--muted)" strokeWidth="3" />
          <line x1="22" y1="70" x2="66" y2="70" stroke="var(--muted)" strokeWidth="3" />
          <line x1="20" y1="78" x2="68" y2="78" stroke="var(--muted)" strokeWidth="3" />
        </g>
      ) : null}
    </svg>
  );
}
