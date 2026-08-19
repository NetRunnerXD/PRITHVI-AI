"use client";

import type { ReactNode } from "react";
import type { DashboardSnapshot } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="neo flex min-h-[180px] flex-col p-4">
      <h3 className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{title}</h3>
      <div className="mt-3 flex-1 text-sm">{children}</div>
    </section>
  );
}

export function LensGrid({
  dash,
  locale,
  focus = "all",
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  focus?: "all" | "why-do";
}) {
  const t = COPY[locale];
  const cur = dash.descriptive.current;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {focus === "all" ? (
        <Card title={t.descriptive}>
          <div className="grid grid-cols-2 gap-3">
            <Stat k="Temp" v={cur.temp_c != null ? `${cur.temp_c.toFixed(1)}°C` : "—"} />
            <Stat k={t.soil} v={cur.soil_moisture_m3m3 != null ? cur.soil_moisture_m3m3.toFixed(3) : "—"} />
            <Stat k={t.et0} v={cur.et0_mm != null ? `${cur.et0_mm.toFixed(2)} mm` : "—"} />
            <Stat k={t.aqi} v={cur.aqi != null ? `${cur.aqi} ${cur.aqi_category || ""}`.trim() : "—"} />
          </div>
        </Card>
      ) : null}
      <Card title={t.diagnostic}>
        <ul className="space-y-3">
          {(dash.diagnostic.stories || []).slice(0, 3).map((s) => (
            <li key={s.id}>
              <p className="font-semibold">{s.title}</p>
              <p className="mt-0.5 text-neo-muted">{s.why}</p>
              <p className="mt-0.5 font-mono text-[11px] text-neo-accent">{s.evidence}</p>
              {s.implication ? <p className="mt-0.5 text-xs">{s.implication}</p> : null}
            </li>
          ))}
          {(dash.diagnostic.stories || []).length === 0
            ? dash.diagnostic.drivers.map((d) => (
                <li key={d}>▸ {d}</li>
              ))
            : null}
        </ul>
      </Card>
      {focus === "all" ? (
        <Card title={t.predictive}>
          <p className="text-3xl font-extrabold">
            {dash.predictive.precip_next_3d_mm}
            <span className="ml-1 text-sm font-medium text-neo-muted">mm / 3d</span>
          </p>
          <p className="mt-1 text-sm text-neo-muted">
            7d {dash.predictive.precip_7d_mm ?? "—"} mm · {t.balance} {dash.predictive.water_balance_7d_mm ?? "—"} mm
          </p>
          <p className="mt-1 text-xs text-neo-muted">
            P(rain): {(dash.predictive.precip_probability_pct || []).slice(0, 3).map((p) => `${p}%`).join(" · ") || "—"}
          </p>
        </Card>
      ) : null}
      <Card title={t.prescriptive}>
        <ul className="space-y-3">
          {dash.prescriptive.actions.slice(0, 3).map((a) => (
            <li key={a.id}>
              <p className="font-semibold">{a.action}</p>
              {a.why ? <p className="mt-0.5 text-xs text-neo-muted">{a.why}</p> : null}
              {a.when ? (
                <p className="mt-0.5 text-[11px] text-neo-accent">
                  {t.when}: {a.when}
                  {a.who ? ` · ${a.who}` : ""}
                </p>
              ) : null}
              {a.quant.water_saved_liters_min != null ? (
                <p className="font-mono text-xs text-neo-accent">
                  {a.quant.water_saved_liters_min}–{a.quant.water_saved_liters_max} L
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      </Card>
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
