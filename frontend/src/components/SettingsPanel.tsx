"use client";

import { COPY, type Locale } from "@/i18n/copy";
import { API_BASE } from "@/lib/config";
import { DEFAULT_SETTINGS, useApp } from "@/lib/store";
import type { Density, TabId, ThemeId, UnitSys } from "@/types/dashboard";

const THEMES: ThemeId[] = ["sand", "monsoon", "midnight", "ocean", "contrast"];
const TABS: TabId[] = ["overview", "alerts", "map", "forecast", "predicted", "risks", "market", "advisor"];

export function SettingsPanel() {
  const { locale, setLocale, outputLocale, setOutputLocale, settings, setSettings, resetSettings } = useApp();
  const t = COPY[locale];
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <section className="neo space-y-3 p-4">
        <h3 className="text-sm font-bold">{t.theme}</h3>
        <div className="flex flex-wrap gap-2">
          {THEMES.map((id) => (
            <button key={id} className={`neo-btn capitalize ${settings.theme === id ? "neo-btn-on" : ""}`} onClick={() => setSettings({ theme: id })}>
              {t[`theme_${id}`] || id}
            </button>
          ))}
        </div>
        <label className="block text-sm">
          {t.density}
          <select
            className="neo-in mt-1 w-full px-3 py-2"
            value={settings.density}
            onChange={(e) => setSettings({ density: e.target.value as Density })}
          >
            <option value="comfortable">{t.comfortable}</option>
            <option value="compact">{t.compact}</option>
          </select>
        </label>
        <label className="block text-sm">
          {t.fontScale} ({settings.fontScale}%)
          <input
            type="range"
            min={90}
            max={120}
            value={settings.fontScale}
            className="mt-1 w-full"
            onChange={(e) => setSettings({ fontScale: Number(e.target.value) })}
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={settings.reduceMotion} onChange={(e) => setSettings({ reduceMotion: e.target.checked })} />
          {t.reduceMotion}
        </label>
      </section>

      <section className="neo space-y-3 p-4">
        <h3 className="text-sm font-bold">{t.language}</h3>
        <div className="flex gap-2">
          {(["en", "hi", "bn"] as Locale[]).map((l) => (
            <button key={l} className={`neo-btn flex-1 ${locale === l ? "neo-btn-on" : ""}`} onClick={() => setLocale(l)}>
              {l.toUpperCase()}
            </button>
          ))}
        </div>
        <p className="text-xs text-neo-muted">{t.replyIn}</p>
        <div className="flex gap-2">
          {(["en", "hi", "bn"] as Locale[]).map((l) => (
            <button key={l} className={`neo-btn flex-1 ${outputLocale === l ? "neo-btn-on" : ""}`} onClick={() => setOutputLocale(l)}>
              {l.toUpperCase()}
            </button>
          ))}
        </div>
        <label className="block text-sm">
          {t.units}
          <select className="neo-in mt-1 w-full px-3 py-2" value={settings.units} onChange={(e) => setSettings({ units: e.target.value as UnitSys })}>
            <option value="metric">{t.metric}</option>
            <option value="imperial">{t.imperial}</option>
          </select>
        </label>
      </section>

      <section className="neo space-y-3 p-4">
        <h3 className="text-sm font-bold">{t.refresh}</h3>
        <label className="block text-sm">
          {t.refreshSec}
          <select
            className="neo-in mt-1 w-full px-3 py-2"
            value={settings.refreshSec}
            onChange={(e) => setSettings({ refreshSec: Number(e.target.value) })}
          >
            {[30, 60, 120, 300].map((s) => (
              <option key={s} value={s}>
                {s}s
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          {t.defaultTab}
          <select
            className="neo-in mt-1 w-full px-3 py-2"
            value={settings.defaultTab}
            onChange={(e) => setSettings({ defaultTab: e.target.value as TabId })}
          >
            {TABS.map((id) => (
              <option key={id} value={id}>
                {tabLabel(t, id)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={settings.showHints} onChange={(e) => setSettings({ showHints: e.target.checked })} />
          {t.showHints}
        </label>
      </section>

      <section className="neo space-y-3 p-4">
        <h3 className="text-sm font-bold">{t.resetSettings}</h3>
        <p className="text-sm text-neo-muted">{t.resetHint}</p>
        <button className="neo-btn" onClick={() => resetSettings()}>
          {t.resetSettings}
        </button>
        <p className="font-mono text-[11px] text-neo-muted">
          {DEFAULT_SETTINGS.theme} · {DEFAULT_SETTINGS.units} · {DEFAULT_SETTINGS.refreshSec}s
        </p>
        <p className="text-xs text-neo-muted">{t.apiEndpoint}</p>
        <p className="break-all font-mono text-[11px] text-neo-muted">{API_BASE || "(same origin /api)"}</p>
      </section>
    </div>
  );
}

function tabLabel(t: Record<string, string>, id: TabId) {
  const map: Record<string, string> = {
    overview: t.tabOverview,
    alerts: t.tabAlerts,
    map: t.tabMap,
    forecast: t.tabForecast,
    predicted: t.tabPredicted,
    risks: t.tabRisks,
    market: t.tabMarket,
    advisor: t.tabAdvisor,
    settings: t.tabSettings,
  };
  return map[id] || id;
}
