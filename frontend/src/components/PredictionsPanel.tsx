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
    ["explain", t.secExplain],
    ["disagree", t.secDisagree],
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
        <div className="mt-3 grid gap-2 sm:grid-cols-4 font-mono text-[11px]">
          <div className="neo-in p-2">CNN {JSON.stringify(vera.cv?.stage1_cnn?.shape)}</div>
          <div className="neo-in p-2">ConvLSTM {JSON.stringify(vera.cv?.stage2_convlstm?.shape)}</div>
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
            q10 {vera.fusion?.q10} · q25 {vera.fusion?.q25} · q50 {vera.fusion?.q50} · q75 {vera.fusion?.q75} · q90{" "}
            {vera.fusion?.q90} mm · P(≥64.5){" "}
            {vera.fusion?.extremes?.p_ge_64_5} · P(≥115.6) {vera.fusion?.extremes?.p_ge_115_6}
          </p>
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
  const rows = (vera.hourly || []).filter((r) => (r.lead_h ?? 0) < 24);
  const chart = rows.map((r) => ({
    h: r.lead_h ?? 0,
    t: istClock(r.t),
    Ensemble: r.ensemble,
    Blend: r.moe,
    Website: r.om,
  }));
  const nowIst = new Date().toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });
  return (
    <section className="neo space-y-3 p-4">
      <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.secHourly}</p>
      <p className="text-xs text-neo-muted">
        Clock now (IST): {nowIst}. Times below are valid hours in India Standard Time — not UTC.
        <strong> Ensemble</strong> = satellite rain shape plus NWP. <strong>Blend</strong> = gated mix of physics/AI members. <strong>Website</strong> = Open-Meteo. They are three different series.
      </p>
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
      <AxisHint x="Valid hour (IST)" y="Rain (mm in that hour)" />
      <div className="overflow-auto">
        <table className="w-full text-left text-[11px]">
          <thead className="text-neo-muted">
            <tr>
              <th className="py-1">Hours ahead</th>
              <th>Valid time (IST)</th>
              <th style={{ color: COL.ensemble }}>Ensemble rain (mm)</th>
              <th style={{ color: COL.blend }}>Blend rain (mm)</th>
              <th style={{ color: COL.om }}>Website rain (mm)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const ts = r.t ? new Date(r.t).getTime() : NaN;
              const isNow = !Number.isNaN(ts) && Math.abs(ts - now) < 35 * 60 * 1000;
              return (
              <tr key={`${r.t}-${r.lead_h}`} className="border-t border-neo-line">
                <td className="py-1 font-mono">{r.lead_h}{isNow ? " · now" : ""}</td>
                <td className="font-mono">{istClock(r.t)}</td>
                <td className="font-mono" style={{ color: COL.ensemble }}>{round2(r.ensemble)}</td>
                <td className="font-mono" style={{ color: COL.blend }}>{round2(r.moe)}</td>
                <td className="font-mono" style={{ color: COL.om }}>{round2(r.om)}</td>
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
    </div>
  );
}

function ExtremesSec({ vera }: { vera: VeraPack }) {
  const x = vera.extremes;
  const [p48, setP48] = useState<"rain" | "temp" | "wind">("rain");
  const cards = [
    { k: "Heat", v: x?.heat_wave },
    { k: "Wind", v: x?.high_wind },
    { k: "Heavy rain", v: x?.heavy_rain },
  ];
  const cmp = x?.compare?.hourly || [];
  const units = { rain: "mm per hour", temp: "°C", wind: "km/h" };
  const series = cmp.map((r) => ({
    h: r.h,
    Blend: p48 === "rain" ? r.blend_mm : p48 === "temp" ? null : null,
    Website: p48 === "rain" ? r.website_mm : p48 === "temp" ? r.website_temp_c : r.website_wind_kmh,
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
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Next 48 hours — Blend vs website</p>
        <p className="text-[11px] text-neo-muted">Blend is the gated member mix. Website is Open-Meteo. This plot is not the satellite Ensemble.</p>
        <div className="mt-2 flex flex-wrap gap-1">
          {(["rain", "temp", "wind"] as const).map((k) => (
            <button key={k} type="button" className={`neo-btn text-[11px] ${p48 === k ? "neo-btn-on" : ""}`} onClick={() => setP48(k)}>
              {k === "rain" ? "Rain (mm/h)" : k === "temp" ? "Temperature (°C)" : "Wind (km/h)"}
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
              {p48 === "rain" ? <Line dataKey="Blend" stroke={COL.blend} dot={false} /> : null}
              <Line dataKey="Website" stroke={COL.om} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <AxisHint x="Hours from now (0–47)" y={`${p48 === "rain" ? "Rain" : p48 === "temp" ? "Air temperature" : "Wind speed"} (${units[p48]})`} />
      </section>
      <section className="neo overflow-auto p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Blend vs website (table)</p>
        <p className="text-[11px] text-neo-muted">{x?.compare?.note}</p>
        <table className="mt-2 w-full text-left text-[11px]">
          <thead className="text-neo-muted">
            <tr>
              <th className="py-1">Hour ahead</th>
              <th style={{ color: COL.blend }}>Blend rain (mm)</th>
              <th style={{ color: COL.om }}>Website rain (mm)</th>
              <th>Website temp (°C)</th>
              <th>Website wind (km/h)</th>
            </tr>
          </thead>
          <tbody>
            {cmp.map((r) => (
              <tr key={r.h} className="border-t border-neo-line">
                <td className="py-1 font-mono">{r.h}</td>
                <td className="font-mono">{round2(r.blend_mm)}</td>
                <td className="font-mono">{round2(r.website_mm)}</td>
                <td className="font-mono">{r.website_temp_c ?? "—"}</td>
                <td className="font-mono">{r.website_wind_kmh ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function CompareSec({ vera }: { vera: VeraPack }) {
  const hours = (vera.hourly || []).filter((r) => (r.lead_h ?? 0) < 24);
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
  return (
    <section className="neo p-4">
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
    </section>
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
  const chart = hours.map((h) => ({
    t: istClock(h.t),
    Blend: h.blend_mm,
    Website: h.website_mm ?? h.rain_mm,
    Ensemble: h.ensemble_mm,
    temp: h.temp_c,
    wind: h.wind_kmh,
    heat: h.wbgt_c,
  }));
  const mins = (di === 0 ? day?.minutes_today : day?.peak_minutes) || [];
  const mchart = mins.map((m) => ({
    t: istClock(m.t),
    Website: m.website_mm_h ?? m.rain_mm_h,
    Blend: m.blend_mm_h,
    Ensemble: m.ensemble_mm_h,
    temp: m.temp_c,
    wind: m.wind_kmh,
    heat: m.wbgt_c,
  }));
  const web = mchart.map((m) => Number(m.Website || 0));
  const bl = mchart.map((m) => Number(m.Blend || 0));
  const n = Math.min(web.length, bl.length) || 1;
  const mae = bl.length ? bl.reduce((s, v, i) => s + Math.abs(v - (web[i] || 0)), 0) / n : null;
  const peak = mchart.reduce((p, m) => Math.max(p, Number(m.Website || 0), Number(m.Blend || 0)), 0);
  const total = mins.reduce((s, m) => s + Number(m.rain_mm || 0), 0);
  const yHour = varK === "rain" ? "Rain (mm in the hour)" : varK === "temp" ? "Temperature (°C)" : varK === "wind" ? "Wind (km/h)" : "WBGT heat (°C)";
  const yMin = varK === "rain" ? "Rain rate (mm/h)" : yHour;
  return (
    <div className="space-y-3">
      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">Inside each hour · next week</p>
        <p className="text-[11px] text-neo-muted">{vera.intra_hour?.note} Times are IST. Ensemble is satellite-shaped rain; Blend is gated members; Website is Open-Meteo.</p>
        <div className="mt-2 flex flex-wrap gap-1">
          {days.map((d, i) => (
            <button key={d.date} type="button" className={`neo-btn text-[11px] ${di === i ? "neo-btn-on" : ""}`} onClick={() => setDi(i)}>
              {d.label || `Day ${i + 1}`} · {d.date}
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
              <Tooltip />
              <Legend />
              {varK === "rain" ? <Line dataKey="Blend" stroke={COL.blend} dot={false} /> : null}
              {varK === "rain" && vsWeb ? <Line dataKey="Website" stroke={COL.om} strokeDasharray="4 3" dot={false} /> : null}
              {varK === "temp" ? <Line dataKey="temp" name="Temperature °C" stroke={COL.nwp} dot={false} /> : null}
              {varK === "wind" ? <Line dataKey="wind" name="Wind km/h" stroke={COL.ai} dot={false} /> : null}
              {varK === "heat" ? <Line dataKey="heat" name="WBGT °C" stroke="#c0392b" dot={false} /> : null}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <AxisHint x="Valid hour (IST)" y={yHour} />
      </section>
      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{di === 0 ? "15-minute shape (Day 1)" : "Peak-hour 5-minute shape"}</p>
        <div className="mt-2 grid gap-2 sm:grid-cols-3">
          <Kpi label="Peak rain rate" value={peak ? `${round2(peak)} mm/h` : "—"} />
          <Kpi label="Rain in this strip" value={`${round2(total)} mm`} sub="sums to the locked hour" />
          <Kpi label="Blend vs website MAE" value={mae != null ? `${round2(mae)} mm/h` : "Not available"} />
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          {(["rain", "temp", "wind", "heat"] as const).map((k) => (
            <button key={k} type="button" className={`neo-btn text-[11px] ${varK === k ? "neo-btn-on" : ""}`} onClick={() => setVarK(k)}>
              {k}
            </button>
          ))}
        </div>
        <div className="mt-2 h-44">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={mchart}>
              <CartesianGrid stroke="#cfe0dd" vertical={false} />
              <XAxis dataKey="t" fontSize={9} />
              <YAxis fontSize={10} width={36} />
              <Tooltip />
              <Legend />
              {varK === "rain" ? <Line dataKey="Blend" stroke={COL.blend} dot={false} /> : null}
              {varK === "rain" && vsWeb ? <Line dataKey="Website" stroke={COL.om} strokeDasharray="4 3" dot={false} /> : null}
              {varK === "temp" ? <Line dataKey="temp" name="Temperature °C" stroke={COL.nwp} dot={false} /> : null}
              {varK === "wind" ? <Line dataKey="wind" name="Wind km/h" stroke={COL.ai} dot={false} /> : null}
              {varK === "heat" ? <Line dataKey="heat" name="WBGT °C" stroke="#c0392b" dot={false} /> : null}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <AxisHint x="Clock time (IST)" y={yMin} />
      </section>
    </div>
  );
}
