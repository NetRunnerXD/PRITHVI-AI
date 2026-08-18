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
import { rain, speed, temp } from "@/lib/units";

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

export function OverviewLive({ dash, locale }: { dash: DashboardSnapshot; locale: Locale }) {
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
  const nc = dash.science?.nowcast;
  const ncStrip = [
    ...(nc?.observed || []).slice(-3).map((h) => ({
      t: hhmm(h.t),
      rain: h.mm,
      engine: "observed" as const,
    })),
    ...(nc?.hours || []).map((h) => ({
      t: hhmm(h.t),
      rain: h.mm,
      engine: (h.engine || "nwp") as "nowcast" | "blend" | "nwp",
    })),
  ];
  const engineLabel: Record<string, string> = {
    observed: t.engineObserved,
    nowcast: t.engineNowcast,
    blend: t.engineBlend,
    nwp: t.engineNwp,
  };
  const days = (dash.predictive.outlook_days || []).slice(0, 7);

  const decide = [
    {
      k: t.pumpSet,
      v: (nc?.pump?.action || "—").toUpperCase(),
      sub: `${t.pInterrupt} ${nc?.pump?.p_interrupt_90m ?? "—"}`,
      hot: nc?.pump?.action === "hold",
    },
    {
      k: t.fieldAccess,
      v: nc?.access?.enterable === false ? t.closedField : t.enterable,
      sub: (nc?.access?.reasons || []).slice(0, 1).join(", ") || "",
      hot: nc?.access?.enterable === false,
    },
    {
      k: t.kalWatch,
      v: nc?.kal?.level === "watch" || nc?.tide?.drain_blocked ? (nc?.tide?.drain_blocked ? t.drainBlocked : t.kalWatch) : t.allClear,
      sub: nc?.regime?.name || "",
      hot: nc?.kal?.level === "watch" || Boolean(nc?.tide?.drain_blocked),
    },
  ];

  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-3">
        {decide.map((c) => (
          <div key={c.k} className={`neo px-3 py-2 ${c.hot ? "ring-1 ring-neo-danger" : ""}`}>
            <p className="text-[10px] uppercase tracking-widest text-neo-muted">{c.k}</p>
            <p className="mt-1 text-sm font-bold">{c.v}</p>
            {c.sub ? <p className="text-[11px] text-neo-muted">{c.sub}</p> : null}
          </div>
        ))}
      </div>
      {dash.science?.provenance ? (
        <p className="text-[11px] text-neo-muted">
          {t.provenance}: {dash.science.provenance.nowcast_mm || dash.science.provenance.rain}
        </p>
      ) : null}
      <div className="grid gap-3 lg:grid-cols-12">
        <section className="neo sky-card relative overflow-hidden p-5 lg:col-span-7">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.sky}</p>
          <div className="mt-3 flex items-center gap-4">
            <SkyGlyph kind={sky.kind || cur.sky_kind || "cloud"} day={sky.is_day !== false} />
            <div className="min-w-0">
              <p className="text-2xl font-extrabold leading-tight">{sky.label || cur.sky_label || "—"}</p>
              <p className="mt-1 font-mono text-4xl font-bold text-neo-accent">
                {temp(sky.temp_c ?? cur.temp_c, units)}
              </p>
              <p className="mt-1 text-xs text-neo-muted">
                {sky.is_day ? t.day : t.night}
                {feels != null ? ` · ${temp(feels, units)}` : ""}
                {sky.place ? ` · ${sky.place}` : ""}
              </p>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <Stat k={`${t.humidity}`} v={sky.humidity_pct != null ? `${Math.round(Number(sky.humidity_pct))} %` : "—"} />
            <Stat k={t.cloud} v={sky.cloud_cover_pct != null ? `${Math.round(Number(sky.cloud_cover_pct))} %` : "—"} />
            <Stat k={t.visibility} v={sky.visibility_km != null ? `${sky.visibility_km} km` : "—"} />
            <Stat k={t.lastHourRain} v={rain(sky.precip_1h_mm, units)} />
          </div>
        </section>

        <section className="neo p-5 lg:col-span-5">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.rainToday}</p>
          <p className="mt-3 font-mono text-4xl font-extrabold text-neo-accent">
            {todayRain != null ? rain(todayRain, units) : "—"}
          </p>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <Stat k={t.rain3} v={rain(dash.predictive.precip_next_3d_mm, units)} />
            <Stat k={t.rain7} v={rain(dash.predictive.precip_7d_mm, units)} />
            <Stat
              k={t.chanceOfRain}
              v={(dash.predictive.precip_probability_pct || []).slice(0, 3).map((p) => `${p}%`).join(" · ") || "—"}
            />
            <Stat k={t.balance} v={rain(dash.predictive.water_balance_7d_mm, units)} />
          </div>
        </section>
      </div>

      {ncStrip.length > 0 ? (
        <section className="neo overflow-x-auto p-3">
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.nowcast}</p>
            <p className="text-[10px] text-neo-muted">{t.modelAnalysis}</p>
          </div>
          <div className="mb-3 flex flex-wrap gap-2 text-[11px]">
            {nc?.clock?.t_start ? (
              <span className="chip">
                {t.onset} {hhmm(nc.clock.t_start)}
              </span>
            ) : null}
            {nc?.clock?.t_stop ? (
              <span className="chip">
                {t.cessation} {hhmm(nc.clock.t_stop)}
              </span>
            ) : null}
            {nc?.pump ? (
              <span className="chip">
                {t.pumpSet} {nc.pump.action === "hold" ? t.holdHint : t.applyHint} · {t.pInterrupt}{" "}
                {nc.pump.p_interrupt_90m ?? "—"}
              </span>
            ) : null}
            {nc?.access ? (
              <span className="chip">
                {t.fieldAccess} {nc.access.enterable ? t.enterable : t.closedField}
              </span>
            ) : null}
            {nc?.kal?.level === "watch" ? <span className="chip">{t.kalWatch}</span> : null}
            {nc?.tide?.drain_blocked ? <span className="chip">{t.drainBlocked}</span> : null}
            {nc?.ponding?.mm_60 != null ? (
              <span className="chip">
                {t.ponding} {rain(nc.ponding.mm_60, units)}
              </span>
            ) : null}
          </div>
          <div className="flex min-w-max gap-2">
            {ncStrip.map((h, i) => (
              <div key={`${h.engine}-${h.t}-${i}`} className="w-12 shrink-0 text-center">
                <p className="text-[10px] text-neo-muted">{h.t}</p>
                <div className="mx-auto mt-1 h-10 w-1.5 overflow-hidden rounded-full bg-neo-bg">
                  <div
                    className="mt-auto w-full rounded-full"
                    style={{
                      height: `${Math.min(100, h.rain * 18)}%`,
                      background:
                        h.engine === "nowcast"
                          ? "var(--accent)"
                          : h.engine === "blend"
                            ? "var(--rain)"
                            : h.engine === "observed"
                              ? "var(--text)"
                              : "var(--muted)",
                      minHeight: h.rain > 0 ? 4 : 0,
                    }}
                  />
                </div>
                <p className="mt-1 font-mono text-[11px] font-bold">{h.rain ? h.rain.toFixed(1) : "—"}</p>
                <p className="text-[9px] uppercase tracking-wide text-neo-muted">{engineLabel[h.engine] || h.engine}</p>
              </div>
            ))}
          </div>
        </section>
      ) : hourly.length > 0 ? (
        <section className="neo overflow-x-auto p-3">
          <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.nextHours}</p>
          <div className="flex min-w-max gap-2">
            {hourly.map((h) => (
              <div key={h.t} className="w-12 shrink-0 text-center">
                <p className="text-[10px] text-neo-muted">{h.t}</p>
                <p className="mt-1 font-mono text-sm font-bold">{Math.round(h.temp)}°</p>
                <div className="mx-auto mt-1 h-8 w-1.5 overflow-hidden rounded-full bg-neo-bg">
                  <div
                    className="mt-auto w-full rounded-full"
                    style={{
                      height: `${Math.min(100, h.rain * 18)}%`,
                      background: "var(--rain)",
                      minHeight: h.rain > 0 ? 4 : 0,
                    }}
                  />
                </div>
                <p className="mt-1 text-[10px] text-neo-muted">{h.rain ? h.rain.toFixed(1) : "—"}</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {days.length > 0 ? (
        <section className="neo p-3">
          <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.tabForecast}</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
            {days.map((d) => (
              <div key={d.date} className="neo-in rounded-2xl px-2 py-2 text-center">
                <p className="text-[11px] font-semibold">{weekday(d.date)}</p>
                <p className="mt-1 font-mono text-sm font-bold">{temp(d.temp_max_c, units)}</p>
                <p className="text-[11px] text-neo-muted">{rain(d.precip_mm, units)}</p>
                <p className="text-[10px] text-neo-muted">{d.precip_prob_pct}%</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-12">
        <section className="neo flex flex-wrap items-center gap-4 p-3 lg:col-span-5">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.windProfile}</p>
          <WindRose
            fromDeg={wind.direction_deg ?? null}
            flowDeg={wind.flow_deg ?? null}
            rose={rose}
            compass={wind.compass || "—"}
            flow={wind.flow_compass || "—"}
          />
          <div className="min-w-0 text-sm">
            <p className="font-mono text-2xl font-bold text-neo-accent">{speed(wind.speed_kmh, units)}</p>
            <p className="text-neo-muted">
              {t.fromWind} {wind.compass || "—"}
              {wind.direction_deg != null ? ` (${Math.round(Number(wind.direction_deg))}°)` : ""}
              <span className="mx-1">→</span>
              {wind.flow_compass || "—"}
            </p>
          </div>
        </section>

        <section className="neo p-4 lg:col-span-7">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.descriptive}</p>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Stat k={`${t.soil} (m³/m³)`} v={cur.soil_moisture_m3m3 != null ? cur.soil_moisture_m3m3.toFixed(3) : "—"} />
            <Stat k={`${t.et0} (mm)`} v={cur.et0_mm != null ? cur.et0_mm.toFixed(2) : "—"} />
            <Stat k={t.aqi} v={cur.aqi != null ? `${cur.aqi}${cur.aqi_category ? ` ${cur.aqi_category}` : ""}` : "—"} />
            <Stat k={`${t.windSpeed}`} v={speed(wind.speed_kmh, units)} />
            <Stat
              k={t.waves}
              v={live?.marine?.wave_height_m != null ? `${Number(live.marine.wave_height_m).toFixed(1)} m` : "—"}
            />
            <Stat k={t.discharge} v={dash.predictive.flood_discharge_trend || "—"} />
          </div>
        </section>
      </div>
    </div>
  );
}

export function OverviewPlots({ dash, locale }: { dash: DashboardSnapshot; locale: Locale }) {
  const t = COPY[locale];
  const live = dash.live;
  const series = dash.descriptive.series;
  const rainH = (series.precip_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const tempH = (series.temp_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const wspd = (series.wind_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const aqi = (series.aqi_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const aqiHist = (series.aqi_history || []).slice(-24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const wave = (series.wave_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const discharge = (live?.flood?.discharge || dash.predictive.river_discharge || []).map((v, i) => ({
    t: `d+${i}`,
    v,
  }));
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      <Spark title={`${t.tabForecast} · 24h`} data={rainH} color="var(--rain)" unit="mm" kind="bar" />
      <Spark title="24h" data={tempH} color="var(--gold)" unit="°C" />
      <Spark title={t.windSpeed} data={wspd} color="var(--accent)" unit="km/h" />
      <Spark title={t.discharge} data={discharge} color="var(--flood)" unit="m³/s" />
      <Spark title={t.omAqi} data={aqi} color="var(--accent2)" unit="US AQI" />
      <Spark title={t.histAqi} data={aqiHist.length ? aqiHist : aqi} color="var(--accent2)" unit={aqiHist.length ? "µg/m³" : "US AQI"} />
      <Spark title={t.waves} data={wave} color="var(--rain)" unit="m" />
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
