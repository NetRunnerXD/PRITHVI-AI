"use client";

import type { ComponentType } from "react";
import { COPY, type Locale } from "@/i18n/copy";
import { useApp } from "@/lib/store";
import type { TabId } from "@/types/dashboard";
import {
  IconAdvisor,
  IconNowcast,
  IconForecast,
  IconLanguages,
  IconMap,
  IconOverview,
  IconPanelClose,
  IconPanelOpen,
  IconPin,
  IconPredicted,
  IconRefresh,
  IconSettings,
  IconUser,
} from "./Icons";

const TABS: { id: TabId; Icon: ComponentType<{ className?: string }> }[] = [
  { id: "home", Icon: IconOverview },
  { id: "analytics", Icon: IconForecast },
  { id: "data", Icon: IconNowcast },
  { id: "map", Icon: IconMap },
  { id: "model", Icon: IconPredicted },
  { id: "chat", Icon: IconAdvisor },
  { id: "settings", Icon: IconSettings },
];

export function Sidebar() {
  const {
    locale,
    setLocale,
    tab,
    setTab,
    dashboard,
    refresh,
    sidebarOpen,
    setSidebarOpen,
    favorites,
    recent,
    setLocation,
    account,
    setAuthModal,
    signOut,
  } = useApp();
  const t = COPY[locale];
  const tabLabel: Record<TabId, string> = {
    home: t.tabHome,
    analytics: t.tabAnalytics,
    data: t.tabData,
    map: t.tabMap,
    model: t.tabModel,
    chat: t.tabChat,
    settings: t.tabSettings,
  };

  return (
    <>
      {/* ── Mobile bottom tab bar (< lg) ── */}
      <nav
        className="mobile-bottom-bar fixed bottom-0 left-0 right-0 z-[1100] flex items-center justify-around border-t border-neo-line bg-neo-card/90 backdrop-blur-2xl px-1.5 py-1 lg:hidden shadow-lg select-none"
        style={{ paddingBottom: "max(env(safe-area-inset-bottom, 0px), 8px)" }}
      >
        {TABS.map(({ id, Icon }) => {
          const active = tab === id;
          return (
            <button
              key={id}
              onClick={() => setTab(id)}
              title={tabLabel[id]}
              data-testid={`tab-mobile-${id}`}
              className={`relative flex flex-col items-center gap-0.5 rounded-xl px-2 py-1 text-[10px] transition-all duration-200 active:scale-90 ${
                active
                  ? "text-neo-accent font-bold bg-[color-mix(in_srgb,var(--accent)_12%,transparent)]"
                  : "text-neo-muted font-medium hover:text-neo-text"
              }`}
            >
              <Icon className={`h-5 w-5 shrink-0 transition-transform duration-200 ${active ? "scale-110 text-neo-accent" : ""}`} />
              <span className="truncate max-w-[3.5rem] tracking-tight">{tabLabel[id]}</span>
              {active && (
                <span className="absolute -top-1 left-1/2 -translate-x-1/2 h-0.5 w-4 rounded-full bg-neo-accent shadow-sm" />
              )}
            </button>
          );
        })}
      </nav>

      {/* ── Desktop sidebar (lg+) ── */}
      <aside
        className={`neo hidden lg:flex shrink-0 flex-col gap-3 p-3 transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] lg:sticky lg:top-4 lg:h-[calc(100vh-2rem)] lg:overflow-y-auto select-none ${
          sidebarOpen ? "lg:w-56" : "lg:w-[4.5rem]"
        }`}
      >
        {/* Header / Brand */}
        <div className={`flex items-center transition-all duration-300 ${sidebarOpen ? "justify-between" : "flex-col gap-2"}`}>
          {sidebarOpen ? (
            <div className="min-w-0 transition-all duration-300">
              <p className="text-base font-black tracking-tight text-neo-accent">{t.brand}</p>
              <p className="mt-0.5 text-[10px] leading-snug text-neo-muted truncate">{t.tag}</p>
            </div>
          ) : (
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[color-mix(in_srgb,var(--accent)_15%,transparent)] border border-[color-mix(in_srgb,var(--accent)_30%,transparent)] text-neo-accent font-black text-sm shadow-sm transition-transform duration-200 hover:scale-105">
              P
            </div>
          )}
          <button
            type="button"
            className="neo-btn flex h-8 w-8 shrink-0 items-center justify-center p-0 rounded-xl transition-all duration-200 hover:scale-105 active:scale-95 hover:border-neo-accent"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-expanded={sidebarOpen}
            title={sidebarOpen ? t.collapse : t.expand}
          >
            <span className="transition-transform duration-300">
              {sidebarOpen ? <IconPanelClose /> : <IconPanelOpen />}
            </span>
          </button>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex flex-col gap-1">
          {TABS.map(({ id, Icon }) => {
            const active = tab === id;
            return (
              <button
                key={id}
                onClick={() => setTab(id)}
                title={!sidebarOpen ? tabLabel[id] : undefined}
                data-testid={`tab-${id}`}
                className={`group relative flex items-center rounded-2xl py-2 text-sm font-semibold transition-all duration-200 ${
                  sidebarOpen ? "px-3 w-full text-left" : "justify-center w-full px-0"
                } ${
                  active
                    ? "bg-neo-accent text-white shadow-neo-sm scale-[1.01]"
                    : "text-neo-text hover:text-neo-accent hover:bg-[color-mix(in_srgb,var(--accent)_8%,transparent)] hover:translate-x-0.5"
                }`}
              >
                <Icon
                  className={`h-[18px] w-[18px] shrink-0 transition-transform duration-200 ${
                    active ? "scale-105 text-white" : "group-hover:scale-110"
                  }`}
                />
                <span
                  className={`overflow-hidden whitespace-nowrap transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] ${
                    sidebarOpen ? "max-w-[130px] opacity-100 ml-2.5" : "max-w-0 opacity-0 ml-0 pointer-events-none"
                  }`}
                >
                  {tabLabel[id]}
                </span>
                {active && !sidebarOpen && (
                  <span className="absolute right-1.5 top-1/2 -translate-y-1/2 h-1.5 w-1.5 rounded-full bg-white shadow-sm" />
                )}
              </button>
            );
          })}
        </nav>

        {/* Focused Location */}
        {dashboard ? (
          <div
            className={`neo-in rounded-2xl transition-all duration-300 overflow-hidden ${
              sidebarOpen ? "px-3 py-2" : "py-2 px-0"
            }`}
          >
            {sidebarOpen ? (
              <div className="fade-in-scale">
                <p className="flex items-center gap-1.5 text-[9px] uppercase tracking-widest text-neo-muted font-bold">
                  <span className="live-dot h-1.5 w-1.5" />
                  <span>{t.focus}</span>
                </p>
                <p className="mt-0.5 truncate text-xs font-bold text-neo-text" title={dashboard.location.label}>
                  {dashboard.location.label}
                </p>
              </div>
            ) : (
              <div className="flex justify-center text-neo-accent" title={dashboard.location.label}>
                <IconPin className="h-4 w-4 transition-transform duration-200 hover:scale-125" />
              </div>
            )}
          </div>
        ) : null}

        {/* Favorites & Recent */}
        {sidebarOpen && (favorites.length > 0 || recent.length > 0) ? (
          <div className="fade-in-scale space-y-1.5">
            {favorites.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {favorites.map((f) => (
                  <button
                    key={f.id}
                    className="chip hover:scale-105 hover:bg-neo-accent hover:text-white transition-all text-[9px] font-semibold flex items-center gap-1"
                    onClick={() => setLocation(f)}
                    title={f.label}
                  >
                    <span className="text-amber-400 font-bold">★</span>
                    <span className="truncate max-w-[80px]">{f.district}</span>
                  </button>
                ))}
              </div>
            ) : null}
            {recent.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {recent.slice(0, 3).map((f) => (
                  <button
                    key={f.id}
                    className="chip hover:scale-105 hover:bg-[color-mix(in_srgb,var(--accent)_15%,transparent)] hover:text-neo-accent transition-all text-[9px]"
                    onClick={() => setLocation(f)}
                    title={f.label}
                  >
                    <span className="truncate max-w-[80px]">{f.district}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {/* Language Switcher & Refresh */}
        <div className="mt-auto flex flex-col gap-2 pt-2 border-t border-[color-mix(in_srgb,var(--line)_60%,transparent)]">
          <div className={`flex items-center gap-1 ${sidebarOpen ? "justify-between" : "flex-col"}`}>
            {sidebarOpen ? (
              <div className="flex items-center gap-1 text-neo-muted">
                <IconLanguages className="h-3.5 w-3.5" />
                <span className="text-[10px] font-bold uppercase tracking-wider">Lang</span>
              </div>
            ) : null}
            <div
              className={`inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] ${
                sidebarOpen ? "gap-0.5" : "flex-col gap-0.5 w-full"
              }`}
            >
              {(["en", "hi", "bn"] as Locale[]).map((l) => (
                <button
                  key={l}
                  onClick={() => setLocale(l)}
                  className={`rounded-lg py-1 text-[10px] font-bold transition-all ${
                    sidebarOpen ? "px-2" : "w-full"
                  } ${
                    locale === l
                      ? "bg-neo-accent2 text-white shadow-sm"
                      : "text-neo-muted hover:text-neo-text hover:bg-[color-mix(in_srgb,var(--card)_60%,transparent)]"
                  }`}
                >
                  {l.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {account ? (
            <button
              className={`neo-btn flex items-center justify-center gap-2 py-2 text-xs ${sidebarOpen ? "w-full" : "w-full px-0"}`}
              onClick={() => signOut()}
              title={account.display_name}
            >
              <IconUser className="h-4 w-4 shrink-0 text-neo-accent" />
              {sidebarOpen ? <span className="truncate">{t.authSignOut}</span> : null}
            </button>
          ) : (
            <button
              className={`neo-btn flex items-center justify-center gap-2 py-2 text-xs ${sidebarOpen ? "w-full" : "w-full px-0"}`}
              onClick={() => setAuthModal(true)}
              title={t.authSignIn}
            >
              <IconUser className="h-4 w-4 shrink-0 text-neo-accent" />
              {sidebarOpen ? <span className="truncate">{t.authSignIn}</span> : null}
            </button>
          )}

          <button
            className={`neo-btn group flex items-center justify-center gap-2 py-2 text-xs font-bold transition-all hover:border-[var(--accent)] ${
              sidebarOpen ? "w-full" : "w-full px-0"
            }`}
            onClick={() => refresh()}
            title={t.refresh}
          >
            <IconRefresh className="h-4 w-4 transition-transform duration-500 group-hover:rotate-180 text-neo-accent shrink-0" />
            {sidebarOpen ? <span className="truncate">{t.refresh}</span> : null}
          </button>
        </div>
      </aside>
    </>
  );
}
