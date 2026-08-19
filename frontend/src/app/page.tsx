"use client";

import { useEffect, useMemo, useState } from "react";
import { ChatDock } from "@/components/ChatDock";
import { DistrictSearch } from "@/components/DistrictSearch";
import { EarlyWarnings } from "@/components/EarlyWarnings";
import { ForecastCharts } from "@/components/ForecastCharts";
import { NowcastLive } from "@/components/NowcastLive";
import { OverviewLive, OverviewPlots } from "@/components/OverviewLive";
import { MandiPanel } from "@/components/MandiPanel";
import { OutlookTable } from "@/components/OutlookTable";
import { PredictionsPanel } from "@/components/PredictionsPanel";
import { RiskCard } from "@/components/RiskCard";
import { SciencePanel } from "@/components/SciencePanel";
import { SettingsPanel } from "@/components/SettingsPanel";
import { Sidebar } from "@/components/Sidebar";
import { SquareMap } from "@/components/SquareMap";
import { ThemeBoot } from "@/components/ThemeBoot";
import { Collapse, SourcesBox } from "@/components/ui";
import { COPY } from "@/i18n/copy";
import { fetchCompare, searchPlaces } from "@/lib/api";
import { rain } from "@/lib/units";
import { useApp } from "@/lib/store";
import type { TabId } from "@/types/dashboard";

const TAB_ORDER: TabId[] = [
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
];

export default function Page() {
  const {
    locale,
    tab,
    setTab,
    dashboard,
    status,
    error,
    refresh,
    quietRefresh,
    setLocation,
    favorites,
    toggleFavorite,
    settings,
    highlight,
    mapFocus,
    windowPack,
  } = useApp();
  const t = COPY[locale];
  const [cmpQ, setCmpQ] = useState("Pune");
  const [cmp, setCmp] = useState<Record<string, unknown> | null>(null);
  const [cmpBusy, setCmpBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const units = settings.units;

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const id = window.setInterval(() => {
      void quietRefresh();
    }, Math.max(15, settings.refreshSec) * 1000);
    return () => window.clearInterval(id);
  }, [quietRefresh, settings.refreshSec]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const n = Number(e.key);
      if (n >= 1 && n <= 9) setTab(TAB_ORDER[n - 1]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setTab]);

  async function runCompare() {
    if (!dashboard) return;
    setCmpBusy(true);
    try {
      const hits = await searchPlaces(cmpQ);
      const other = hits[0]?.district || cmpQ;
      const data = await fetchCompare(dashboard.location.district, other);
      setCmp(data);
    } catch (e) {
      setCmp({ error: String(e) });
    } finally {
      setCmpBusy(false);
    }
  }

  const liveAt = dashboard?.live?.generated_at || dashboard?.generated_at;
  const pinned = dashboard ? favorites.some((f) => f.id === dashboard.location.id) : false;

  const cmpRows = useMemo(() => {
    const d = (cmp && !("error" in cmp) ? (cmp as { delta_a_minus_b?: Record<string, number | null> }).delta_a_minus_b : null) || {};
    return [
      { k: `${t.rain3} (mm)`, v: d.rain_3d_mm },
      { k: `${t.balance} (mm)`, v: d.water_balance_7d_mm },
      { k: `${t.floodWatch} (%)`, v: d.flood_score },
      { k: t.aqi, v: d.aqi },
    ];
  }, [cmp, t]);

  function copyBrief() {
    if (!dashboard) return;
    const act = dashboard.prescriptive.actions[0];
    const lines = [
      `Rituchakra — ${dashboard.location.label}`,
      `${t.rain3}: ${rain(dashboard.predictive.precip_next_3d_mm, units)}`,
      act?.action || "",
    ].filter(Boolean);
    void navigator.clipboard.writeText(lines.join("\n"));
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col gap-3 p-2 sm:p-3 lg:flex-row lg:p-4">
      <ThemeBoot />
      <Sidebar />
      <div className="min-w-0 flex-1 space-y-3">
        <header className="neo flex flex-wrap items-center gap-2 px-3 py-2 sm:px-4">
          <DistrictSearch locale={locale} onPick={(l) => setLocation(l)} />
          {dashboard ? (
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <span className="live-dot" aria-hidden />
              <span className="truncate text-sm font-semibold">{dashboard.location.label}</span>
              {liveAt ? (
                <span className="text-[11px] text-neo-muted">
                  {new Date(liveAt).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit" })}
                </span>
              ) : null}
              <button className="neo-btn text-xs" onClick={() => toggleFavorite(dashboard.location)}>
                {pinned ? "★" : "☆"}
              </button>
              <button className="neo-btn text-xs" onClick={copyBrief}>
                {copied ? t.copied : t.copyBrief}
              </button>
            </div>
          ) : null}
        </header>

        {status === "error" ? <p className="neo px-3 py-2 text-sm text-neo-danger">{error}</p> : null}
        {dashboard?.provider_status?.["open-meteo"] === "stale" ? (
          <p className="neo px-3 py-2 text-sm text-neo-warn" role="status">
            Live forecast quota is used up. Showing the last saved Open-Meteo / archive scene until the daily limit resets.
          </p>
        ) : null}
        {dashboard?.provider_status?.["open-meteo"] === "error" ? (
          <p className="neo px-3 py-2 text-sm text-neo-danger" role="status">
            Weather model is unavailable (Open-Meteo). Other tabs that need temperature and rain will stay empty until it answers.
          </p>
        ) : null}

        {!dashboard && tab !== "settings" ? (
          <p className="text-neo-muted">{status === "loading" ? t.loading : "…"}</p>
        ) : (
          <>
            {tab === "overview" && dashboard ? (
              <div className="space-y-3">
                <OverviewLive dash={dashboard} locale={locale} />
                <Collapse title={t.science} defaultOpen={false}>
                  <SciencePanel dash={dashboard} locale={locale} />
                </Collapse>
                <Collapse title={t.plots} defaultOpen={false}>
                  <OverviewPlots dash={dashboard} locale={locale} />
                </Collapse>
                <SourcesBox tab="overview" locale={locale} provenance={dashboard.science?.provenance} />
              </div>
            ) : null}

            {tab === "nowcast" && dashboard ? (
              <div className="space-y-3">
                <NowcastLive dash={dashboard} locale={locale} />
                <SourcesBox tab="nowcast" locale={locale} provenance={dashboard.science?.provenance} />
              </div>
            ) : null}

            {tab === "alerts" && dashboard ? (
              <div className="space-y-3">
                <section className="neo p-4">
                  <h3 className="text-sm font-bold">{t.actions}</h3>
                  <ul className="mt-3 space-y-2 text-sm">
                    {dashboard.prescriptive.actions.slice(0, 6).map((a) => (
                      <li key={a.id} className="border-t border-neo-line pt-2">
                        <p className="font-semibold">{a.action}</p>
                        {a.when ? <p className="text-xs text-neo-muted">{a.when}</p> : null}
                      </li>
                    ))}
                    {!dashboard.prescriptive.actions.length ? <li className="text-neo-muted">{t.allClear}</li> : null}
                  </ul>
                </section>
                <EarlyWarnings
                  items={dashboard.prescriptive.warnings}
                  locale={locale}
                  live={dashboard.live}
                  status={dashboard.provider_status}
                />
                <SourcesBox tab="alerts" locale={locale} />
              </div>
            ) : null}

            {tab === "map" && dashboard ? (
              <div className="space-y-3">
                <SquareMap
                  dash={dashboard}
                  locale={locale}
                  onPick={(l) => setLocation(l)}
                  focus={mapFocus}
                />
                <SourcesBox tab="map" locale={locale} />
              </div>
            ) : null}

            {tab === "forecast" && dashboard ? (
              <div className="space-y-4">
                {windowPack && Array.isArray((windowPack as { days?: unknown[] }).days) ? (
                  <section className="neo p-4">
                    <h3 className="text-sm font-bold">{t.predictive}</h3>
                    <table className="mt-2 w-full text-left text-sm">
                      <thead>
                        <tr className="text-neo-muted">
                          <th className="py-1">date</th>
                          <th className="py-1">mm</th>
                          <th className="py-1">%</th>
                        </tr>
                      </thead>
                      <tbody>
                        {((windowPack as { days: { date?: string; precip_mm?: number; precip_prob_pct?: number }[] }).days).map((d) => (
                          <tr key={d.date} className="border-t border-neo-line">
                            <td className="py-1 font-mono">{d.date}</td>
                            <td className="py-1 font-mono">{d.precip_mm}</td>
                            <td className="py-1 font-mono">{d.precip_prob_pct ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </section>
                ) : null}
                <OutlookTable dash={dashboard} locale={locale} />
                <ForecastCharts dash={dashboard} locale={locale} />
                <Collapse title={t.compare} defaultOpen={false}>
                  <div className="flex flex-wrap gap-2">
                    <input value={cmpQ} onChange={(e) => setCmpQ(e.target.value)} className="neo-in px-3 py-2 text-sm" placeholder="Pune" />
                    <button className="neo-btn" disabled={cmpBusy} onClick={runCompare}>
                      {cmpBusy ? "…" : t.compare}
                    </button>
                  </div>
                  {cmp && !("error" in cmp) ? (
                    <table className="mt-3 w-full text-left text-sm">
                      <tbody>
                        {cmpRows.map((row) => (
                          <tr key={row.k} className="border-t border-neo-line">
                            <td className="py-2 text-neo-muted">{row.k}</td>
                            <td className="py-2 font-mono">{row.v == null ? "—" : `${row.v > 0 ? "+" : ""}${row.v}`}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : null}
                </Collapse>
                <SourcesBox tab="forecast" locale={locale} />
              </div>
            ) : null}

            {tab === "predicted" && dashboard ? (
              <div className="space-y-4">
                <PredictionsPanel dash={dashboard} locale={locale} />
                <SourcesBox tab="predicted" locale={locale} />
              </div>
            ) : null}

            {tab === "risks" && dashboard ? (
              <div className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  {dashboard.risks.map((r) => (
                    <RiskCard
                      key={r.id}
                      risk={r}
                      locale={locale}
                      highlight={Boolean(highlight && (highlight === r.id || highlight.includes(r.id)))}
                    />
                  ))}
                </div>
                <SquareMap
                  dash={dashboard}
                  locale={locale}
                  onPick={(l) => setLocation(l)}
                  focus={mapFocus}
                  compact
                />
                <SourcesBox tab="risks" locale={locale} />
              </div>
            ) : null}

            {tab === "market" && dashboard ? (
              <div className="space-y-3">
                <MandiPanel dash={dashboard} locale={locale} />
                <SourcesBox tab="market" locale={locale} />
              </div>
            ) : null}

            {tab === "advisor" ? (
              <div className="space-y-3">
                <ChatDock />
                <SourcesBox tab="advisor" locale={locale} />
              </div>
            ) : null}

            {tab === "settings" ? (
              <div className="space-y-3">
                <SettingsPanel />
                <SourcesBox tab="settings" locale={locale} />
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
