"use client";

import type { ComponentType } from "react";
import { COPY, type Locale } from "@/i18n/copy";
import { askChips } from "@/i18n/presets";
import { useApp } from "@/lib/store";
import type { TabId } from "@/types/dashboard";
import {
  IconAdvisor,
  IconAlerts,
  IconNowcast,
  IconForecast,
  IconLanguages,
  IconMap,
  IconMarket,
  IconOverview,
  IconPanelClose,
  IconPanelOpen,
  IconPin,
  IconPredicted,
  IconRefresh,
  IconRisks,
  IconSettings,
} from "./Icons";

const TABS: { id: TabId; Icon: ComponentType<{ className?: string }> }[] = [
  { id: "overview", Icon: IconOverview },
  { id: "nowcast", Icon: IconNowcast },
  { id: "alerts", Icon: IconAlerts },
  { id: "map", Icon: IconMap },
  { id: "forecast", Icon: IconForecast },
  { id: "predicted", Icon: IconPredicted },
  { id: "risks", Icon: IconRisks },
  { id: "market", Icon: IconMarket },
  { id: "advisor", Icon: IconAdvisor },
  { id: "settings", Icon: IconSettings },
];

export function Sidebar() {
  const { locale, setLocale, tab, setTab, dashboard, refresh, sidebarOpen, setSidebarOpen, setPendingAsk, favorites, recent, setLocation } =
    useApp();
  const t = COPY[locale];
  const tabLabel: Record<TabId, string> = {
    overview: t.tabOverview,
    nowcast: t.tabNowcast,
    alerts: t.tabAlerts,
    map: t.tabMap,
    forecast: t.tabForecast,
    predicted: t.tabPredicted,
    risks: t.tabRisks,
    market: t.tabMarket,
    advisor: t.tabAdvisor,
    settings: t.tabSettings,
  };

  return (
    <aside
      className={`neo flex w-full shrink-0 flex-col gap-3 p-3 transition-[width] duration-200 lg:sticky lg:top-4 lg:h-[calc(100vh-2rem)] lg:overflow-y-auto ${
        sidebarOpen ? "lg:w-56" : "lg:w-[4.25rem]"
      }`}
    >
      <div className={`flex items-center ${sidebarOpen ? "justify-between" : "flex-col gap-2"}`}>
        <div className={sidebarOpen ? "min-w-0" : "text-center"}>
          <p className="text-lg font-extrabold tracking-tight text-neo-accent">{sidebarOpen ? t.brand : "R"}</p>
          {sidebarOpen ? <p className="mt-0.5 text-[11px] leading-snug text-neo-muted">{t.tag}</p> : null}
        </div>
        <button
          type="button"
          className="neo-btn flex h-8 w-8 shrink-0 items-center justify-center px-0"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          aria-expanded={sidebarOpen}
          title={sidebarOpen ? t.collapse : t.expand}
        >
          {sidebarOpen ? <IconPanelClose /> : <IconPanelOpen />}
        </button>
      </div>

      <nav className="flex flex-wrap gap-1 lg:flex-col">
        {TABS.map(({ id, Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            title={tabLabel[id]}
            className={`flex items-center gap-2.5 rounded-2xl px-2.5 py-2 text-sm font-semibold transition ${
              sidebarOpen ? "w-full text-left" : "justify-center lg:w-full"
            } ${tab === id ? "bg-neo-accent text-white shadow-neo-sm" : "text-neo-text hover:text-neo-accent"}`}
          >
            <Icon className="h-[18px] w-[18px] shrink-0" />
            {sidebarOpen ? <span className="truncate">{tabLabel[id]}</span> : null}
          </button>
        ))}
      </nav>

      {dashboard ? (
        <div className={`neo-in px-2.5 py-2 ${sidebarOpen ? "" : "hidden lg:block"}`}>
          {sidebarOpen ? (
            <>
              <p className="flex items-center gap-1 text-[10px] uppercase tracking-widest text-neo-muted">
                <IconPin className="h-3 w-3" /> {t.focus}
              </p>
              <p className="mt-1 truncate text-sm font-semibold">{dashboard.location.label}</p>
            </>
          ) : (
            <div className="flex justify-center text-neo-accent" title={dashboard.location.label}>
              <IconPin className="h-4 w-4" />
            </div>
          )}
        </div>
      ) : null}

      {sidebarOpen && (favorites.length || recent.length) ? (
        <div>
          {favorites.length ? (
            <div className="mb-2 flex flex-wrap gap-1.5">
              {favorites.map((f) => (
                <button key={f.id} className="chip" onClick={() => setLocation(f)}>
                  ★ {f.district}
                </button>
              ))}
            </div>
          ) : null}
          {recent.length ? (
            <div className="flex flex-wrap gap-1.5">
              {recent.slice(0, 3).map((f) => (
                <button key={f.id} className="chip" onClick={() => setLocation(f)}>
                  {f.district}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className={`mt-auto flex gap-1 ${sidebarOpen ? "flex-col" : "flex-row lg:flex-col"}`}>
        <div className={`flex items-center gap-1 ${sidebarOpen ? "" : "hidden lg:flex lg:flex-col"}`}>
          {sidebarOpen ? <IconLanguages className="h-3.5 w-3.5 text-neo-muted" /> : null}
          {(["en", "hi", "bn"] as Locale[]).map((l) => (
            <button
              key={l}
              onClick={() => setLocale(l)}
              className={`rounded-xl py-1 text-[10px] font-bold ${sidebarOpen ? "flex-1" : "w-full"} ${
                locale === l ? "bg-neo-accent2 text-white" : "neo-btn"
              }`}
            >
              {l.toUpperCase()}
            </button>
          ))}
        </div>
        <button className="neo-btn flex items-center justify-center gap-2" onClick={() => refresh()} title={t.refresh}>
          <IconRefresh className="h-4 w-4" />
          {sidebarOpen ? t.refresh : null}
        </button>
      </div>

      {sidebarOpen ? (
        <div>
          <p className="mb-1.5 text-[10px] uppercase tracking-widest text-neo-muted">{t.askAgent}</p>
          <div className="flex flex-wrap gap-1.5">
            {askChips(locale).map((item) => (
              <button
                key={item.short}
                className="chip hover:text-neo-accent2"
                onClick={() => {
                  setPendingAsk(item.q);
                  setTab("advisor");
                }}
              >
                {item.short}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </aside>
  );
}
