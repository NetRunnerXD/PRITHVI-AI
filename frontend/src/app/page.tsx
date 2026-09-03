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
import { AuthModal } from "@/components/AuthModal";
import { Sidebar } from "@/components/Sidebar";
import { SquareMap } from "@/components/SquareMap";
import { ThemeBoot } from "@/components/ThemeBoot";
import { Collapse, SourcesBox } from "@/components/ui";
import { COPY } from "@/i18n/copy";
import { fetchCompare, searchPlaces } from "@/lib/api";
import { rain } from "@/lib/units";
import { useApp } from "@/lib/store";
import { ChatFloat } from "@/components/ChatFloat";
import { QualityCatalog } from "@/components/QualityCatalog";
import type { TabId } from "@/types/dashboard";

const TAB_ORDER: TabId[] = ["home", "analytics", "data", "map", "model", "chat", "settings"];

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
    loadAccount,
    setLocation,
    favorites,
    toggleFavorite,
    settings,
    highlight,
    mapFocus,
    windowPack,
    viewMode,
    setViewMode,
  } = useApp();
  const t = COPY[locale];
  const [cmpQ, setCmpQ] = useState("Pune");
  const [cmp, setCmp] = useState<Record<string, unknown> | null>(null);
  const [cmpBusy, setCmpBusy] = useState(false);
  const units = settings.units;

  const [analyticsSubTab, setAnalyticsSubTab] = useState<"metrics" | "nowcast" | "forecast">("metrics");
  const [dataSubTab, setDataSubTab] = useState<"meteorology" | "environment" | "hydrology" | "seismology" | "agriculture" | "risks">("meteorology");

  useEffect(() => {
    refresh();
    void loadAccount();
  }, [refresh, loadAccount]);

  useEffect(() => {
    const id = window.setInterval(() => {
      void quietRefresh();
    }, Math.max(15, settings.refreshSec) * 1000);
    return () => window.clearInterval(id);
  }, [quietRefresh, settings.refreshSec]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "0") {
        setTab("settings");
        return;
      }
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



  return (
    <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col gap-3 p-2 pb-20 sm:p-3 sm:pb-20 lg:flex-row lg:p-4 lg:pb-4">
      <ThemeBoot />
      <Sidebar />
      <AuthModal />
      <div className="min-w-0 flex-1 space-y-3">
        <header className="neo relative z-50 flex flex-wrap items-center gap-2 px-3 py-2 sm:px-4">
          <div className="flex items-center gap-2 lg:hidden shrink-0">
            <img
              src="/logo.png"
              alt="PRITHVI-AI"
              width={28}
              height={28}
              className="h-7 w-7 rounded-lg object-cover shadow-sm border border-white/20"
            />
          </div>
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
              {settings.showHints ? (
                <span className="hidden text-[11px] text-neo-muted md:inline">{t.keyboardHint}</span>
              ) : null}
            </div>
          ) : null}

          {/* Compact View Mode toggle for Mobile screens (<lg) where Desktop Sidebar is hidden */}
          <div className="ml-auto flex items-center lg:hidden">
            <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
              <button
                type="button"
                onClick={() => setViewMode("detail")}
                title="Detailed Technical Data & Charts"
                className={`rounded-lg px-2 py-0.5 text-[10px] font-bold transition-all ${
                  viewMode === "detail"
                    ? "bg-neo-accent text-white shadow-sm"
                    : "text-neo-muted hover:text-neo-text"
                }`}
              >
                Detail
              </button>
              <button
                type="button"
                onClick={() => setViewMode("overview")}
                title="Layman Summaries & Overview"
                className={`rounded-lg px-2 py-0.5 text-[10px] font-bold transition-all ${
                  viewMode === "overview"
                    ? "bg-amber-500 text-white shadow-sm"
                    : "text-neo-muted hover:text-neo-text"
                }`}
              >
                Overview
              </button>
            </div>
          </div>
        </header>

        {status === "error" ? <p className="neo px-3 py-2 text-sm text-neo-danger">{error}</p> : null}
        {dashboard?.provider_status?.["open-meteo"] === "stale" || dashboard?.provider_status?.["open-meteo"] === "fallback" ? (
          <div className="flex items-center justify-between gap-2 rounded-xl bg-amber-500/10 border border-amber-500/25 px-3.5 py-2 text-xs text-amber-800 dark:text-amber-300 shadow-xs" role="status">
            <span className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-amber-500 shrink-0" />
              <span>Live forecast link busy. Displaying India Climatology &amp; Regional AI Synthesis.</span>
            </span>
          </div>
        ) : dashboard?.provider_status?.["open-meteo"] === "error" ? (
          <div className="flex items-center justify-between gap-2 rounded-xl bg-amber-500/10 border border-amber-500/25 px-3.5 py-2 text-xs text-amber-800 dark:text-amber-300 shadow-xs" role="status">
            <span className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-amber-500 shrink-0" />
              <span>Weather model link busy. Displaying synthesized regional meteorological telemetry.</span>
            </span>
          </div>
        ) : null}

        {!dashboard && tab !== "settings" ? (
          <p className="text-neo-muted">{status === "loading" ? t.loading : "…"}</p>
        ) : (
          <>
            {tab === "home" && dashboard ? (
              <div className="space-y-3">
                <OverviewLive 
                  dash={dashboard} 
                  locale={locale} 
                  onNavigateData={(sub) => {
                    setDataSubTab(sub as any);
                    setTab("data");
                  }} 
                />
                <SourcesBox tab="home" locale={locale} provenance={dashboard.science?.provenance} />
              </div>
            ) : null}

            {tab === "analytics" && dashboard ? (
              <div className="space-y-4">
                {/* Subtab Navigation Bar */}
                <div className="neo flex flex-wrap items-center gap-2 p-2 sm:p-2.5">
                  <button
                    type="button"
                    className={`neo-btn flex items-center gap-2 text-xs font-bold tracking-wide uppercase px-3.5 py-2 transition ${
                      analyticsSubTab === "metrics" ? "neo-btn-on shadow-sm" : "opacity-80 hover:opacity-100"
                    }`}
                    onClick={() => setAnalyticsSubTab("metrics")}
                  >
                    <span className="text-sm">📊</span>
                    <span className="hidden sm:inline">{locale === "hi" ? "लाइव मेट्रिक्स" : locale === "bn" ? "লাইভ মেট্রিক্স" : "Live Metrics"}</span>
                  </button>
                  <button
                    type="button"
                    className={`neo-btn flex items-center gap-2 text-xs font-bold tracking-wide uppercase px-3.5 py-2 transition ${
                      analyticsSubTab === "nowcast" ? "neo-btn-on shadow-sm" : "opacity-80 hover:opacity-100"
                    }`}
                    onClick={() => setAnalyticsSubTab("nowcast")}
                  >
                    <span className="text-sm">⚡</span>
                    <span className="hidden sm:inline">{locale === "hi" ? "नाउकास्टिंग (Kalman)" : locale === "bn" ? "নাওকাস্টিং (Kalman)" : "Nowcasting & Kalman"}</span>
                  </button>
                  <button
                    type="button"
                    className={`neo-btn flex items-center gap-2 text-xs font-bold tracking-wide uppercase px-3.5 py-2 transition ${
                      analyticsSubTab === "forecast" ? "neo-btn-on shadow-sm" : "opacity-80 hover:opacity-100"
                    }`}
                    onClick={() => setAnalyticsSubTab("forecast")}
                  >
                    <span className="text-sm">📈</span>
                    <span className="hidden sm:inline">{locale === "hi" ? "पूर्वानुमान एवं ग्राफ़" : locale === "bn" ? "পূর্বাভাস ও গ্রাফ" : "Forecast & Graphs"}</span>
                  </button>
                </div>

                {/* Subtab 1: Live Metrics */}
                {analyticsSubTab === "metrics" && (
                  <div className="space-y-4">
                    <OverviewPlots dash={dashboard} locale={locale} />
                    <Collapse title={t.compare} defaultOpen={false}>
                      <div className="flex flex-wrap gap-2">
                        <input value={cmpQ} onChange={(e) => setCmpQ(e.target.value)} className="neo-in px-3 py-2 text-sm" placeholder="Pune" />
                        <button className="neo-btn" disabled={cmpBusy} onClick={runCompare}>
                          {cmpBusy ? "…" : t.compare}
                        </button>
                      </div>
                      {cmp && "error" in cmp ? (
                        <p className="mt-2 text-sm text-neo-danger">{String((cmp as { error: string }).error)}</p>
                      ) : null}
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
                  </div>
                )}

                {/* Subtab 2: Nowcasting (including Between-Scene Kalman) */}
                {analyticsSubTab === "nowcast" && (
                  <div className="space-y-4">
                    <NowcastLive dash={dashboard} locale={locale} />
                  </div>
                )}

                {/* Subtab 3: Forecast & Graphs */}
                {analyticsSubTab === "forecast" && (
                  <div className="space-y-4">
                    {windowPack && Array.isArray((windowPack as { days?: unknown[] }).days) ? (
                      <section className="neo overflow-x-auto p-4">
                        <h3 className="text-sm font-bold">{t.predictive}</h3>
                        <table className="mt-2 w-full min-w-[20rem] text-left text-sm">
                          <thead>
                            <tr className="text-neo-muted">
                              <th className="py-1">{t.colDate}</th>
                              <th className="py-1">{t.colRain}</th>
                              <th className="py-1">{t.colProb}</th>
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
                  </div>
                )}

                <SourcesBox tab="analytics" locale={locale} provenance={dashboard.science?.provenance} />
              </div>
            ) : null}

            {tab === "data" && dashboard ? (
              <div className="space-y-4">
                {/* Data Subtabs */}
                <div className="flex gap-1.5 p-1.5 rounded-2xl bg-[var(--card)] border border-[var(--line)] shadow-sm overflow-x-auto sm:flex-wrap">
                  {[
                    { id: "meteorology", label: "Meteorology" },
                    { id: "environment", label: "Air" },
                    { id: "hydrology", label: "Hydrology" },
                    { id: "seismology", label: "Seismology" },
                    { id: "agriculture", label: "Agriculture" },
                    { id: "risks", label: "Risk" },
                  ].map((sub) => (
                    <button
                      key={sub.id}
                      onClick={() => setDataSubTab(sub.id as any)}
                      className={`flex-1 min-w-fit rounded-xl px-3 py-2.5 text-[11px] font-bold uppercase tracking-wider transition-all duration-200 ${
                        dataSubTab === sub.id
                          ? "bg-[var(--accent)] text-[var(--bg)] shadow-md transform scale-[1.02]"
                          : "text-neo-muted hover:text-[var(--text)] hover:bg-[color-mix(in_srgb,var(--accent)_10%,transparent)]"
                      }`}
                    >
                      {sub.label}
                    </button>
                  ))}
                </div>

                {dataSubTab !== "agriculture" && dataSubTab !== "risks" && (
                  <QualityCatalog dash={dashboard} group={dataSubTab} />
                )}

                {dataSubTab === "meteorology" && (
                  <Collapse title={t.science} defaultOpen={false}>
                    <SciencePanel dash={dashboard} locale={locale} />
                  </Collapse>
                )}

                {dataSubTab === "risks" && (
                  <div className="space-y-3">
                    <div className="grid gap-3 sm:grid-cols-2">
                      {[...(dashboard.risks || [])]
                        .sort((a, b) => (b.score_pct ?? 0) - (a.score_pct ?? 0))
                        .map((r) => (
                          <RiskCard
                            key={r.id}
                            risk={r}
                            locale={locale}
                            highlight={Boolean(highlight && (highlight === r.id || highlight.includes(r.id)))}
                          />
                        ))}
                    </div>
                  </div>
                )}

                {dataSubTab === "agriculture" && (
                  <MandiPanel dash={dashboard} locale={locale} />
                )}

                <SourcesBox tab="data" locale={locale} provenance={dashboard.science?.provenance} />
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

            {tab === "model" && dashboard ? (
              <div className="space-y-4">
                <PredictionsPanel dash={dashboard} locale={locale} />
                <SourcesBox tab="model" locale={locale} />
              </div>
            ) : null}

            {tab === "chat" ? (
              <div className="space-y-3">
                <ChatDock />
                <SourcesBox tab="chat" locale={locale} />
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
      {tab !== "chat" ? <ChatFloat /> : null}
    </div>
  );
}
