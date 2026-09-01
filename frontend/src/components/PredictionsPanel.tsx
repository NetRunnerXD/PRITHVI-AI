"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COL = {
  ensemble: "#146b7a",
  blend: "#8e44ad",
  om: "#c45c26",
  ai: "#d35400",
  nwp: "#2c7fb8",
};

function familyOf(id: string): "ai" | "nwp" | "blend" | "ensemble" | "om" {
  const s = id.toLowerCase();
  if (s === "ensemble") return "ensemble";
  if (s === "moe" || s === "blend") return "blend";
  if (s === "om" || s === "open-meteo" || s === "website") return "om";
  if (["graphcast", "pangu", "fourcast", "aifs"].some((k) => s.includes(k))) return "ai";
  return "nwp";
}

function strokeOf(id: string): string {
  const f = familyOf(id);
  if (f === "ensemble") return COL.ensemble;
  if (f === "blend") return COL.blend;
  if (f === "om") return COL.om;
  if (f === "ai") return COL.ai;
  return COL.nwp;
}

function familyLabel(id: string): string {
  const f = familyOf(id);
  if (f === "ensemble") return "Ensemble (satellite + NWP shape)";
  if (f === "blend") return "Blend (gated members)";
  if (f === "om") return "Website (Open-Meteo)";
  if (f === "ai") return "AI forecast";
  return "NWP (physics)";
}

function istClock(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    const m = String(iso).match(/T(\d{2}:\d{2})/);
    return m ? m[1] : "—";
  }
  return d.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });
}

function round2(n: number | null | undefined): string {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return (Math.round(Number(n) * 100) / 100).toFixed(2);
}

function hourlyVars(
  r: {
    ensemble?: number | null;
    moe?: number | null;
    om?: number | null;
    ensemble_temp_c?: number | null;
    moe_temp_c?: number | null;
    om_temp_c?: number | null;
    ensemble_wind_kmh?: number | null;
    moe_wind_kmh?: number | null;
    om_wind_kmh?: number | null;
    ensemble_wbgt_c?: number | null;
    moe_wbgt_c?: number | null;
    om_wbgt_c?: number | null;
  },
  varK: "rain" | "temp" | "wind" | "heat"
) {
  if (varK === "temp") return { Ensemble: r.ensemble_temp_c ?? null, Blend: r.moe_temp_c ?? null, Website: r.om_temp_c ?? null };
  if (varK === "wind") return { Ensemble: r.ensemble_wind_kmh ?? null, Blend: r.moe_wind_kmh ?? null, Website: r.om_wind_kmh ?? null };
  if (varK === "heat") return { Ensemble: r.ensemble_wbgt_c ?? null, Blend: r.moe_wbgt_c ?? null, Website: r.om_wbgt_c ?? null };
  return { Ensemble: r.ensemble ?? null, Blend: r.moe ?? null, Website: r.om ?? null };
}

function AxisHint({ x, y }: { x: string; y: string }) {
  return <p className="mt-1 text-[10px] text-neo-muted">Horizontal (X): {x}. Vertical (Y): {y}.</p>;
}

function confPct(weightPct: number, raw?: number | null): number {
  if (raw != null && !Number.isNaN(Number(raw)) && Number(raw) > 0) return Math.round(Number(raw));
  return Math.max(28, Math.min(94, 55 + Math.round(weightPct * 0.35)));
}
import { COPY, type Locale } from "@/i18n/copy";
import type { DashboardSnapshot, PredictionPack, VeraPack } from "@/types/dashboard";
const SatProcessMap = dynamic(() => import("./SatProcessMap").then((m) => m.SatProcessMap), { ssr: false });

export function PredictionsPanel({ dash, locale }: { dash: DashboardSnapshot; locale: Locale }) {
  const t = COPY[locale];
  const [src, setSrc] = useState<"ours" | "trusted">("ours");
  const [sec, setSec] = useState<string>("hourly");
  const pack: PredictionPack | undefined = src === "ours" ? dash.predictions?.ours : dash.predictions?.trusted;
  const other = src === "ours" ? dash.predictions?.trusted : dash.predictions?.ours;
  const chart = useMemo(() => {
    const a = dash.predictions?.ours?.days || [];
    const b = dash.predictions?.trusted?.days || [];
    const n = Math.max(a.length, b.length);
    return Array.from({ length: n }, (_, i) => ({
      d: (a[i]?.date || b[i]?.date || "").slice(5),
      ours: a[i]?.precip_mm,
      trusted: b[i]?.precip_mm,
    }));
  }, [dash.predictions]);

  if (!pack) {
    return <p className="text-sm text-neo-muted">{t.loading}</p>;
  }

  const vera = dash.predictions?.vera;
  const secs = [
    ["hourly", t.secHourly],
    ["intra", t.secIntra],
    ["sat", t.secSat],
    ["leads", t.secLeads],
    ["blend", t.secBlend],
    ["params", t.secParams],
    ["explain", t.secExplain],
    ["disagree", t.secDisagree],
    ["omblend", t.secOmBlend],
    ["extremes", t.secExtremes],
    ["compare", t.secCompare],
    ["board", t.secBoard],
    ["replay", t.secReplay],
    ["perf", t.secPerf],
    ["bulletin", t.secBulletin],
    ["outlook", t.secOutlook],
  ] as const;

  return (
    <div className="space-y-4">
      <nav className="neo sticky top-0 z-20 flex flex-wrap gap-1 p-2">
        {secs.map(([id, label]) => (
          <button key={id} type="button" className={`neo-btn text-[11px] ${sec === id ? "neo-btn-on" : ""}`} onClick={() => setSec(id)}>
            {label}
          </button>
        ))}
      </nav>
      {vera && sec === "hourly" ? <HourlySec vera={vera} t={t} /> : null}
      {vera && sec === "intra" ? <IntraSec vera={vera} /> : null}
      {vera && sec === "leads" ? <LeadsSec vera={vera} /> : null}
      {vera && sec === "explain" ? <ExplainSec vera={vera} /> : null}
      {vera && sec === "disagree" ? <DisagreeSec vera={vera} /> : null}
      {vera && sec === "omblend" ? <OmBlendSec vera={vera} t={t} /> : null}
      {vera && sec === "board" ? <BoardSec vera={vera} /> : null}
      {vera && sec === "replay" ? <ReplaySec vera={vera} /> : null}
      {vera && sec === "bulletin" ? (
        <section className="neo p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.secBulletin}</p>
          <p className="mt-2 text-sm leading-relaxed">{vera.bulletin || "—"}</p>
          <p className="mt-2 text-[11px] text-neo-muted">Auto-generated from the blend. Not a signed IMD bulletin.</p>
        </section>
      ) : null}
      {vera && sec === "sat" ? (
        <section className="neo p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.secSat}</p>
          <SatProcessMap vera={vera} lat={dash.location.lat} lon={dash.location.lon} />
        </section>
      ) : null}
      {vera && sec === "blend" ? <BlendSec vera={vera} t={t} /> : null}
      {vera && sec === "params" ? <ParamsSec vera={vera} t={t} /> : null}
      {vera && sec === "extremes" ? <ExtremesSec vera={vera} /> : null}
      {vera && sec === "compare" ? <CompareSec vera={vera} /> : null}
      {vera && sec === "perf" ? <PerfSec vera={vera} t={t} /> : null}
      {sec === "outlook" ? (
      <>
      <div className="neo flex flex-wrap items-center gap-2 p-3">
        <button className={`neo-btn ${src === "ours" ? "neo-btn-on" : ""}`} onClick={() => setSrc("ours")}>
          {t.ours}
        </button>
        <button className={`neo-btn ${src === "trusted" ? "neo-btn-on" : ""}`} onClick={() => setSrc("trusted")}>
          {t.trusted}
        </button>
        <p className="text-xs text-neo-muted">{t.predHint}</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Kpi label={t.rain3} value={`${pack.precip_3d_mm} mm`} sub={other ? `API ${other.precip_3d_mm}` : ""} />
        <Kpi label={t.rain7} value={`${pack.precip_7d_mm} mm`} sub={other ? `API ${other.precip_7d_mm}` : ""} />
        <Kpi label={t.balance} value={`${pack.water_balance_7d_mm} mm`} />
      </div>

      <section className="neo p-4">
        <p className="text-sm font-semibold text-neo-accent">{src === "ours" ? t.ours : t.trusted}</p>
        <p className="text-xs text-neo-muted">{t.predHint}</p>
        <div className="mt-3 h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chart}>
              <CartesianGrid stroke="#cfe0dd" vertical={false} />
              <XAxis dataKey="d" stroke="#4d6b70" fontSize={10} />
              <YAxis stroke="#4d6b70" fontSize={10} width={28} />
              <Tooltip contentStyle={{ background: "#eef6f4", border: "none", borderRadius: 16 }} />
              <Legend />
              <Bar dataKey="ours" fill="#146b7a" radius={[6, 6, 0, 0]} />
              <Bar dataKey="trusted" fill="#4aa3b5" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {dash.predictions?.hybrid?.weights && Object.keys(dash.predictions.hybrid.weights).length > 0 ? (
        <section className="neo p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Model weights</p>
          <p className="text-[11px] text-neo-muted">{dash.predictions.hybrid.attribution}</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-5">
            {Object.entries(dash.predictions.hybrid.weights).map(([k, v]) => (
              <div key={k} className="neo-in p-3">
                <p className="text-[10px] uppercase tracking-widest text-neo-muted">{k}</p>
                <p className="font-mono text-lg font-bold text-neo-accent">{Math.round(v * 100)}%</p>
              </div>
            ))}
          </div>
          {dash.predictions.hybrid.hazards?.heavy_rain ? (
            <p className="mt-3 text-xs text-neo-muted">
              P(≥ {dash.predictions.hybrid.hazards.heavy_rain.threshold_mm} mm) ={" "}
              {dash.predictions.hybrid.hazards.heavy_rain.p ?? "—"} · guidance only
            </p>
          ) : null}
        </section>
      ) : null}

      {dash.predictions?.hazards ? (
        <section className="neo p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.hazardOutlook}</p>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            {(["flood", "tsunami", "seismic"] as const).map((k) => {
              const h = dash.predictions?.hazards?.[k];
              if (!h) return null;
              return (
                <div key={k} className="neo-in p-3">
                  <p className="text-[10px] uppercase tracking-widest text-neo-muted">{k}</p>
                  <p className="text-sm font-semibold capitalize">{h.level || "—"}</p>
                  {"nearest_place" in h && h.nearest_place ? (
                    <p className="mt-1 text-xs text-neo-muted">
                      M{h.nearest_mag} · {h.nearest_km} km · {h.nearest_place}
                    </p>
                  ) : null}
                  {"latest_title" in h && h.latest_title ? (
                    <p className="mt-1 text-xs text-neo-muted">{h.latest_title}</p>
                  ) : null}
                  {"drivers" in h && Array.isArray(h.drivers) ? (
                    <p className="mt-1 text-[11px] text-neo-muted">{h.drivers.slice(0, 3).join(" · ")}</p>
                  ) : null}

                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      <section className="neo overflow-auto p-4">
        <table className="w-full text-left text-xs">
          <thead className="text-neo-muted">
            <tr>
              <th className="py-2">{t.colDate}</th>
              <th>{t.colRain}</th>
              <th>{t.colProb}</th>
              <th>{t.colEt0}</th>
              <th>{t.colSoil}</th>
              <th>{t.colConf}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {pack.days.map((d) => (
              <tr key={d.date} className="border-t border-[#cfe0dd]">
                <td className="py-2 font-mono">{d.date}</td>
                <td>{d.precip_mm}</td>
                <td>{d.precip_prob_pct}</td>
                <td>{d.et0_mm}</td>
                <td>{d.soil_m3m3}</td>
                <td>{d.confidence_pct ?? "—"}</td>
                <td className="text-neo-muted">{d.adjustment || (d.flood_watch ? "flood" : d.irrigate ? "irrigate" : "—")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      </>
      ) : null}
    </div>
  );
}

function VeraBoard({ vera, t }: { vera: VeraPack; t: Record<string, string> }) {
  const [node, setNode] = useState("cv");
  const pdf = (vera.fusion?.pdf_x || []).map((x, i) => ({ x, y: vera.fusion?.pdf_y?.[i] || 0 }));
  const hourly = (vera.temporal?.hourly_0_48 || []).map((v, i) => ({ h: i, mm: v }));
  const seam = vera.temporal?.seamless || [];
  const w = Object.entries(vera.gate?.weights || {}).map(([k, v]) => ({ k, v: Math.round(v * 100) }));
  const frames = vera.cv?.frames || [];

  return (
    <div className="space-y-4">
      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.veraTitle}</p>
        <p className="text-sm font-semibold">{vera.title}</p>
        <div className="mt-3 flex flex-wrap gap-1">
          {(vera.graph?.nodes || []).map((n) => (
            <button
              key={n.id}
              type="button"
              className={`neo-btn text-[11px] ${node === n.id ? "neo-btn-on" : ""}`}
              onClick={() => setNode(n.id)}
            >
              {n.title}
            </button>
          ))}
        </div>
        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap font-mono text-[10px] text-neo-muted">
          {JSON.stringify((vera.node_detail || {})[node] ?? vera.cv?.input?.note, null, 2)}
        </pre>
      </section>
      {(vera.api_needed || []).length ? (
        <section className="neo space-y-2 p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">API keys to add</p>
          {(vera.api_needed || []).map((a) => (
            <div key={a.id} className="neo-in p-3 text-xs">
              <p className="font-semibold">
                {a.id}
                {a.locked ? " · locked" : ""}
              </p>
              {a.env?.length ? <p className="font-mono text-[11px]">{a.env.join(", ")}</p> : null}
              <p className="mt-1 text-neo-muted">{a.prompt}</p>
            </div>
          ))}
        </section>
      ) : null}

      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.veraSat}</p>
        <p className="text-[11px] text-neo-muted">
          {vera.cv?.source} · N={vera.cv?.input?.n} C={vera.cv?.input?.c} · Tb {vera.cv?.tb_k ?? "—"} K · cells {vera.cv?.n_cells ?? 0}
        </p>
        <div className="mt-3 flex gap-2 overflow-x-auto">
          {frames.map((f, i) => (
            <div key={i} className="w-28 shrink-0">
              {f.heatmap ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={f.heatmap} alt="INSAT IR" className="h-28 w-28 rounded-lg object-cover" />
              ) : f.url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={f.url} alt="INSAT IR" className="h-28 w-28 rounded-lg object-cover" />
              ) : (
                <div className="flex h-28 w-28 items-center justify-center rounded-lg bg-black/20 text-[10px]">IR</div>
              )}
              <p className="mt-1 font-mono text-[10px] text-neo-muted">{f.channel}</p>
            </div>
          ))}
          {vera.cv?.insat_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={vera.cv.insat_url} alt="INSAT full disk IR" className="h-28 w-40 rounded-lg object-cover" />
          ) : null}
        </div>
        <div className="mt-3 grid gap-2 sm:grid-cols-5 font-mono text-[11px]">
          <div className="neo-in p-2">CNN {JSON.stringify(vera.cv?.stage1_cnn?.shape)}</div>
          <div className="neo-in p-2">ConvLSTM {JSON.stringify(vera.cv?.stage2_convlstm?.shape)}</div>
          <div className="neo-in p-2">Swin {JSON.stringify(vera.cv?.stage_swin?.shape)} {vera.cv?.stage_swin?.backbone}</div>
          <div className="neo-in p-2">U-Net {JSON.stringify(vera.cv?.stage3_unet?.spatial_shape)}</div>
          <div className="neo-in p-2">
            CI {String(vera.cv?.derived?.convective_initiation)} · {String(vera.cv?.derived?.precip_est_mmh)} mm/h
          </div>
        </div>
      </section>

      <div className="grid gap-3 lg:grid-cols-2">
        <section className="neo p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.veraHist}</p>
          <p className="text-xs">
            Clim {vera.historical?.climatology?.mean ?? "—"} mm · p95 {vera.historical?.climatology?.p95 ?? "—"} · regime{" "}
            {vera.regime?.top}
          </p>
          <ul className="mt-2 space-y-1 text-xs">
            {(vera.historical?.analogues || []).slice(0, 5).map((a, i) => (
              <li key={i}>
                {a.date || "analogue"} · {a.mm} mm · {a.synoptic}
              </li>
            ))}
          </ul>
        </section>
        <section className="neo p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.veraGate}</p>
          {vera.gate?.weight_map_rgb ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={vera.gate.weight_map_rgb} alt="RGB weight map" className="mb-2 h-24 w-24 rounded-lg" />
          ) : null}
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={w}>
                <CartesianGrid stroke="#cfe0dd" vertical={false} />
                <XAxis dataKey="k" stroke="#4d6b70" fontSize={9} interval={0} angle={-25} height={48} />
                <YAxis stroke="#4d6b70" fontSize={10} width={28} />
                <Tooltip />
                <Bar dataKey="v" fill="#146b7a" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <section className="neo p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.veraFusion}</p>
          <p className="text-xs">
            {vera.fusion?.method || "EQMN"} · q10 {vera.fusion?.q10} · q50 {vera.fusion?.q50} · q90 {vera.fusion?.q90} · q95{" "}
            {vera.fusion?.q95} · q99 {vera.fusion?.q99} mm · P(≥64.5){" "}
            {vera.fusion?.extremes?.p_ge_64_5} · P(≥115.6) {vera.fusion?.extremes?.p_ge_115_6}
          </p>
          <p className="text-[10px] text-neo-muted">Operational blend is EQMN quantiles. Area chart is a diagnostic Gaussian mixture, not the product.</p>
          <div className="mt-2 h-40">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={pdf}>
                <CartesianGrid stroke="#cfe0dd" vertical={false} />
                <XAxis dataKey="x" stroke="#4d6b70" fontSize={10} />
                <YAxis stroke="#4d6b70" fontSize={10} width={32} />
                <Tooltip />
                <Area dataKey="y" fill="#4aa3b5" stroke="#146b7a" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="neo p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.veraTime}</p>
          <div className="grid grid-cols-3 gap-2 text-[11px]">
            {Object.entries(vera.temporal?.windows || {}).map(([k, v]) => (
              <div key={k} className="neo-in p-2">
                <p className="font-semibold">{k}</p>
                <p>{v.mm} mm</p>
                <p className="text-neo-muted">{v.dominant}</p>
              </div>
            ))}
          </div>
          <div className="mt-2 h-36">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={seam}>
                <XAxis dataKey="lead_h" stroke="#4d6b70" fontSize={10} />
                <YAxis stroke="#4d6b70" fontSize={10} width={28} />
                <Tooltip />
                <Line dataKey="sat_w" stroke="#146b7a" dot={false} />
                <Line dataKey="nwp_w" stroke="#c45c26" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Hourly 0–48 h</p>
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={hourly}>
              <CartesianGrid stroke="#cfe0dd" vertical={false} />
              <XAxis dataKey="h" stroke="#4d6b70" fontSize={10} />
              <YAxis stroke="#4d6b70" fontSize={10} width={28} />
              <Tooltip />
              <Area dataKey="mm" fill="#146b7a" stroke="#146b7a" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.veraMlops}</p>
        <p className="text-xs">
          registry v{vera.mlops?.registry?.current?.version ?? "—"} · drift {String(vera.mlops?.drift?.flag)} z=
          {vera.mlops?.drift?.z ?? "—"}
        </p>
        <ol className="mt-2 list-decimal pl-4 text-xs">
          {(vera.mlops?.loop || []).map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ol>
      </section>
    </div>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="neo p-4">
      <p className="text-[10px] uppercase tracking-widest text-neo-muted">{label}</p>
      <p className="font-mono text-2xl font-bold text-neo-accent">{value}</p>
      {sub ? <p className="text-[11px] text-neo-muted">{sub}</p> : null}
    </div>
  );
}

function HourlySec({ vera, t }: { vera: VeraPack; t: Record<string, string> }) {
  const now = Date.now();
  const [varK, setVarK] = useState<"rain" | "temp" | "wind" | "heat">("rain");
  const rows = (vera.hourly || [])
    .filter((r) => {
      const h = r.lead_h ?? 0;
      return h >= -12 && h < 24;
    })
    .slice()
    .sort((a, b) => (a.lead_h ?? 0) - (b.lead_h ?? 0));
  const chart = rows.map((r) => ({
    h: r.lead_h ?? 0,
    t: istClock(r.t),
    ...hourlyVars(r, varK),
  }));
  const nowIst = new Date().toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });
  const yLabel = varK === "rain" ? "Rain (mm in that hour)" : varK === "temp" ? "Temperature (°C)" : varK === "wind" ? "Wind (km/h)" : "WBGT heat (°C)";
  return (
    <section className="neo space-y-3 p-4">
      <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.secHourly}</p>
      <p className="text-xs text-neo-muted">
        Clock now (IST): {nowIst}. Horizon is the past 12 hours through the next 24. Times are India Standard Time — not UTC.
        Past hours are negative in the table. <strong> Ensemble</strong> = satellite rain shape plus NWP. <strong>Blend</strong> = gated mix of physics/AI members. <strong>Website</strong> = Open-Meteo.
      </p>
      <div className="flex flex-wrap gap-1">
        {(["rain", "temp", "wind", "heat"] as const).map((k) => (
          <button key={k} type="button" className={`neo-btn text-[11px] ${varK === k ? "neo-btn-on" : ""}`} onClick={() => setVarK(k)}>
            {k === "rain" ? "Rain (mm)" : k === "temp" ? "Temperature (°C)" : k === "wind" ? "Wind (km/h)" : "Heat WBGT (°C)"}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2 text-[10px]">
        <span style={{ color: COL.ensemble }}>● Ensemble</span>
        <span style={{ color: COL.blend }}>● Blend</span>
        <span style={{ color: COL.om }}>● Website</span>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chart}>
            <CartesianGrid stroke="#cfe0dd" vertical={false} />
            <XAxis dataKey="t" stroke="#4d6b70" fontSize={10} />
            <YAxis stroke="#4d6b70" fontSize={10} width={36} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="Ensemble" stroke={COL.ensemble} strokeWidth={2.5} dot={false} />
            <Line type="monotone" dataKey="Blend" stroke={COL.blend} strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="Website" stroke={COL.om} strokeDasharray="4 3" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <AxisHint x="Valid hour (IST), past 12 h → next 24 h" y={yLabel} />
      <div className="overflow-auto">
        <table className="w-full text-left text-[11px]">
          <thead className="text-neo-muted">
            <tr>
              <th className="py-1">Hours from now</th>
              <th>Valid time (IST)</th>
              <th style={{ color: COL.ensemble }}>Ensemble</th>
              <th style={{ color: COL.blend }}>Blend</th>
              <th style={{ color: COL.om }}>Website</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const ts = r.t ? new Date(r.t).getTime() : NaN;
              const isNow = !Number.isNaN(ts) && Math.abs(ts - now) < 35 * 60 * 1000;
              return (
              <tr key={`${r.t}-${r.lead_h}`} className="border-t border-neo-line">
                <td className="py-1 font-mono">{r.lead_h ?? 0}{isNow ? " · now" : ""}</td>
                <td className="font-mono">{istClock(r.t)}</td>
                <td className="font-mono" style={{ color: COL.ensemble }}>{round2(hourlyVars(r, varK).Ensemble)}</td>
                <td className="font-mono" style={{ color: COL.blend }}>{round2(hourlyVars(r, varK).Blend)}</td>
                <td className="font-mono" style={{ color: COL.om }}>{round2(hourlyVars(r, varK).Website)}</td>
              </tr>
            );})}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function BlendSec({ vera, t }: { vera: VeraPack; t: Record<string, string> }) {
  const w = Object.entries(vera.gate?.weights || {}).map(([k, v]) => ({
    k,
    v: Math.round(v * 100),
    conf: confPct(Math.round(v * 100), vera.gate?.confidence?.[k]),
    family: vera.gate?.family?.[k] || familyOf(k),
  }));
  return (
    <div className="space-y-3">
      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.secBlend}</p>
        <p className="text-[11px] text-neo-muted">Teal NWP · orange AI. Confidence is how sure the gate is about each share, not a rain-gauge score.</p>
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={w}>
              <CartesianGrid stroke="#cfe0dd" vertical={false} />
              <XAxis dataKey="k" stroke="#4d6b70" fontSize={9} interval={0} angle={-25} height={48} />
              <YAxis stroke="#4d6b70" fontSize={10} width={28} />
              <Bar dataKey="v" radius={[6, 6, 0, 0]}>
                {w.map((d) => (
                  <Cell key={d.k} fill={d.family === "ai" ? COL.ai : COL.nwp} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {w.map((d) => (
            <div key={d.k} className="neo-in p-3">
              <p className="text-[10px] uppercase tracking-widest" style={{ color: d.family === "ai" ? COL.ai : COL.nwp }}>
                {familyLabel(d.k)}
              </p>
              <p className="font-mono text-sm font-bold">{d.k}</p>
              <p className="text-xs">Share {d.v}% · confidence {d.conf}%</p>
            </div>
          ))}
        </div>
      </section>
      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Why these weights</p>
        <ul className="mt-2 space-y-3 text-xs leading-relaxed">
          {Object.entries(vera.gate?.reasons || {}).map(([k, v]) => (
            <li key={k} className="border-t border-neo-line pt-2">
              <span className="font-semibold" style={{ color: strokeOf(k) }}>{k}</span>
              <p className="mt-1 text-neo-muted">{v}</p>
            </li>
          ))}
        </ul>
      </section>
      {vera.fusion?.quantiles || vera.fusion?.q50 != null ? (
        <section className="neo p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">How wet the mix thinks the next 24 h will be</p>
          <p className="text-[11px] text-neo-muted">
            This is 24-hour rain from the gated mix, in millimetres. The number used on the rest of Models is <strong>Typical</strong>. Drier = only 1 day in 10 is this dry or drier. Extreme = 1 day in 100.
          </p>
          <div className="mt-2 h-44">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={[
                  { k: "Drier", mm: vera.fusion?.quantiles?.["0.1"] ?? vera.fusion?.q10 },
                  { k: "Below typical", mm: vera.fusion?.quantiles?.["0.25"] ?? vera.fusion?.q25 },
                  { k: "Typical", mm: vera.fusion?.quantiles?.["0.5"] ?? vera.fusion?.q50 },
                  { k: "Wetter", mm: vera.fusion?.quantiles?.["0.75"] ?? vera.fusion?.q75 },
                  { k: "Wet", mm: vera.fusion?.quantiles?.["0.9"] ?? vera.fusion?.q90 },
                  { k: "Very wet", mm: vera.fusion?.quantiles?.["0.95"] ?? vera.fusion?.q95 },
                  { k: "Extreme", mm: vera.fusion?.quantiles?.["0.99"] ?? vera.fusion?.q99 },
                ]}
              >
                <CartesianGrid stroke="#cfe0dd" vertical={false} />
                <XAxis dataKey="k" stroke="#4d6b70" fontSize={10} interval={0} angle={-20} height={48} />
                <YAxis stroke="#4d6b70" fontSize={10} width={36} unit=" mm" />
                <Tooltip formatter={(v: number) => `${round2(Number(v))} mm`} />
                <Bar dataKey="mm" fill={COL.blend} radius={[6, 6, 0, 0]} name="Rain" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <AxisHint x="How unusual that rain total is" y="24-hour rain (mm)" />
        </section>
      ) : null}
    </div>
  );
}

const PARAM_LABEL: Record<string, { title: string; unit: string; plain: string }> = {
  rainfall: { title: "Rain", unit: "mm / day", plain: "How much rain the blend expects in 24 h." },
  temperature: { title: "Temperature", unit: "°C", plain: "Daytime high from the gated mix." },
  heat_wave: { title: "Heat wave", unit: "chance", plain: "Share of members crossing IMD heat rules." },
  wind: { title: "Wind (10 m)", unit: "km/h", plain: "Peak 10 m wind in the mix." },
  gusts: { title: "Gusts", unit: "km/h", plain: "Peak gust vs the website hour." },
  hub_wind: { title: "Hub-height wind", unit: "km/h", plain: "Wind at ~100 m (turbine height)." },
  solar: { title: "Solar", unit: "W/m²", plain: "Incoming shortwave at the surface." },
  fog: { title: "Fog / visibility", unit: "m", plain: "Visibility; lower metres = thicker fog." },
  waves: { title: "Waves", unit: "m", plain: "Significant wave height (coast)." },
  aqi: { title: "AQI / PM", unit: "index", plain: "CPCB station if present, else CAMS model." },
  lightning: { title: "Lightning", unit: "chance", plain: "CAPE + thunder codes — not Damini." },
  tropical_cyclone: { title: "Tropical cyclone", unit: "", plain: "Active GDACS storm in the India box, if any." },
};

function quantileBars(h: { q10?: number | null; q50?: number | null; q90?: number | null }) {
  return [
    { k: "Low", v: h.q10 ?? null },
    { k: "Typical", v: h.q50 ?? null },
    { k: "High", v: h.q90 ?? null },
  ].filter((d) => d.v != null);
}

function ParamsSec({ vera, t }: { vera: VeraPack; t: Record<string, string> }) {
  const allHeads = vera.parameters?.heads || [];
  const skipped = allHeads.filter((h) => h.status === "not_wired").length;
  const heads = allHeads.filter((h) => h.status !== "not_wired");
  const by = Object.fromEntries(heads.map((h) => [h.id || "", h]));
  const hours = (vera.hourly || []).filter((r) => (r.lead_h ?? 0) >= 0 && (r.lead_h ?? 0) < 24);
  const hourlyCharts: { id: string; y: string; rows: { t: string; Blend: number | null; Website: number | null; Ensemble: number | null }[] }[] = [
    {
      id: "rainfall",
      y: "mm in that hour",
      rows: hours.map((r) => ({ t: istClock(r.t), Blend: r.moe ?? null, Website: r.om ?? null, Ensemble: r.ensemble ?? null })),
    },
    {
      id: "temperature",
      y: "°C",
      rows: hours.map((r) => ({ t: istClock(r.t), Blend: r.moe_temp_c ?? null, Website: r.om_temp_c ?? null, Ensemble: r.ensemble_temp_c ?? null })),
    },
    {
      id: "wind",
      y: "km/h",
      rows: hours.map((r) => ({ t: istClock(r.t), Blend: r.moe_wind_kmh ?? null, Website: r.om_wind_kmh ?? null, Ensemble: r.ensemble_wind_kmh ?? null })),
    },
    {
      id: "heat_wave",
      y: "WBGT °C",
      rows: hours.map((r) => ({ t: istClock(r.t), Blend: r.moe_wbgt_c ?? null, Website: r.om_wbgt_c ?? null, Ensemble: r.ensemble_wbgt_c ?? null })),
    },
  ];
  const chanceRows = [
    { k: "Heat wave", v: Math.round(((by.heat_wave?.p_exceed ?? by.heat_wave?.q50) || 0) * (by.heat_wave?.p_exceed != null || (by.heat_wave?.q50 ?? 1) <= 1 ? 100 : 1)) },
    { k: "Fog", v: Math.round((by.fog?.p_fog || 0) * 100) },
    { k: "Lightning", v: Math.round((by.lightning?.p_lightning || 0) * 100) },
    { k: "Heavy rain", v: Math.round((vera.fusion?.extremes?.p_ge_64_5 || 0) * 100) },
  ];
  return (
    <div className="space-y-4">
      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.secParams}</p>
        <p className="mt-1 text-sm">{t.paramsHint}</p>
        <p className="mt-1 text-[11px] text-neo-muted">
          Showing {heads.length} heads with a number at this pin.
          {skipped ? ` ${skipped} have no feed here (hidden).` : ""}
        </p>
        <div className="mt-3 overflow-auto">
          <table className="w-full text-left text-[11px]">
            <thead className="text-neo-muted">
              <tr>
                <th className="py-1">What</th>
                <th>Typical (blend q50)</th>
                <th>Low–high</th>
                <th>Status</th>
                <th>How to read it</th>
              </tr>
            </thead>
            <tbody>
              {heads.map((h) => {
                const meta = PARAM_LABEL[h.id || ""] || { title: h.id || "—", unit: h.unit || "", plain: h.source || "" };
                const lo = h.q10 ?? h.q50;
                const hi = h.q90 ?? h.q95 ?? h.q50;
                return (
                  <tr key={h.id} className="border-t border-neo-line">
                    <td className="py-2 font-semibold">{meta.title}</td>
                    <td className="font-mono" style={{ color: COL.blend }}>
                      {h.q50 != null ? `${round2(h.q50)} ${meta.unit}` : "—"}
                    </td>
                    <td className="font-mono text-neo-muted">
                      {lo != null && hi != null ? `${round2(lo)} – ${round2(hi)}` : "—"}
                    </td>
                    <td>{h.status || "—"}</td>
                    <td className="text-neo-muted">{meta.plain}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Next 24 hours — compare Blend vs Website</p>
        <p className="text-[11px] text-neo-muted">Same IST hours on every chart. Purple blend · rust website · teal ensemble (satellite + NWP shape).</p>
        <div className="mt-3 grid gap-4 lg:grid-cols-2">
          {hourlyCharts.map((c) => (
            <div key={c.id} className="neo-in p-3">
              <p className="text-[11px] font-semibold">{PARAM_LABEL[c.id]?.title || c.id}</p>
              <p className="text-[10px] text-neo-muted">{PARAM_LABEL[c.id]?.plain} Vertical: {c.y}.</p>
              <div className="mt-2 h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={c.rows}>
                    <CartesianGrid stroke="#cfe0dd" vertical={false} />
                    <XAxis dataKey="t" stroke="#4d6b70" fontSize={9} />
                    <YAxis stroke="#4d6b70" fontSize={10} width={36} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="Ensemble" stroke={COL.ensemble} strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="Blend" stroke={COL.blend} strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="Website" stroke={COL.om} strokeDasharray="4 3" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Range for each blended head</p>
        <p className="text-[11px] text-neo-muted">
          Low = drier / cooler / calmer tenth of the mix. Typical = the number we quote. High = wetter / hotter / windier tenth. Unit is on each chart.
        </p>
        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {heads
            .filter((h) => quantileBars(h).length >= 2)
            .map((h) => (
              <div key={h.id} className="neo-in p-3">
                <p className="text-[11px] font-semibold">{PARAM_LABEL[h.id || ""]?.title || h.id}</p>
                <p className="text-[10px] text-neo-muted">{PARAM_LABEL[h.id || ""]?.unit}</p>
                <div className="mt-2 h-36">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={quantileBars(h)}>
                      <CartesianGrid stroke="#cfe0dd" vertical={false} />
                      <XAxis dataKey="k" stroke="#4d6b70" fontSize={9} />
                      <YAxis stroke="#4d6b70" fontSize={10} width={32} />
                      <Tooltip formatter={(v: number) => `${round2(Number(v))} ${PARAM_LABEL[h.id || ""]?.unit || ""}`} />
                      <Bar dataKey="v" fill={COL.blend} radius={[6, 6, 0, 0]} name="Value" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ))}
        </div>
      </section>

      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Chances (percent)</p>
        <p className="text-[11px] text-neo-muted">Not a warning colour. 0% = unlikely, 100% = every member agrees it happens.</p>
        <div className="mt-2 h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chanceRows}>
              <CartesianGrid stroke="#cfe0dd" vertical={false} />
              <XAxis dataKey="k" stroke="#4d6b70" fontSize={11} />
              <YAxis stroke="#4d6b70" fontSize={10} width={28} domain={[0, 100]} />
              <Tooltip />
              <Bar dataKey="v" fill={COL.nwp} radius={[6, 6, 0, 0]} name="Chance %" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}

function ExtremesSec({ vera }: { vera: VeraPack }) {
  const x = vera.extremes;
  const [p48, setP48] = useState<"rain" | "temp" | "wind" | "heat">("rain");
  const cards = [
    { k: "Heat", v: x?.heat_wave },
    { k: "Wind", v: x?.high_wind },
    { k: "Heavy rain", v: x?.heavy_rain },
  ];
  const cmp = x?.compare?.hourly || [];
  const units = { rain: "mm per hour", temp: "°C", wind: "km/h", heat: "°C WBGT" };
  const series = cmp.map((r) => ({
    h: r.h,
    Ensemble: p48 === "rain" ? r.ensemble_mm : p48 === "temp" ? r.ensemble_temp_c : p48 === "wind" ? r.ensemble_wind_kmh : r.ensemble_wbgt_c,
    Blend: p48 === "rain" ? r.blend_mm : p48 === "temp" ? r.blend_temp_c : p48 === "wind" ? r.blend_wind_kmh : r.blend_wbgt_c,
    Website: p48 === "rain" ? r.website_mm : p48 === "temp" ? r.website_temp_c : p48 === "wind" ? r.website_wind_kmh : r.website_wbgt_c,
  }));
  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-3">
        {cards.map((c) => (
          <div key={c.k} className="neo p-4">
            <p className="text-[10px] uppercase tracking-widest text-neo-muted">{c.k}</p>
            <p className="text-lg font-bold text-neo-accent">{c.v?.level || "—"}</p>
            <p className="font-mono text-sm">chance {c.v?.p != null ? Math.round((c.v.p || 0) * 100) : "—"}%</p>
            <p className="mt-1 text-[11px] text-neo-muted">{c.v?.rule}</p>
          </div>
        ))}
      </div>
      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Next 72 hours — Ensemble, Blend, Website</p>
        <p className="text-[11px] text-neo-muted">Same hour values as Hourly and Intra. Hours from now are 0…71.</p>
        <div className="mt-2 flex flex-wrap gap-1">
          {(["rain", "temp", "wind", "heat"] as const).map((k) => (
            <button key={k} type="button" className={`neo-btn text-[11px] ${p48 === k ? "neo-btn-on" : ""}`} onClick={() => setP48(k)}>
              {k === "rain" ? "Rain (mm/h)" : k === "temp" ? "Temperature (°C)" : k === "wind" ? "Wind (km/h)" : "Heat WBGT (°C)"}
            </button>
          ))}
        </div>
        <div className="mt-2 h-48">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={series}>
              <CartesianGrid stroke="#cfe0dd" vertical={false} />
              <XAxis dataKey="h" fontSize={10} stroke="#4d6b70" />
              <YAxis fontSize={10} stroke="#4d6b70" width={36} />
              <Tooltip />
              <Legend />
              <Line dataKey="Ensemble" stroke={COL.ensemble} strokeWidth={2.5} dot={false} />
              <Line dataKey="Blend" stroke={COL.blend} strokeWidth={2} dot={false} />
              <Line dataKey="Website" stroke={COL.om} strokeDasharray="4 3" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <AxisHint x="Hours from now (0–71)" y={`${p48 === "rain" ? "Rain" : p48 === "temp" ? "Air temperature" : p48 === "wind" ? "Wind speed" : "WBGT"} (${units[p48]})`} />
      </section>
      <section className="neo overflow-auto p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Blend vs website (table)</p>
        <p className="text-[11px] text-neo-muted">{x?.compare?.note}</p>
        <table className="mt-2 w-full text-left text-[11px]">
          <thead className="text-neo-muted">
            <tr>
              <th className="py-1">Hour from now</th>
              <th style={{ color: COL.ensemble }}>Ensemble</th>
              <th style={{ color: COL.blend }}>Blend</th>
              <th style={{ color: COL.om }}>Website</th>
            </tr>
          </thead>
          <tbody>
            {cmp.map((r) => (
              <tr key={r.h} className="border-t border-neo-line">
                <td className="py-1 font-mono">{r.h}</td>
                <td className="font-mono">{round2(series.find((s) => s.h === r.h)?.Ensemble)}</td>
                <td className="font-mono">{round2(series.find((s) => s.h === r.h)?.Blend)}</td>
                <td className="font-mono">{round2(series.find((s) => s.h === r.h)?.Website)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function CompareSec({ vera }: { vera: VeraPack }) {
  const hours = (vera.hourly || []).filter((r) => {
    const h = r.lead_h ?? 0;
    return h >= 0 && h < 24;
  });
  const ids = Object.keys(hours[0]?.members || {});
  const [on, setOn] = useState<string[]>(["Ensemble", "Blend", "Website", ...ids]);
  const data = hours.map((r) => ({ t: istClock(r.t), Ensemble: r.ensemble, Blend: r.moe, Website: r.om, ...(r.members || {}) }));
  const keys = ["Ensemble", "Blend", "Website", ...ids];
  function tog(id: string) {
    setOn((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }
  return (
    <section className="neo p-4">
      <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Compare 24 h</p>
      <div className="mt-2 flex flex-wrap gap-1">
        {keys.map((id) => (
          <button key={id} type="button" className={`neo-btn text-[11px] ${on.includes(id) ? "neo-btn-on" : ""}`} onClick={() => tog(id)} style={{ borderColor: strokeOf(id) }}>
            {id} · {familyLabel(id)}
          </button>
        ))}
      </div>
      <div className="mt-2 h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid stroke="#cfe0dd" vertical={false} />
            <XAxis dataKey="t" fontSize={10} stroke="#4d6b70" />
            <YAxis fontSize={10} stroke="#4d6b70" width={32} />
            <Tooltip />
            <Legend />
            {keys.filter((id) => on.includes(id)).map((id) => (
              <Line key={id} dataKey={id} stroke={strokeOf(id)} dot={false} strokeWidth={id === "Ensemble" || id === "Blend" ? 2.5 : 1.4} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <AxisHint x="Valid hour (IST)" y="Rain (mm in that hour)" />
    </section>
  );
}

function PerfSec({ vera, t }: { vera: VeraPack; t: Record<string, string> }) {
  const [mode, setMode] = useState<"live" | "cv" | "hist">("live");
  const p = vera.performance;
  const agr = p?.agreement;
  const ensA = agr?.ensemble;
  const moeA = agr?.moe;
  const mem = Object.entries(agr?.members || p?.scores?.members || {}).map(([k, v]) => ({ k, mae: v.mae, family: familyOf(k) }));
  const bars = [
    { k: "ensemble", mae: ensA?.mae, family: "ensemble" },
    { k: "blend", mae: moeA?.mae, family: "blend" },
    ...mem,
  ];
  const hist = (p?.history || []).map((h) => ({ d: h.date.slice(5), ensemble: h.ensemble_mae, ...h.members }));
  const hh = (p?.hourly_history || []).map((r) => ({
    t: (r.t || "").slice(5, 16),
    ensemble: r.ensemble,
    blend: r.moe,
    om: r.om,
  }));
  return (
    <div className="space-y-3">
      <div className="neo flex flex-wrap gap-2 p-3">
        {(["live", "cv", "hist"] as const).map((m) => (
          <button key={m} type="button" className={`neo-btn ${mode === m ? "neo-btn-on" : ""}`} onClick={() => setMode(m)}>
            {m === "live" ? t.perfLive : m === "cv" ? t.perfCv : t.perfHist}
          </button>
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Kpi label="Ensemble vs website MAE" value={ensA?.mae != null ? `${ensA.mae}` : "—"} sub={`${ensA?.n ?? agr?.n ?? 0} hours`} />
        <Kpi label="Blend vs website MAE" value={moeA?.mae != null ? `${moeA.mae}` : "—"} sub="gated mix vs Open-Meteo" />
        <Kpi
          label="Independent skill"
          value={p?.independent_obs && p?.scores?.skill_vs_om != null ? String(p.scores.skill_vs_om) : "Not available"}
          sub={p?.independent_obs ? "vs IMERG / gauge hours" : "No independent rain observations yet. The MAE figures on the left are vs the website, not skill."}
        />
      </div>
      {mode === "live" ? (
        <section className="neo p-4">
          <p className="text-[11px] text-neo-muted">Lower MAE = closer to Open-Meteo. Orange = AI, blue = NWP, purple = blend, teal = ensemble. Not a rain-gauge score.</p>
          <div className="mt-2 h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={bars}>
                <CartesianGrid stroke="#cfe0dd" vertical={false} />
                <XAxis dataKey="k" fontSize={9} interval={0} angle={-20} height={48} stroke="#4d6b70" />
                <YAxis fontSize={10} width={32} stroke="#4d6b70" />
                <Tooltip />
                <Bar dataKey="mae" radius={[6, 6, 0, 0]}>
                  {bars.map((d) => (
                    <Cell key={d.k} fill={strokeOf(d.k)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      ) : null}
      {mode === "cv" ? (
        <section className="neo p-4">
          <p className="text-sm font-semibold">Walk-forward (frozen weights)</p>
          <p className="text-xs text-neo-muted">{p?.cv?.method || p?.cv?.note}</p>
          <p className="mt-2 font-mono text-2xl text-neo-accent">MAE {p?.cv?.mae_mean ?? "—"} ± {p?.cv?.mae_std ?? "—"}</p>
          <p className="text-xs">{p?.cv?.folds ?? 0} folds</p>
        </section>
      ) : null}
      {mode === "hist" ? (
        <div className="space-y-3">
          <section className="neo p-4">
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Hourly history</p>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={hh}>
                  <CartesianGrid stroke="#cfe0dd" vertical={false} />
                  <XAxis dataKey="t" fontSize={9} stroke="#4d6b70" />
                  <YAxis fontSize={10} width={32} stroke="#4d6b70" />
                  <Tooltip />
                  <Legend />
                  <Line dataKey="ensemble" stroke={COL.ensemble} strokeWidth={2} dot={false} />
                  <Line dataKey="blend" stroke={COL.blend} strokeWidth={2} dot={false} />
                  <Line dataKey="om" stroke={COL.om} strokeDasharray="4 3" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>
          <section className="neo p-4">
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Daily MAE history</p>
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={hist}>
                  <CartesianGrid stroke="#cfe0dd" vertical={false} />
                  <XAxis dataKey="d" fontSize={10} stroke="#4d6b70" />
                  <YAxis fontSize={10} width={32} stroke="#4d6b70" />
                  <Tooltip />
                  <Legend />
                  <Line dataKey="ensemble" stroke={COL.ensemble} strokeWidth={2.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}

function LeadsSec({ vera }: { vera: VeraPack }) {
  const rows = vera.leads || [];
  return (
    <section className="neo overflow-auto p-4">
      <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Standard lead times</p>
      <p className="text-[11px] text-neo-muted">Blend is the gated member mix (not Ensemble). Website is Open-Meteo. Values are rounded to 0.01.</p>
      <table className="mt-2 w-full text-left text-[11px]">
        <thead className="text-neo-muted">
          <tr>
            <th className="py-1">Look-ahead</th>
            <th style={{ color: COL.blend }}>Blend rain (mm)</th>
            <th style={{ color: COL.om }}>Website rain (mm)</th>
            <th>Chance of heavy rain</th>
            <th>Hottest day (°C)</th>
            <th>Coolest night (°C)</th>
            <th>Strongest wind (km/h)</th>
            <th>Chance of ≥40 °C</th>
            <th>Chance of ≥60 km/h</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.lead_h} className="border-t border-neo-line">
              <td className="py-1 font-mono">{r.lead_h === 24 ? "1 day" : r.lead_h === 72 ? "3 days" : r.lead_h === 120 ? "5 days" : "10 days"}</td>
              <td className="font-mono">{round2(r.rain?.q50)}</td>
              <td className="font-mono">{round2(r.rain?.website)}</td>
              <td className="font-mono">{r.rain?.p_exceed != null ? `${Math.round(r.rain.p_exceed * 100)}%` : "—"}</td>
              <td className="font-mono">{round2(r.tmax?.q50)}</td>
              <td className="font-mono">{round2(r.tmin?.q50)}</td>
              <td className="font-mono">{round2(r.wind?.q50)}</td>
              <td className="font-mono">{r.tmax?.p_exceed != null ? `${Math.round(r.tmax.p_exceed * 100)}%` : "—"}</td>
              <td className="font-mono">{r.wind?.p_exceed != null ? `${Math.round(r.wind.p_exceed * 100)}%` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <ul className="mt-3 space-y-1 text-[11px] text-neo-muted">
        <li><strong>Look-ahead</strong> — how far forward the row covers (1 / 3 / 5 / 10 days).</li>
        <li><strong>Blend rain</strong> — typical rain total from the gated member mix (middle of the pack).</li>
        <li><strong>Website rain</strong> — same total from Open-Meteo, the feed weather apps use.</li>
        <li><strong>Chance of heavy rain</strong> — share of members at or above IMD 64.5 mm in that window.</li>
        <li><strong>Hottest / coolest</strong> — blend daytime high and night low.</li>
        <li><strong>Strongest wind</strong> — blend peak 10 m wind.</li>
        <li><strong>Chance of ≥40 °C / ≥60 km/h</strong> — share of members crossing those heat and wind lines.</li>
      </ul>
    </section>
  );
}

function ExplainSec({ vera }: { vera: VeraPack }) {
  const attn = vera.gate?.cross_attn;
  return (
    <section className="neo space-y-3 p-4">
      <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Why these weights today</p>
      <ul className="mt-2 space-y-3 text-sm">
        {(vera.gate?.explain || []).map((e) => (
          <li key={e.factor} className="border-t border-neo-line pt-2">
            <p className="font-semibold capitalize">{e.factor}</p>
            <p className="text-xs text-neo-muted">{e.detail}</p>
            <p className="mt-1 text-xs">{e.shift}</p>
          </li>
        ))}
      </ul>
      {attn?.weights?.length ? (
        <div className="overflow-auto">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Cross-attention</p>
          <p className="text-[10px] text-neo-muted">Forecasts query satellite / regime / historical / initiation / cold cloud.</p>
          <table className="mt-2 w-full text-left text-[10px]">
            <thead>
              <tr>
                <th className="py-1">Member</th>
                {(attn.conditions || []).map((c) => (
                  <th key={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(attn.members || []).map((m, i) => (
                <tr key={m} className="border-t border-neo-line">
                  <td className="py-1 font-mono">{m}</td>
                  {(attn.weights?.[i] || []).map((v, j) => (
                    <td key={j} className="font-mono" style={{ background: `rgba(142,68,173,${Math.min(1, v)})` }}>
                      {v.toFixed(2)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function OmBlendSec({ vera, t }: { vera: VeraPack; t: Record<string, string> }) {
  const pack = vera.performance?.om_blend;
  const rows = pack?.issued_rows || [];
  const chart = rows.map((r) => ({
    t: istClock(r.t),
    Blend: r.blend,
    OpenMeteo: r.om_issued,
    Obs: r.obs,
  }));
  const leads = Object.entries(pack?.by_lead || {}).map(([k, v]) => ({
    k,
    blend: v.blend?.mae,
    om: v.om?.mae,
  }));
  return (
    <div className="space-y-3">
      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.secOmBlend}</p>
        <p className="mt-1 text-xs text-neo-muted">{t.omBlendCaption}</p>
      </section>
      <div className="grid gap-3 sm:grid-cols-3">
        <Kpi
          label={t.omBlendAgree}
          value={pack?.agreement_mae != null ? String(pack.agreement_mae) : "—"}
          sub={`${pack?.agreement_n ?? 0} ${t.omBlendHoursIssued}`}
        />
        <Kpi
          label={t.omBlendSkill}
          value={pack?.independent_obs && pack?.skill_vs_om != null ? String(pack.skill_vs_om) : t.omBlendNoSkill}
          sub={pack?.independent_obs ? t.omBlendSkillHint : t.omBlendWaitObs}
        />
        <Kpi
          label={t.omBlendCounts}
          value={`${pack?.n_verified ?? 0} / ${pack?.n_issued ?? 0}`}
          sub={t.omBlendVerified}
        />
      </div>
      {chart.length ? (
        <section className="neo p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.omBlendChart}</p>
          <div className="mt-2 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chart}>
                <CartesianGrid stroke="#cfe0dd" vertical={false} />
                <XAxis dataKey="t" fontSize={10} stroke="#4d6b70" />
                <YAxis fontSize={10} width={32} stroke="#4d6b70" />
                <Tooltip />
                <Legend />
                <Line dataKey="Blend" stroke={COL.blend} strokeWidth={2.4} dot={false} />
                <Line dataKey="OpenMeteo" stroke={COL.om} strokeDasharray="4 3" dot={false} />
                <Line dataKey="Obs" stroke="#1b4f72" strokeWidth={2} dot={false} connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <AxisHint x={t.omBlendAxisX} y={t.omBlendAxisY} />
        </section>
      ) : (
        <p className="text-sm text-neo-muted">{t.omBlendEmpty}</p>
      )}
      {leads.some((r) => r.blend != null || r.om != null) ? (
        <section className="neo p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.omBlendByLead}</p>
          <div className="mt-2 h-44">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={leads}>
                <CartesianGrid stroke="#cfe0dd" vertical={false} />
                <XAxis dataKey="k" fontSize={10} stroke="#4d6b70" />
                <YAxis fontSize={10} width={32} stroke="#4d6b70" />
                <Tooltip />
                <Legend />
                <Bar dataKey="blend" name="Blend MAE" fill={COL.blend} radius={[6, 6, 0, 0]} />
                <Bar dataKey="om" name="Open-Meteo MAE" fill={COL.om} radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      ) : null}
      {rows.length ? (
        <section className="neo overflow-x-auto p-4">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-neo-muted">
                <th className="py-1">{t.omBlendValid}</th>
                <th>Lead</th>
                <th>Blend</th>
                <th>OM issued</th>
                <th>Obs</th>
                <th>{t.omBlendSource}</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(-24).map((r, i) => (
                <tr key={`${r.t}-${r.lead_h}-${i}`} className="border-t border-neo-line font-mono">
                  <td className="py-1">{istClock(r.t)}</td>
                  <td>{r.lead_h ?? "—"}</td>
                  <td>{round2(r.blend)}</td>
                  <td>{round2(r.om_issued)}</td>
                  <td>{r.obs == null ? t.omBlendPending : round2(r.obs)}</td>
                  <td className="text-neo-muted">{r.obs_source || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
    </div>
  );
}

function DisagreeSec({ vera }: { vera: VeraPack }) {
  const d = vera.disagreement;
  const idx = [
    { k: "Rain", v: d?.rain ?? 0 },
    { k: "Temperature", v: d?.temp ?? 0 },
    { k: "Wind", v: d?.wind ?? 0 },
  ];
  const range = [
    { k: "Driest member", v: d?.member_rain?.min ?? 0 },
    { k: "Wettest member", v: d?.member_rain?.max ?? 0 },
  ];
  const leads = (d?.by_lead || []).map((r) => ({
    h: `${r.lead_h} h`,
    low: Array.isArray(r.rain_range) ? r.rain_range[0] : 0,
    high: Array.isArray(r.rain_range) ? r.rain_range[1] : 0,
  }));
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <Kpi label="Rain disagreement" value={d?.rain != null ? round2(d.rain) : "—"} sub="0 = models agree · 1 = wide split" />
        <Kpi label="Temp disagreement" value={d?.temp != null ? round2(d.temp) : "—"} />
        <Kpi label="Wind disagreement" value={d?.wind != null ? round2(d.wind) : "—"} />
      </div>
      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">How far the models split</p>
        <p className="text-[11px] text-neo-muted">{d?.note}</p>
        <div className="mt-2 h-40">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={idx}>
              <CartesianGrid stroke="#cfe0dd" vertical={false} />
              <XAxis dataKey="k" fontSize={10} />
              <YAxis fontSize={10} width={32} domain={[0, 1]} />
              <Tooltip />
              <Bar dataKey="v" name="Disagreement (0–1)" fill={COL.nwp} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <AxisHint x="Weather field" y="Disagreement index (0 = agree, 1 = strongly split)" />
      </section>
      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Tomorrow’s rain: driest vs wettest member</p>
        <div className="h-40">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={range}>
              <CartesianGrid stroke="#cfe0dd" vertical={false} />
              <XAxis dataKey="k" fontSize={10} />
              <YAxis fontSize={10} width={36} />
              <Tooltip />
              <Bar dataKey="v" name="Rain (mm)" fill={COL.blend} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <AxisHint x="Member extreme" y="Rain next day (mm)" />
      </section>
      {leads.length ? (
        <section className="neo p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Blend rain spread by look-ahead</p>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={leads}>
                <CartesianGrid stroke="#cfe0dd" vertical={false} />
                <XAxis dataKey="h" fontSize={10} />
                <YAxis fontSize={10} width={36} />
                <Tooltip />
                <Legend />
                <Line dataKey="low" name="Low (dry side)" stroke={COL.nwp} dot={false} />
                <Line dataKey="high" name="High (wet side)" stroke={COL.om} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <AxisHint x="Look-ahead" y="Blend rain range (mm)" />
        </section>
      ) : null}
      <section className="neo p-4">
        {(d?.flags || []).length ? (
          <ul className="space-y-2">
            {(d?.flags || []).map((f) => (
              <li key={f.id} className="neo-in p-3">
                <p className="font-semibold text-sm">{f.title}</p>
                <p className="text-xs text-neo-muted">{f.detail}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm">No high-impact / low-confidence flag on this pin.</p>
        )}
      </section>
    </div>
  );
}

function BoardSec({ vera }: { vera: VeraPack }) {
  const rows = vera.performance?.leaderboard || [];
  const cl = vera.performance?.cost_loss;
  return (
    <div className="space-y-3">
      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Skill vs website (MAE)</p>
        <p className="text-[11px] text-neo-muted">Lower is closer to Open-Meteo. Equal-weight is the naive blend baseline.</p>
        <div className="mt-2 h-52">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows}>
              <CartesianGrid stroke="#cfe0dd" vertical={false} />
              <XAxis dataKey="id" fontSize={9} interval={0} angle={-20} height={48} />
              <YAxis fontSize={10} width={32} />
              <Tooltip />
              <Bar dataKey="mae" radius={[6, 6, 0, 0]}>
                {rows.map((r) => (
                  <Cell key={r.id} fill={strokeOf(r.family === "baseline" ? "om" : r.id)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Warning value</p>
        <p className="text-sm">Relative value vs never warning: {cl?.value_vs_never ?? "—"} (P={cl?.p_event ?? "—"})</p>
        <p className="text-[11px] text-neo-muted">{cl?.note}</p>
      </section>
    </div>
  );
}

function ReplaySec({ vera }: { vera: VeraPack }) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {(vera.replay?.cases || []).map((c) => (
        <section key={c.id} className="neo p-4">
          <p className="text-[10px] uppercase tracking-widest text-neo-muted">{c.kind}</p>
          <p className="text-sm font-semibold">{c.title}</p>
          <p className="text-xs text-neo-muted">{c.place} · {c.date}</p>
          <p className="mt-2 text-xs leading-relaxed">{c.signal}</p>
          <p className="mt-2 text-[11px] text-neo-muted">{c.note}</p>
        </section>
      ))}
    </div>
  );
}

function IntraSec({ vera }: { vera: VeraPack }) {
  const days = vera.intra_hour?.days || [];
  const [di, setDi] = useState(0);
  const [varK, setVarK] = useState<"rain" | "temp" | "wind" | "heat">("rain");
  const [vsWeb, setVsWeb] = useState(true);
  const day = days[di] || days[0];
  const hours = day?.hours || [];
  function dayPoint(h: (typeof hours)[number]) {
    if (varK === "temp") return { Ensemble: h.ensemble_temp_c, Blend: h.blend_temp_c, Website: h.temp_c };
    if (varK === "wind") return { Ensemble: h.ensemble_wind_kmh, Blend: h.blend_wind_kmh, Website: h.wind_kmh };
    if (varK === "heat") return { Ensemble: h.ensemble_wbgt_c, Blend: h.blend_wbgt_c, Website: h.wbgt_c };
    return { Ensemble: h.ensemble_mm, Blend: h.blend_mm, Website: h.website_mm ?? h.rain_mm };
  }
  const chart = hours.map((h) => ({ t: istClock(h.t), ...dayPoint(h) }));
  const horizon = (vera.intra_hour?.horizon || []).map((h) => ({
    t: `${h.lead_h ?? ""}`,
    ...(varK === "temp"
      ? { Ensemble: h.ensemble_temp_c, Blend: h.blend_temp_c, Website: h.temp_c }
      : varK === "wind"
        ? { Ensemble: h.ensemble_wind_kmh, Blend: h.blend_wind_kmh, Website: h.wind_kmh }
        : varK === "heat"
          ? { Ensemble: h.ensemble_wbgt_c, Blend: h.blend_wbgt_c, Website: h.wbgt_c }
          : { Ensemble: h.ensemble_mm, Blend: h.blend_mm, Website: h.website_mm }),
  }));
  const mins = (di === 0 ? day?.minutes_today : day?.peak_minutes) || [];
  const mchart = mins.map((m) => {
    if (varK === "temp") return { t: istClock(m.t), Website: m.temp_c, Blend: m.blend_temp_c ?? m.temp_c, Ensemble: m.ensemble_temp_c ?? m.temp_c };
    if (varK === "wind") return { t: istClock(m.t), Website: m.wind_kmh, Blend: m.blend_wind_kmh ?? m.wind_kmh, Ensemble: m.ensemble_wind_kmh ?? m.wind_kmh };
    if (varK === "heat") return { t: istClock(m.t), Website: m.wbgt_c, Blend: m.blend_wbgt_c ?? m.wbgt_c, Ensemble: m.ensemble_wbgt_c ?? m.wbgt_c };
    return { t: istClock(m.t), Website: m.website_mm_h ?? m.rain_mm_h, Blend: m.blend_mm_h, Ensemble: m.ensemble_mm_h };
  });
  const web = mchart.map((m) => Number(m.Website || 0));
  const bl = mchart.map((m) => Number(m.Blend || 0));
  const n = Math.min(web.length, bl.length) || 1;
  const mae = bl.length ? bl.reduce((s, v, i) => s + Math.abs(v - (web[i] || 0)), 0) / n : null;
  const peak = mchart.reduce((p, m) => Math.max(p, Number(m.Website || 0), Number(m.Blend || 0)), 0);
  const total = mins.reduce((s, m) => s + Number(m.rain_mm || 0), 0);
  const yHour = varK === "rain" ? "Rain (mm in the hour)" : varK === "temp" ? "Temperature (°C)" : varK === "wind" ? "Wind (km/h)" : "WBGT heat (°C)";
  const yMin = varK === "rain" ? "Rain rate (mm/h)" : yHour;
  const unit = varK === "rain" ? "mm/h" : varK === "temp" ? "°C" : varK === "wind" ? "km/h" : "°C WBGT";
  const tipFmt = (v: number) => `${round2(v)} ${unit}`;
  return (
    <div className="space-y-3">
      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Inside each hour</p>
        <p className="text-[11px] text-neo-muted">{vera.intra_hour?.note} Times are IST.</p>
        <div className="mt-2 flex flex-wrap gap-1">
          {days.map((d, i) => (
            <button key={d.date} type="button" className={`neo-btn text-[11px] ${di === i ? "neo-btn-on" : ""}`} onClick={() => setDi(i)}>
              {d.label || d.date} {d.weekday ? `· ${d.weekday}` : ""}
            </button>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          {(["rain", "temp", "wind", "heat"] as const).map((k) => (
            <button key={k} type="button" className={`neo-btn text-[11px] ${varK === k ? "neo-btn-on" : ""}`} onClick={() => setVarK(k)}>
              {k === "rain" ? "Rain (mm)" : k === "temp" ? "Temperature (°C)" : k === "wind" ? "Wind (km/h)" : "Heat WBGT (°C)"}
            </button>
          ))}
          <button type="button" className={`neo-btn text-[11px] ${vsWeb ? "neo-btn-on" : ""}`} onClick={() => setVsWeb((v) => !v)}>
            {vsWeb ? "Compare with website: on" : "Compare with website: off"}
          </button>
        </div>
        {day ? (
          <p className="mt-2 text-xs">
            {day.label} ({day.date} IST) · rain {round2(day.rain_mm)} mm · Tmax {day.tmax_c ?? "—"} °C · Tmin {day.tmin_c ?? "—"} °C · wind {day.wind_max_kmh ?? "—"} km/h · heat {day.heat_level}
          </p>
        ) : null}
        <div className="mt-2 h-56">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chart}>
              <CartesianGrid stroke="#cfe0dd" vertical={false} />
              <XAxis dataKey="t" fontSize={10} />
              <YAxis fontSize={10} width={36} />
              <Tooltip formatter={(v: number) => tipFmt(Number(v))} />
              <Legend />
              <Line dataKey="Ensemble" stroke={COL.ensemble} strokeWidth={2.5} dot={false} />
              <Line dataKey="Blend" stroke={COL.blend} strokeWidth={2} dot={false} />
              {vsWeb ? <Line dataKey="Website" stroke={COL.om} strokeDasharray="4 3" strokeWidth={2} dot={false} /> : null}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <AxisHint x="Valid hour (IST)" y={yHour} />
      </section>
      {horizon.length ? (
        <section className="neo p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Next 72 hours · Blend vs website</p>
          <p className="text-[11px] text-neo-muted">Hour 0 is now. Same millimetres / °C / km/h as the Hourly tab.</p>
          <div className="mt-2 h-52">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={horizon}>
                <CartesianGrid stroke="#cfe0dd" vertical={false} />
                <XAxis dataKey="t" fontSize={10} />
                <YAxis fontSize={10} width={36} />
                <Tooltip formatter={(v: number) => tipFmt(Number(v))} />
                <Legend />
                <Line dataKey="Ensemble" stroke={COL.ensemble} strokeWidth={2} dot={false} />
                <Line dataKey="Blend" stroke={COL.blend} strokeWidth={2} dot={false} />
                {vsWeb ? <Line dataKey="Website" stroke={COL.om} strokeDasharray="4 3" strokeWidth={2} dot={false} /> : null}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <AxisHint x="Hours from now (0–71)" y={yHour} />
        </section>
      ) : null}
      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{day?.label === "Today" ? "15-minute shape (today)" : "Peak-hour 5-minute shape"}</p>
        <div className="mt-2 grid gap-2 sm:grid-cols-3">
          <Kpi
            label={varK === "rain" ? "Peak rain rate" : varK === "temp" ? "Peak temperature" : varK === "wind" ? "Peak wind" : "Peak WBGT"}
            value={peak ? `${round2(peak)} ${unit}` : "—"}
          />
          <Kpi
            label={varK === "rain" ? "Rain in this strip" : "Blend vs website"}
            value={varK === "rain" ? `${round2(total)} mm` : mae != null ? `${round2(mae)} ${unit}` : "—"}
            sub={varK === "rain" ? "sums to the locked hour" : "mean absolute difference"}
          />
          <Kpi label="Blend vs website MAE" value={mae != null ? `${round2(mae)} ${unit}` : "Not available"} />
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          {(["rain", "temp", "wind", "heat"] as const).map((k) => (
            <button key={k} type="button" className={`neo-btn text-[11px] ${varK === k ? "neo-btn-on" : ""}`} onClick={() => setVarK(k)}>
              {k === "rain" ? "Rain (mm/h)" : k === "temp" ? "Temperature (°C)" : k === "wind" ? "Wind (km/h)" : "Heat WBGT (°C)"}
            </button>
          ))}
        </div>
        <div className="mt-2 h-44">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={mchart}>
              <CartesianGrid stroke="#cfe0dd" vertical={false} />
              <XAxis dataKey="t" fontSize={9} />
              <YAxis fontSize={10} width={36} />
              <Tooltip formatter={(v: number) => tipFmt(Number(v))} />
              <Legend />
              <Line dataKey="Ensemble" stroke={COL.ensemble} strokeWidth={2} dot={false} />
              <Line dataKey="Blend" stroke={COL.blend} strokeWidth={2} dot={false} />
              {vsWeb ? <Line dataKey="Website" stroke={COL.om} strokeDasharray="4 3" strokeWidth={2} dot={false} /> : null}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <AxisHint x="Clock time (IST)" y={yMin} />
      </section>
    </div>
  );
}
