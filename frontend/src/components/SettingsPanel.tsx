"use client";

import { useEffect, useState } from "react";
import { COPY, type Locale } from "@/i18n/copy";
import { API_BASE, apiUrl } from "@/lib/config";
import { gpsFix, patchAlertLocation, patchProfile } from "@/lib/auth";
import { DEFAULT_SETTINGS, useApp } from "@/lib/store";
import { DistrictSearch } from "./DistrictSearch";
import type { Density, TabId, ThemeId, UnitSys } from "@/types/dashboard";

const THEMES: ThemeId[] = ["sand", "monsoon", "midnight", "ocean", "contrast"];
const TABS: TabId[] = ["home", "analytics", "data", "map", "model", "chat"];

type LlmRow = { id: string; model: string; ok?: boolean };

export function SettingsPanel() {
  const { locale, setLocale, outputLocale, setOutputLocale, settings, setSettings, resetSettings, account, setAccount, setAuthModal, setLocation } =
    useApp();
  const t = COPY[locale];
  const [llms, setLlms] = useState<LlmRow[]>([{ id: "ollama", model: "qwen2.5:3b" }]);
  useEffect(() => {
    let stop = false;
    fetch(apiUrl("/health"))
      .then((r) => r.json())
      .then((body) => {
        if (stop) return;
        const rows = (body?.llm?.available || []) as LlmRow[];
        if (rows.length) setLlms(rows);
      })
      .catch(() => undefined);
    return () => {
      stop = true;
    };
  }, []);
  const [name, setName] = useState(account?.display_name || "");
  const [sms, setSms] = useState(Boolean(account?.sms_opt_in));
  const [acctMsg, setAcctMsg] = useState("");
  useEffect(() => {
    setName(account?.display_name || "");
    setSms(Boolean(account?.sms_opt_in));
  }, [account]);

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <section className="neo space-y-3 p-4">
        <h3 className="text-sm font-bold">{t.authAccount}</h3>
        {account ? (
          <>
            <p className="text-xs text-neo-muted">{account.phone}</p>
            <label className="block text-sm">
              {t.authName}
              <input className="neo-in mt-1 w-full px-3 py-2" value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={sms} onChange={(e) => setSms(e.target.checked)} />
              {t.authSmsOptIn}
            </label>
            <button
              className="neo-btn text-sm"
              onClick={() => {
                void patchProfile({ display_name: name, sms_opt_in: sms })
                  .then((u) => {
                    setAccount(u);
                    setAcctMsg(t.authSaved);
                  })
                  .catch((e) => setAcctMsg(String(e)));
              }}
            >
              {t.authSaveProfile}
            </button>
            <p className="text-xs font-semibold">{t.authAlertLocation}</p>
            {account.location ? (
              <p className="font-mono text-[11px] text-neo-muted">
                {account.location.place || account.location.district} · {account.location.lat?.toFixed(4)}, {account.location.lon?.toFixed(4)}
              </p>
            ) : null}
            <DistrictSearch
              locale={locale}
              onPick={(l) => {
                void patchAlertLocation({ lat: l.lat, lon: l.lon, place: l.place_name || l.district, source: "manual" }).then((u) => {
                  setAccount(u);
                  setAcctMsg(t.authSaved);
                });
              }}
            />
            <button
              className="neo-btn text-sm"
              onClick={() => {
                void gpsFix().then((fix) => {
                  if (!fix) {
                    setAcctMsg(t.authGpsFail);
                    return;
                  }
                  void patchAlertLocation({ ...fix, source: "gps" }).then((u) => {
                    setAccount(u);
                    setAcctMsg(t.authSaved);
                  });
                });
              }}
            >
              {t.authUseGps}
            </button>
            {account.location ? (
              <button
                className="neo-btn text-sm"
                onClick={() => {
                  const loc = account.location;
                  if (!loc) return;
                  void setLocation({
                    id: `alert:${loc.lat},${loc.lon}`,
                    label: loc.place || loc.district || "Alert location",
                    country: "IN",
                    state: loc.state || "",
                    district: loc.district || loc.place || "",
                    lat: loc.lat,
                    lon: loc.lon,
                    timezone: "Asia/Kolkata",
                    crop_hint: "aman_rice",
                    season_hint: "kharif",
                    plot_m2: 400,
                    place_kind: "place",
                    place_name: loc.place || loc.district || undefined,
                  });
                }}
              >
                {t.authApplyDash}
              </button>
            ) : null}
            {acctMsg ? <p className="text-xs text-neo-muted">{acctMsg}</p> : null}
          </>
        ) : (
          <>
            <p className="text-sm text-neo-muted">{t.authSettingsHint}</p>
            <button className="neo-btn text-sm" onClick={() => setAuthModal(true)}>
              {t.authSignIn}
            </button>
          </>
        )}
      </section>

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
        <label className="block text-sm">
          {t.advisorModel}
          <select
            className="neo-in mt-1 w-full px-3 py-2"
            value={settings.llmProvider || "ollama"}
            onChange={(e) => setSettings({ llmProvider: e.target.value })}
          >
            {llms.map((row) => (
              <option key={row.id} value={row.id}>
                {row.id} ({row.model})
              </option>
            ))}
          </select>
        </label>
        <p className="text-xs text-neo-muted">{t.advisorModelHint}</p>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={Boolean(settings.showEvidence)}
            onChange={(e) => setSettings({ showEvidence: e.target.checked })}
          />
          {t.showEvidence}
        </label>
        <p className="text-xs text-neo-muted">{t.showEvidenceHint}</p>
        <p className="text-xs text-neo-muted">{t.replyIn}</p>
        <div className="flex gap-2">
          {(["en", "hi", "bn", "auto"] as const).map((l) => (
            <button key={l} className={`neo-btn flex-1 ${outputLocale === l ? "neo-btn-on" : ""}`} onClick={() => setOutputLocale(l)}>
              {l === "auto" ? t.replyAuto : l.toUpperCase()}
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
            {[
              [30, locale === "hi" ? "30 सेकंड" : locale === "bn" ? "৩০ সেকেন্ড" : "30 seconds"],
              [60, locale === "hi" ? "1 मिनट" : locale === "bn" ? "১ মিনিট" : "1 minute"],
              [120, locale === "hi" ? "2 मिनट" : locale === "bn" ? "২ মিনিট" : "2 minutes"],
              [300, locale === "hi" ? "5 मिनट" : locale === "bn" ? "৫ মিনিট" : "5 minutes"],
              [600, locale === "hi" ? "10 मिनट" : locale === "bn" ? "১০ মিনিট" : "10 minutes"],
            ].map(([s, label]) => (
              <option key={s} value={s}>
                {label}
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
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={Boolean(settings.displayNullValues)}
            onChange={(e) => setSettings({ displayNullValues: e.target.checked })}
          />
          {t.displayNullValues || "Display Null Values"}
        </label>
        <p className="text-xs text-neo-muted">{t.displayNullValuesHint || "Show weather and sensor metrics with empty or null readings."}</p>
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
    home: t.tabHome,
    analytics: t.tabAnalytics,
    data: t.tabData,
    map: t.tabMap,
    model: t.tabModel,
    chat: t.tabChat,
    settings: t.tabSettings,
  };
  return map[id] || id;
}
