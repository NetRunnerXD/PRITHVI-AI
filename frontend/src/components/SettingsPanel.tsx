"use client";

import { useEffect, useState } from "react";
import { COPY, type Locale } from "@/i18n/copy";
import { apiUrl, SHOW_DEV } from "@/lib/config";
import { gpsFix, patchAlertLocation, patchProfile } from "@/lib/auth";
import { useApp } from "@/lib/store";
import { DistrictSearch } from "./DistrictSearch";
import type { Density, TabId, ThemeId, UnitSys } from "@/types/dashboard";

const THEMES: ThemeId[] = ["sand", "mist", "dusk_mist", "monsoon", "midnight", "ocean", "contrast", "sih_mobile"];
const TABS: TabId[] = ["home", "analytics", "data", "map", "model", "chat"];

type LlmRow = { id: string; model: string; ok?: boolean; reason?: string };

const LLM_LABELS: Record<string, string> = {
  local: "Local Ollama",
  worker: "Ollama worker (home PC)",
  groq: "Groq",
  gemini: "Gemini",
  ollama: "Ollama",
};

export function SettingsPanel() {
  const {
    locale,
    setLocale,
    outputLocale,
    setOutputLocale,
    settings,
    setSettings,
    account,
    setAccount,
    setAuthModal,
    setLocation,
    location,
    viewMode,
    setViewMode,
  } = useApp();
  const t = COPY[locale];
  const [llms, setLlms] = useState<LlmRow[]>([{ id: "ollama", model: "qwen2.5:3b" }]);
  useEffect(() => {
    let stop = false;
    fetch(apiUrl("/health"))
      .then((r) => r.json())
      .then((body) => {
        if (stop) return;
        const rows = ((body?.llm?.settings || body?.llm?.available || []) as LlmRow[]).filter(
          (r) => ["local", "worker", "groq", "gemini", "ollama"].includes(r.id)
        );
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
  const [demoSms, setDemoSms] = useState<{
    text?: string;
    engine?: string;
    to?: string;
    chars?: number;
    sms?: { enabled?: boolean; dry_run?: boolean; has_key?: boolean };
  } | null>(null);
  const [demoBusy, setDemoBusy] = useState<"off" | "preview" | "send">("off");
  const [demoMsg, setDemoMsg] = useState("");
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
        <h3 className="text-sm font-bold">
          {locale === "hi" ? "डेमो SMS" : locale === "bn" ? "ডেমো SMS" : "Demo SMS"}
        </h3>
        {demoSms?.text ? (
          <pre className="neo-in whitespace-pre-wrap px-3 py-2 text-sm">{demoSms.text}</pre>
        ) : (
          <p className="text-xs text-neo-muted">
            {locale === "hi" ? "अभी कोई पूर्वावलोकन नहीं।" : locale === "bn" ? "এখনও কোনো প্রিভিউ নেই।" : "No preview yet."}
          </p>
        )}
        {demoSms?.engine ? (
          <p className="text-[11px] text-neo-muted">
            {demoSms.engine === "ollama" ? "Ollama" : demoSms.engine} · {demoSms.chars || 0}/160
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <button
            className="neo-btn text-sm"
            disabled={demoBusy !== "off"}
            onClick={() => {
              setDemoBusy("preview");
              setDemoMsg("");
              const q = new URLSearchParams();
              if (location?.lat != null) q.set("lat", String(location.lat));
              if (location?.lon != null) q.set("lon", String(location.lon));
              if (location?.place_name || location?.district) q.set("place", location.place_name || location.district);
              q.set("locale", locale);
              void fetch(apiUrl(`/sms/demo/preview?${q.toString()}`), { method: "POST" })
                .then(async (r) => {
                  const body = await r.json().catch(() => ({}));
                  if (!r.ok) throw new Error(body?.detail || r.statusText);
                  setDemoSms(body);
                  setDemoMsg(locale === "hi" ? "पूर्वावलोकन तैयार।" : locale === "bn" ? "প্রিভিউ তৈরি।" : "Preview ready.");
                })
                .catch((e) => setDemoMsg(String(e)))
                .finally(() => setDemoBusy("off"));
            }}
          >
            {demoBusy === "preview"
              ? locale === "hi"
                ? "बना रहे हैं…"
                : locale === "bn"
                ? "তৈরি হচ্ছে…"
                : "Generating…"
              : locale === "hi"
              ? "SMS पूर्वावलोकन"
              : locale === "bn"
              ? "SMS প্রিভিউ"
              : "Generate preview"}
          </button>
          <button
            className="neo-btn text-sm"
            disabled={demoBusy !== "off"}
            onClick={() => {
              setDemoBusy("send");
              setDemoMsg("");
              const q = new URLSearchParams();
              if (location?.lat != null) q.set("lat", String(location.lat));
              if (location?.lon != null) q.set("lon", String(location.lon));
              if (location?.place_name || location?.district) q.set("place", location.place_name || location.district);
              void fetch(apiUrl(`/sms/demo/send?${q.toString()}`), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: demoSms?.text || "", locale }),
              })
                .then(async (r) => {
                  const body = await r.json().catch(() => ({}));
                  if (!r.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "Send failed (need FAST2SMS_API_KEY)");
                  setDemoSms({ ...demoSms, text: body.text, to: body.to, sms: body.sms });
                  setDemoMsg(
                    body.send?.dry_run
                      ? locale === "hi"
                        ? "की नहीं — भेजा नहीं गया।"
                        : locale === "bn"
                        ? "কী নেই — পাঠানো হয়নি।"
                        : "No API key — not sent."
                      : locale === "hi"
                      ? "SMS भेजा गया।"
                      : locale === "bn"
                      ? "SMS পাঠানো হয়েছে।"
                      : "SMS sent.",
                  );
                })
                .catch((e) => setDemoMsg(String(e)))
                .finally(() => setDemoBusy("off"));
            }}
          >
            {demoBusy === "send"
              ? locale === "hi"
                ? "भेज रहे हैं…"
                : locale === "bn"
                ? "পাঠানো হচ্ছে…"
                : "Sending…"
              : locale === "hi"
              ? "SMS भेजें"
              : locale === "bn"
              ? "SMS পাঠান"
              : "Send SMS"}
          </button>
        </div>
        {demoMsg ? <p className="text-xs font-semibold">{demoMsg}</p> : null}
      </section>

      <section className="neo space-y-3 p-4">
        <h3 className="text-sm font-bold">
          {locale === "hi" ? "डैशबोर्ड दृश्य मोड (View Mode)" : locale === "bn" ? "ড্যাশবোর্ড ভিউ মোড (View Mode)" : "Dashboard View Mode"}
        </h3>
        <p className="text-xs text-neo-muted">
          {locale === "hi"
            ? "डिटेल मोड में विस्तृत डेटा व चार्ट दिखेंगे। ओवरव्यू मोड में सरल व संक्षिप्त सारांश दिखेगा।"
            : locale === "bn"
            ? "ডিটেইল মোডে সম্পূর্ণ ডেটা ও চার্ট প্রদর্শিত হবে। ওভারভিউ মোডে সহজবোধ্য সারসংক্ষেপ থাকবে।"
            : "Choose between detailed telemetry/charts or a simplified plain-language layman overview."}
        </p>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            className={`neo-btn flex flex-col items-center justify-center p-3 text-center transition-all ${
              viewMode === "detail"
                ? "border-neo-accent bg-[color-mix(in_srgb,var(--accent)_12%,transparent)] font-bold text-neo-accent ring-1 ring-neo-accent shadow-sm"
                : "text-neo-muted hover:text-neo-text"
            }`}
            onClick={() => setViewMode("detail")}
          >
            <span className="text-xs font-bold">{locale === "hi" ? "डिटेल (Detail)" : locale === "bn" ? "ডিটেইল (Detail)" : "Detail Data"}</span>
            <span className="mt-0.5 text-[10px] text-neo-muted opacity-80">
              {locale === "hi" ? "चार्ट, मेट्रिक्स व डेटा" : locale === "bn" ? "চার্ট, মেট্রিক্স ও ডেটা" : "Charts, Telemetry & Sensor Data"}
            </span>
          </button>
          <button
            type="button"
            className={`neo-btn flex flex-col items-center justify-center p-3 text-center transition-all ${
              viewMode === "overview"
                ? "border-amber-500 bg-amber-500/10 font-bold text-amber-600 dark:text-amber-400 ring-1 ring-amber-500 shadow-sm"
                : "text-neo-muted hover:text-neo-text"
            }`}
            onClick={() => setViewMode("overview")}
          >
            <span className="text-xs font-bold">{locale === "hi" ? "ओवरव्यू (Overview)" : locale === "bn" ? "ওভারভিউ (Overview)" : "Layman Overview"}</span>
            <span className="mt-0.5 text-[10px] text-neo-muted opacity-80">
              {locale === "hi" ? "सरल सारांश व अलर्ट" : locale === "bn" ? "সহজ সারসংক্ষেপ ও সতর্কতা" : "Plain Language & Fast Summary"}
            </span>
          </button>
        </div>
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
            value={settings.llmProvider === "ollama" ? "local" : settings.llmProvider || "local"}
            onChange={(e) => setSettings({ llmProvider: e.target.value })}
          >
            {llms.map((row) => (
              <option key={row.id} value={row.id} disabled={row.ok === false}>
                {LLM_LABELS[row.id] || row.id} ({row.model})
                {row.ok === false && row.reason ? ` — ${row.reason}` : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={Boolean(settings.showEvidence)}
            onChange={(e) => setSettings({ showEvidence: e.target.checked })}
          />
          {t.showEvidence}
        </label>
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
        <label className="flex items-center gap-2 text-sm pt-1">
          <input
            type="checkbox"
            checked={Boolean(settings.showAdvancedTabs)}
            onChange={(e) => setSettings({ showAdvancedTabs: e.target.checked })}
          />
          {locale === "hi"
            ? "उन्नत वैज्ञानिक टैब (डेटा, मॉडल, विश्लेषण) दिखाएं"
            : locale === "bn"
            ? "উন্নত বৈজ্ঞানিক ট্যাব (উপাত্ত, মডেল, বিশ্লেষণ) দেখান"
            : "Show Advanced Tabs (Data, Model, Analytics)"}
        </label>
        <p className="text-xs text-neo-muted">
          {locale === "hi"
            ? "साइडबार में मॉडल्स, डेटा एवं एनालिटिक्स टैब को सक्रिय या छुपाएं।"
            : locale === "bn"
            ? "সাইডবারে মডেল, উপাত্ত ও বিশ্লেষণ ট্যাব দৃশ্যমান বা লুকান।"
            : "Display or hide deep-dive Analytics, Raw Data, and ML Model tabs in the sidebar."}
        </p>
      </section>


      {/* Developer Controls: Individual API & Machine Learning Toggles (enabled when SHOW_DEV=True) */}
      {SHOW_DEV ? (
        <section className="neo space-y-4 p-4 md:col-span-2 border-t-2 border-neo-accent/30">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--line)] pb-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-bold">🛠️ Developer Telemetry &amp; Process Controls</span>
                <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[10px] font-mono font-bold text-amber-600 dark:text-amber-400">
                  PRO / DEV
                </span>
              </div>
              <p className="text-xs text-neo-muted mt-0.5">
                Selectively disable or enable upstream data providers and intensive ML pipeline modules to isolate performance bottlenecks or reduce latency.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="neo-btn text-xs px-2.5 py-1"
                onClick={() => setSettings({ devDisabledProviders: [] })}
              >
                Enable All
              </button>
              <button
                type="button"
                className="neo-btn text-xs px-2.5 py-1 text-amber-600"
                onClick={() =>
                  setSettings({
                    devDisabledProviders: [
                      "nasa-power",
                      "nasa-power-clim",
                      "data.gov.in-mandi",
                      "data.gov.in-aqi",
                      "open-meteo-models",
                      "openaq-hist",
                      "science",
                      "anomalies",
                    ],
                  })
                }
              >
                Turbo Mode (Fastest)
              </button>
            </div>
          </div>

          {/* Upstream APIs */}
          <div className="space-y-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-neo-muted">External Telemetry APIs</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
              {[
                { id: "open-meteo", name: "Open-Meteo Forecast", latency: "~300ms", desc: "Core weather & 7-day outlook" },
                { id: "open-meteo-models", name: "Open-Meteo 8-Model Blend", latency: "~2.2s", desc: "ECMWF, GFS, ICON ensemble" },
                { id: "open-meteo-flood", name: "GloFAS Flood API", latency: "~500ms", desc: "River discharge rates" },
                { id: "open-meteo-air", name: "CAMS Air Quality API", latency: "~400ms", desc: "PM2.5, PM10, gases" },
                { id: "open-meteo-marine", name: "Marine Waves & SST", latency: "~600ms", desc: "Coastal wave height & swell" },
                { id: "data.gov.in-aqi", name: "Data.gov.in CPCB AQI", latency: "~1.8s", desc: "National ground sensors" },
                { id: "data.gov.in-mandi", name: "Data.gov.in Mandi Prices", latency: "~2.4s", desc: "Agmarknet crop arrivals" },
                { id: "imd-cap", name: "IMD CAP Bulletins", latency: "~900ms", desc: "National early warning XML" },
                { id: "imd-rest", name: "IMD Official Station REST", latency: "~1.2s", desc: "Local synoptic weather" },
                { id: "sachet", name: "Sachet NDMA Feeds", latency: "~800ms", desc: "State disaster alerts" },
                { id: "nasa-power", name: "NASA POWER Daily", latency: "~1.5s", desc: "16-day surface solar & rain (off by default)" },
                { id: "nasa-power-clim", name: "NASA POWER 8-year climate", latency: "~2.8s", desc: "Historical matrix for anomalies (off by default)" },
                { id: "usgs-seismic", name: "USGS Seismic Feed", latency: "~350ms", desc: "Earthquake events geo-radius" },
                { id: "incois-tsunami", name: "INCOIS Tsunami Bulletins", latency: "~700ms", desc: "ITEWS Indian Ocean threat" },
                { id: "openaq-hist", name: "OpenAQ Historical Archive", latency: "~1.1s", desc: "48h pollutant trend records" },
                { id: "waqi", name: "WAQI Realtime Station", latency: "~300ms", desc: "Alternative IoT AQI sensor" },
                { id: "mosdac", name: "ISRO MOSDAC Satellite", latency: "~900ms", desc: "INSAT-3D HDF5/thermal feed" },
                { id: "gdacs", name: "GDACS Disaster Events", latency: "~300ms", desc: "UN/EU global disaster RSS" },
              ].map((api) => {
                const disabledList = settings.devDisabledProviders || [];
                const isOff = disabledList.includes(api.id);
                return (
                  <div
                    key={api.id}
                    onClick={() => {
                      const next = isOff ? disabledList.filter((x) => x !== api.id) : [...disabledList, api.id];
                      setSettings({ devDisabledProviders: next });
                    }}
                    className={`cursor-pointer rounded-xl border p-2.5 transition-all select-none ${
                      isOff
                        ? "bg-red-500/10 border-red-500/30 opacity-70"
                        : "bg-[var(--card)] border-[var(--line)] hover:border-neo-accent shadow-xs"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold truncate">{api.name}</span>
                      <span
                        className={`h-2.5 w-2.5 rounded-full ${
                          isOff ? "bg-red-500" : "bg-emerald-500 animate-pulse"
                        }`}
                      />
                    </div>
                    <div className="flex items-center justify-between text-[10px] mt-1 text-neo-muted">
                      <span className="truncate">{api.desc}</span>
                      <span className="font-mono shrink-0 ml-1">{api.latency}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Backend Machine Learning & Decision Science Processes */}
          <div className="space-y-2 pt-2 border-t border-[var(--line)]">
            <h4 className="text-xs font-bold uppercase tracking-wider text-neo-muted">
              Backend ML &amp; Decision Science Engines
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
              {[
                { id: "science", name: "Decision-Science Pipeline", desc: "Hysteresis, phenology & livelihood" },
                { id: "anomalies", name: "Climatological Anomaly Engine", desc: "Z-score tail anomaly detection" },
                { id: "risks", name: "Multi-Hazard Risk Engine", desc: "10-factor weighted linear scores" },
                { id: "regret", name: "Regret-Theory Irrigation Advice", desc: "Minimax regret water evaluation" },
                { id: "sat_live", name: "INSAT Computer Vision / Optical Flow", desc: "Live satellite cloud motion" },
                { id: "vera", name: "VERA-MoE Neural Architecture", desc: "Mixture-of-Experts neural blend" },
              ].map((proc) => {
                const disabledList = settings.devDisabledProviders || [];
                const isOff = disabledList.includes(proc.id);
                return (
                  <div
                    key={proc.id}
                    onClick={() => {
                      const next = isOff ? disabledList.filter((x) => x !== proc.id) : [...disabledList, proc.id];
                      setSettings({ devDisabledProviders: next });
                    }}
                    className={`cursor-pointer rounded-xl border p-2.5 transition-all select-none ${
                      isOff
                        ? "bg-red-500/10 border-red-500/30 opacity-70"
                        : "bg-[var(--card)] border-[var(--line)] hover:border-neo-accent shadow-xs"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold truncate">{proc.name}</span>
                      <span
                        className={`h-2.5 w-2.5 rounded-full ${
                          isOff ? "bg-red-500" : "bg-emerald-500 animate-pulse"
                        }`}
                      />
                    </div>
                    <div className="text-[10px] mt-1 text-neo-muted truncate">{proc.desc}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      ) : null}
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
