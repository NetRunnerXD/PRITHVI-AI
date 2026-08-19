"use client";

import { COPY, type Locale } from "@/i18n/copy";
import type { DashboardSnapshot } from "@/types/dashboard";

export function SciencePanel({ dash, locale }: { dash: DashboardSnapshot; locale: Locale }) {
  const t = COPY[locale];
  const s = dash.science;
  if (!s?.hysteresis && !s?.regret) return null;
  const hy = s.hysteresis;
  const rg = s.regret;
  const live = s.livelihood;
  const atlas = s.residual;
  const trust = s.bandit;
  const ph = s.phenology;
  const named = s.vernacular?.named;
  const blind = s.blindspot;
  const wb = s.water_balance;
  const speech = named ? named[locale] || named.en : "";
  const nc = s.nowcast;

  return (
    <section className="neo space-y-3 p-4">
      <h3 className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.science}</h3>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        <Tile
          k={t.hysteresis}
          v={`${hy?.limb === "wetting" ? t.wetting : t.drying} · ${hy?.flip || "—"}`}
          sub={`${t.runoff} 3d ${hy?.runoff_3d_mm ?? "—"} mm · mem ${hy?.memory ?? "—"}`}
        />
        <Tile
          k={t.regret}
          v={(rg?.action || "—").toUpperCase()}
          sub={`hold ${rg?.regret_hold_mm ?? "—"} mm · apply ${rg?.regret_apply_mm ?? "—"} mm`}
        />
        <Tile
          k={t.livelihood}
          v={`${live?.score_pct ?? "—"}% ${live?.level || ""}`}
          sub={`${t.closedDays}: ${(live?.closed_days || []).slice(0, 3).join(", ") || "—"}`}
        />
        <Tile
          k={t.trustSource}
          v={(trust?.source || "—").replace("_", " ")}
          sub={`${t.ours} ${trust?.trust_ours_pct ?? "—"}% · ${atlas?.id || ""} ${atlas?.regime || ""}`}
        />
        <Tile
          k={t.phenology}
          v={ph?.stage || "—"}
          sub={`${ph?.family || ""} · score ${ph?.stage_score ?? "—"}`}
        />
        <Tile
          k={t.blindspot}
          v={(blind?.level || "—").toUpperCase()}
          sub={blind?.drivers?.[0] || ""}
        />
      </div>
      {speech ? (
        <p className="text-sm">
          <span className="text-[11px] uppercase tracking-wide text-neo-muted">{t.speechName}: </span>
          {speech}
        </p>
      ) : null}
      {wb?.parts ? (
        <p className="font-mono text-[11px] text-neo-muted">
          {t.waterBudget}: P {wb.parts.precip_mm} − ET₀ {wb.parts.et0_mm} − Q {wb.parts.runoff_mm} − ΔS{" "}
          {wb.parts.delta_soil_mm} − U {wb.parts.deep_plus_unobserved_mm} ≈ {wb.checksum_mm}
        </p>
      ) : null}
      {trust?.reason ? <p className="text-xs text-neo-muted">{trust.reason}</p> : null}
      {nc ? (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          <Tile
            k={t.nowcast}
            v={nc.regime?.name?.toLowerCase() === "squall" ? "STORM" : (nc.regime?.name || "—").toUpperCase()}
            sub={`${t.onset} ${nc.clock?.t_start ? nc.clock.t_start.slice(11, 16) : "—"} · ${t.cessation} ${
              nc.clock?.t_stop ? nc.clock.t_stop.slice(11, 16) : "—"
            }`}
          />
          <Tile
            k={t.pumpSet}
            v={(nc.pump?.action || "—").toUpperCase()}
            sub={`${t.pInterrupt} ${nc.pump?.p_interrupt_90m ?? "—"} · ${t.litresAtRisk} ${nc.pump?.liters_at_risk ?? "—"}`}
          />
          <Tile
            k={t.fieldAccess}
            v={nc.access?.enterable ? t.enterable : t.closedField}
            sub={`${nc.access?.reasons?.[0] || ""} · ${t.ponding} ${nc.ponding?.mm_60 ?? "—"} mm`}
          />
          <Tile
            k={t.kalWatch}
            v={(nc.kal?.level || "—").toUpperCase()}
            sub={nc.tide?.drain_blocked ? t.drainBlocked : t.air6h + " " + (nc.air?.peak_us_aqi ?? "—")}
          />
        </div>
      ) : null}
    </section>
  );
}

function Tile({ k, v, sub }: { k: string; v: string; sub: string }) {
  return (
    <div className="neo-in rounded-2xl px-3 py-2">
      <p className="text-[10px] uppercase tracking-widest text-neo-muted">{k}</p>
      <p className="mt-1 text-sm font-bold">{v}</p>
      <p className="mt-0.5 text-[11px] text-neo-muted">{sub}</p>
    </div>
  );
}
