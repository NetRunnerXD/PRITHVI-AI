"use client";

import { useEffect, useMemo, useState } from "react";
import type { DashboardSnapshot, EarlyWarning, Location } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";
import { searchPlaces } from "@/lib/api";
import { useApp } from "@/lib/store";
import { dist, localizeDigits } from "@/lib/units";
import { factorLabel, riskTitle } from "@/lib/plain";
import { LaymanSummaryBody } from "../LaymanSummaryView";
import { getAlertsLaymanSummary } from "@/lib/laymanSummaries";
import { tWord, translateSeverity } from "./i18n";
import { alertDot, alertTone, suggLevel, suggestionLevel, haversineKm } from "./helpers";
import { formatAlertWindow, formatOfficialBulletin, getGeneralizedAlertGuidance, groupAlertsByLocation, openAlert, parseAlertLocation, alertTimePhase, INDIA_CITIES_MAP, type AlertCluster } from "./alertModel";
import { getHazardTheme, IconChevronDown, IconCross, IconCyclone, IconExternal, IconFileBulletin, IconMapNavigator, IconPin, IconSeismic, IconShieldAlert, IconSparkle, IconTsunamiWave, IconWarningSign } from "./icons";
import { AirCard, EarthquakeTsunamiCard, LandWeatherCard, MarineWeatherCard, NowcastSection, TropicalCycloneCard } from "./cards";

export function RiskAlertPanel({
  dash,
  locale,
  onNavigateData,
  allAlerts,
  className,
  isMobileCollapsible,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  onNavigateData?: (subTab: string) => void;
  allAlerts: any[];
  className?: string;
  isMobileCollapsible?: boolean;
}) {
  const t = COPY[locale];
  const setTab = useApp((s) => s.setTab);
  const setLocation = useApp((s) => s.setLocation);
  const openFloatChat = useApp((s) => s.openFloatChat);
  const applySuggestion = useApp((s) => s.applySuggestion);
  const [panelTab, setPanelTab] = useState<"alerts" | "risks">("alerts");
  const [selectedCluster, setSelectedCluster] = useState<AlertCluster | null>(null);
  const [mobileExpanded, setMobileExpanded] = useState<boolean>(allAlerts.length > 0);
  const [expandedRiskId, setExpandedRiskId] = useState<string | null>(null);
  const devDisabled = useApp((s) => s.settings.devDisabledProviders || []);
  const risksDisabled = devDisabled.includes("risks");

  const mergedAlerts = useMemo(() => allAlerts, [allAlerts]);

  const risks = useMemo(() => {
    if (risksDisabled) return [];
    return [...(dash.risks || [])].sort((a, b) => (b.score_pct ?? 0) - (a.score_pct ?? 0));
  }, [dash.risks, risksDisabled]);

  const mesh = useMemo(() => {
    return (dash.risks_india || []).slice(0, 12);
  }, [dash.risks_india]);

  const liveAlerts = useMemo(
    () => mergedAlerts.filter((w) => alertTimePhase(w) !== "past"),
    [mergedAlerts],
  );

  const clusters = useMemo(() => {
    return groupAlertsByLocation(liveAlerts, dash.location);
  }, [liveAlerts, dash.location]);

  const handleSwitchLocation = (locInfo: {
    city?: string | null;
    state?: string | null;
    lat?: number | null;
    lon?: number | null;
    placeFormatted?: string | null;
    alerts?: any[];
  }) => {
    // 1. Direct coordinates if present on the cluster or inside any alert item
    let lat = locInfo.lat != null && !isNaN(Number(locInfo.lat)) ? Number(locInfo.lat) : null;
    let lon = locInfo.lon != null && !isNaN(Number(locInfo.lon)) ? Number(locInfo.lon) : null;

    if ((lat == null || lon == null) && locInfo.alerts && locInfo.alerts.length > 0) {
      for (const a of locInfo.alerts) {
        if (a.lat != null && a.lon != null && !isNaN(Number(a.lat)) && !isNaN(Number(a.lon))) {
          lat = Number(a.lat);
          lon = Number(a.lon);
          break;
        }
      }
    }

    const rawCity = (locInfo.city || "").trim();
    const rawState = (locInfo.state || "").trim();
    const cleanCity = rawCity.replace(/\s*\([^)]*\)/g, "").trim().toLowerCase();
    const cleanState = rawState.replace(/\s*\([^)]*\)/g, "").trim().toLowerCase();

    // 2. Check instant India cities / state capital dictionary map
    const matched =
      (cleanCity ? INDIA_CITIES_MAP[cleanCity] : null) ||
      Object.values(INDIA_CITIES_MAP).find(
        (c) => (cleanState && c.state.toLowerCase() === cleanState) || (cleanCity && c.city.toLowerCase() === cleanCity)
      );

    if (lat != null && lon != null) {
      const cName = matched?.city || locInfo.city || locInfo.placeFormatted || "Area";
      const sName = matched?.state || locInfo.state || "India";
      setLocation({
        id: `loc_${lat}_${lon}`,
        label: `${cName}, ${sName}`,
        district: cName,
        state: sName,
        country: "India",
        lat,
        lon,
        timezone: "Asia/Kolkata",
        crop_hint: "Rice",
        place_name: cName,
      });
      return;
    }

    if (matched) {
      setLocation({
        id: `loc_${matched.lat}_${matched.lon}`,
        label: `${matched.city}, ${matched.state}`,
        district: matched.city,
        state: matched.state,
        country: "India",
        lat: matched.lat,
        lon: matched.lon,
        timezone: "Asia/Kolkata",
        crop_hint: "Rice",
        place_name: matched.city,
      });
      return;
    }

    const searchQuery = [rawCity, rawState].filter(Boolean).join(", ") || locInfo.placeFormatted || "";
    if (!searchQuery) return;

    searchPlaces(searchQuery)
      .then((res) => {
        if (res && res[0]) {
          setLocation(res[0]);
        }
      })
      .catch(() => undefined);
  };

  return (
    <>
      <aside
        className={`neo neo-section-alerts flex flex-col overflow-hidden select-none ${className || "w-full"}`}
      >
        {/* Header with Segmented Navigation & Collapsible Trigger on Mobile */}
        <div
          className={`flex shrink-0 items-center justify-between gap-2 border-b border-[color-mix(in_srgb,var(--line)_60%,var(--warn)_40%)] px-3 py-2 bg-[color-mix(in_srgb,var(--card)_80%,var(--warn)_8%)] ${
            isMobileCollapsible ? "cursor-pointer" : ""
          }`}
          onClick={isMobileCollapsible ? () => setMobileExpanded((v) => !v) : undefined}
        >
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="live-dot" style={{ backgroundColor: "var(--warn)", boxShadow: "0 0 8px var(--warn)" }} aria-hidden />
            <p className="alerts-section-title text-[11px] font-black uppercase tracking-[0.18em] truncate">
              {panelTab === "alerts"
                ? t.alertsPanel || (locale === "hi" ? "अलर्ट" : locale === "bn" ? "সতর্কতা" : "Alerts")
                : (locale === "hi" ? "जोखिम" : locale === "bn" ? "ঝুঁকি" : "RISKS")}
            </p>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setPanelTab("alerts");
                  if (isMobileCollapsible && !mobileExpanded) setMobileExpanded(true);
                }}
                className={`rounded-lg px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-1.5 ${panelTab === "alerts"
                    ? "bg-neo-accent text-white shadow-sm"
                    : "text-neo-muted hover:text-neo-text"
                  }`}
              >
                <span>{t.alertsPanel || (locale === "hi" ? "अलर्ट" : locale === "bn" ? "সতর্কতা" : "Alerts")}</span>
                {liveAlerts.length > 0 && (
                  <span className="rounded-full bg-gradient-to-r from-rose-500 to-red-600 text-white px-1.5 py-0.5 text-[8px] font-black leading-none shadow-sm animate-pulse">
                    {localizeDigits(liveAlerts.length, locale)}
                  </span>
                )}
              </button>
              {!risksDisabled && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setPanelTab("risks");
                    if (isMobileCollapsible && !mobileExpanded) setMobileExpanded(true);
                  }}
                  className={`rounded-lg px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${panelTab === "risks"
                      ? "bg-neo-accent text-white shadow-sm"
                      : "text-neo-muted hover:text-neo-text"
                    }`}
                >
                  <span>{locale === "hi" ? "जोखिम मेट्रिक्स" : locale === "bn" ? "ঝুঁকি মেট্রিক্স" : "RISKS"}</span>
                </button>
              )}
            </div>

            {isMobileCollapsible && (
              <button
                type="button"
                aria-expanded={mobileExpanded}
                aria-label={mobileExpanded ? "Collapse Risk Section" : "Expand Risk Section"}
                className="neo-btn p-1 h-7 w-7 flex items-center justify-center rounded-lg text-neo-muted hover:text-neo-text"
                onClick={(e) => {
                  e.stopPropagation();
                  setMobileExpanded((v) => !v);
                }}
              >
                <IconChevronDown
                  className={`w-3.5 h-3.5 text-amber-500 transition-transform duration-300 ${
                    mobileExpanded ? "rotate-180" : ""
                  }`}
                />
              </button>
            )}
          </div>
        </div>

        {/* Content Area with Custom Scrollbar (Auto-adjusting up to max-h-[450px]) */}
        <div
          className={`modal-scrollbar min-h-0 max-h-[450px] overflow-y-auto p-2.5 space-y-2.5 transition-all duration-300 ${
            isMobileCollapsible && !mobileExpanded ? "hidden" : "block animate-in fade-in slide-in-from-top-1"
          }`}
        >
          {panelTab === "alerts" ? (
            clusters.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full min-h-[140px] text-center p-4">
                <div className="h-8 w-8 rounded-full bg-[color-mix(in_srgb,var(--accent)_12%,transparent)] border border-[color-mix(in_srgb,var(--accent)_30%,transparent)] flex items-center justify-center text-neo-accent mb-2">
                  <IconShieldAlert className="w-4 h-4" />
                </div>
                <p className="text-xs font-bold text-neo-text">
                  {locale === "hi" ? "कोई आपातकालीन बुलेटिन नहीं" : locale === "bn" ? "কোনো জরুরি সতর্কতা নেই" : "No active urgent bulletins"}
                </p>
                <p className="text-[11px] text-neo-muted mt-1 max-w-xs">
                  {locale === "hi"
                    ? "पृथ्वी-नेत्र द्वारा बाढ़, वायु, समुद्री व भूकंपीय सुरक्षा स्कैन निरंतर सक्रिय हैं।"
                    : locale === "bn"
                    ? "পৃথিবী-নেত্র দ্বারা বন্যা, বায়ু, সামুদ্রিক ও ভূমিকম্প নজরদারি অবিরাম সক্রিয় রয়েছে।"
                    : "Continuous multi-hazard radar monitoring for flood, air quality, seismic and marine safety is active."}
                </p>
              </div>
            ) : (
              clusters.map((cluster) => {
                const theme = cluster.primaryTheme;

                return (
                  <div
                    key={cluster.id}
                    className={`group relative w-full rounded-2xl border-l-[5px] p-3 text-left transition-all hover:shadow-lg hover:-translate-y-0.5 cursor-pointer border border-[var(--line)] ${theme.borderClass}`}
                    style={{ background: theme.cardBg }}
                    onClick={() => handleSwitchLocation(cluster)}
                  >
                    {/* Top Row: Place Heading: City (State) + Highest Severity Badge + Multi-Threat Counter */}
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-1.5 flex-1 min-w-0">
                        <div
                          className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md"
                          style={{ backgroundColor: `color-mix(in srgb, ${theme.color} 15%, transparent)`, color: theme.color }}
                        >
                          <IconPin className="w-3 h-3" />
                        </div>
                        <h4 className="truncate text-xs font-black tracking-tight text-neo-text" title={cluster.placeFormatted}>
                          {cluster.placeFormatted}
                        </h4>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        {cluster.alerts.length > 1 && (
                          <span className="rounded-md bg-black/40 backdrop-blur-md px-1.5 py-0.5 text-[8px] font-mono font-black uppercase text-white shadow-xs border border-white/20">
                            {localizeDigits(cluster.alerts.length, locale)} {locale === "hi" ? "खतरे" : locale === "bn" ? "ঝুঁকি" : "Hazards"}
                          </span>
                        )}
                        <span
                          className="rounded-md px-2 py-0.5 text-[8px] font-black uppercase tracking-wider text-white shadow-sm flex items-center gap-1"
                          style={{ backgroundColor: theme.color }}
                        >
                          <span className="h-1.5 w-1.5 rounded-full bg-white animate-ping" />
                          <span>{translateSeverity(cluster.highestSeverity, locale)}</span>
                        </span>
                      </div>
                    </div>

                    {/* Threat Subtitle / Compound Title */}
                    <p className="mt-1 line-clamp-1 text-[11px] font-bold text-neo-text">
                      {cluster.compositeTitle}
                    </p>
                    {formatAlertWindow(cluster.alerts[0] || {}) ? (
                      <p className="mt-0.5 line-clamp-1 text-[10px] font-mono text-neo-muted">
                        {formatAlertWindow(cluster.alerts[0])}
                      </p>
                    ) : null}

                    {/* Directive / Action Line */}
                    <div
                      className="mt-1.5 rounded-xl px-2.5 py-1.5 text-[10px] leading-snug flex items-start gap-1.5 shadow-xs border"
                      style={{
                        backgroundColor: `color-mix(in srgb, ${theme.color} 10%, var(--card))`,
                        borderColor: `color-mix(in srgb, ${theme.color} 30%, transparent)`,
                      }}
                    >
                      <IconWarningSign
                        className="w-3.5 h-3.5 shrink-0 mt-0.5"
                        style={{ color: theme.color }}
                      />
                      <span className="line-clamp-1 font-bold text-neo-text">{cluster.compositeAction}</span>
                    </div>

                    {/* Bottom Action Strip with Distance & Directives */}
                    <div className="mt-2.5 flex items-center justify-between pt-2 border-t border-[color-mix(in_srgb,var(--line)_50%,transparent)] text-[9px]">
                      <div className="flex items-center gap-1.5 font-mono">
                        {cluster.isCurrentLoc ? (
                          <span className="font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                            {locale === "hi" ? "सक्रिय स्थान" : locale === "bn" ? "বর্তমান অবস্থান" : "Active Location"}
                          </span>
                        ) : cluster.distKm != null ? (
                          <span className="font-medium text-neo-muted flex items-center gap-1">
                            <IconMapNavigator className="w-2.5 h-2.5" />
                            {localizeDigits(cluster.distKm, locale)} km {locale === "hi" ? "स्थान से दूरी" : locale === "bn" ? "স্থান থেকে দূরত্ব" : "from pin"}
                          </span>
                        ) : (
                          <span className="font-medium text-neo-muted">{locale === "hi" ? "क्षेत्रीय दायरा" : locale === "bn" ? "আঞ্চলিক পরিধি" : "Regional Scope"}</span>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSwitchLocation(cluster);
                          }}
                          className="font-bold text-neo-accent hover:underline flex items-center gap-1"
                          title={
                            locale === "hi"
                              ? `डैशबोर्ड स्थान को ${cluster.placeFormatted} पर बदलें`
                              : locale === "bn"
                              ? `ড্যাশবোর্ড অবস্থান ${cluster.placeFormatted}-এ পরিবর্তন করুন`
                              : `Switch dashboard location to ${cluster.placeFormatted}`
                          }
                        >
                          <span>{tWord("switchPin", locale, "Switch Pin")}</span>
                          <IconExternal className="w-2.5 h-2.5" />
                        </button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedCluster(cluster);
                          }}
                          className="rounded-lg bg-[color-mix(in_srgb,var(--accent)_12%,transparent)] border border-[color-mix(in_srgb,var(--accent)_25%,transparent)] px-2 py-0.5 font-bold text-neo-accent hover:bg-neo-accent hover:text-white transition-all flex items-center gap-1 shadow-sm"
                        >
                          <IconFileBulletin className="w-2.5 h-2.5" />
                          <span>{tWord("details", locale, "Details")}</span>
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })
            )
          ) : (
            <div className="space-y-2">
              {risks.length === 0 ? (
                <p className="text-center text-xs text-neo-muted py-6">No risk factors evaluated.</p>
              ) : (
                risks.map((r) => {
                  const score = r.score_pct ?? 0;
                  const isSevere = score >= 70 || r.severity === "danger" || r.severity === "extreme";
                  const isElevated = !isSevere && (score >= 40 || r.severity === "warning" || r.severity === "alert");
                  const isExpanded = expandedRiskId === r.id;

                  const toneColor = isSevere
                    ? "text-rose-600 dark:text-rose-400"
                    : isElevated
                      ? "text-amber-600 dark:text-amber-400"
                      : "text-slate-600 dark:text-slate-400";

                  const barBg = isSevere
                    ? "bg-rose-600 dark:bg-rose-500"
                    : isElevated
                      ? "bg-amber-500 dark:bg-amber-500"
                      : "bg-slate-400/80 dark:bg-slate-500/80";

                  const badgeStyle = isSevere
                    ? "bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/20"
                    : isElevated
                      ? "bg-amber-500/10 text-amber-800 dark:text-amber-300 border-amber-500/20"
                      : "bg-slate-500/10 text-slate-700 dark:text-slate-300 border-slate-500/20";

                  const topFactor = [...(r.factors || [])].sort(
                    (a, b) => (b.contribution_pct ?? 0) - (a.contribution_pct ?? 0)
                  )[0];
                  const topContrib = topFactor?.contribution_pct ?? 0;

                  return (
                    <div
                      key={r.id}
                      className={`neo-in p-2.5 rounded-xl cursor-pointer hover:border-[color-mix(in_srgb,var(--line)_60%,var(--accent))] transition-all border ${
                        isExpanded
                          ? "border-neo-accent shadow-sm bg-[color-mix(in_srgb,var(--accent)_3%,var(--card))]"
                          : "border-[var(--line)]"
                      }`}
                      onClick={() => setExpandedRiskId(isExpanded ? null : r.id)}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <IconChevronDown
                            className={`w-3.5 h-3.5 text-neo-muted transition-transform duration-200 shrink-0 ${
                              isExpanded ? "rotate-180 text-neo-accent" : ""
                            }`}
                          />
                          <span className="text-xs font-bold text-neo-text truncate">{riskTitle(r.id, locale, r.label)}</span>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <span className={`font-mono text-xs font-black ${toneColor}`}>
                            {localizeDigits(score, locale)}%
                          </span>
                          <span className={`chip text-[8px] font-extrabold uppercase px-2 py-0.5 rounded-md border ${badgeStyle}`}>
                            {translateSeverity(r.severity, locale)}
                          </span>
                        </div>
                      </div>

                      {/* Progress bar */}
                      <div className="mt-1.5 h-1.5 w-full rounded-full bg-[color-mix(in_srgb,var(--line)_70%,transparent)] overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${barBg}`}
                          style={{
                            width: `${Math.min(100, Math.max(5, score))}%`,
                          }}
                        />
                      </div>

                      {score === 0 || topContrib === 0 ? (
                        <p className="mt-1.5 text-[9px] text-neo-muted truncate flex items-center gap-1.5">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500/80 inline-block shrink-0" />
                          <span>{locale === "hi" ? "सामान्य स्थिति · कोई सक्रिय जोखिम चालक नहीं" : locale === "bn" ? "স্বাভাবিক অবস্থা · কোনো সক্রিয় ঝুঁকি চালক নেই" : "Nominal baseline · No active risk drivers"}</span>
                        </p>
                      ) : (
                        <p className="mt-1.5 text-[9px] text-neo-muted truncate flex items-center justify-between">
                          <span>{locale === "hi" ? "प्रमुख चालक: " : locale === "bn" ? "প্রধান চালক: " : "Primary driver: "}<span className="font-semibold text-neo-text">{factorLabel(topFactor.id, locale, topFactor.label)}</span> ({localizeDigits(topContrib, locale)}%)</span>
                          <span className="text-[8px] text-neo-accent font-semibold ml-1">
                            {isExpanded ? (locale === "hi" ? "कारक छिपाएं ▲" : locale === "bn" ? "ফ্যাক্টর লুকান ▲" : "Hide factors ▲") : (locale === "hi" ? "कारक दिखाएं ▼" : locale === "bn" ? "ফ্যাক্টর দেখুন ▼" : "Show factors ▼")}
                          </span>
                        </p>
                      )}

                      {/* Expanded Factor Breakdown Drawer */}
                      {isExpanded && (
                        <div className="mt-2.5 pt-2.5 border-t border-[var(--line)] space-y-2 animate-in fade-in slide-in-from-top-1 duration-200">
                          <div className="flex items-center justify-between text-[10px] text-neo-muted font-bold">
                            <span>{locale === "hi" ? "योगदान देने वाले कारक" : locale === "bn" ? "অবদানকারী প্রভাব ও ফ্যাক্টর" : "Contributing Drivers & Factors"}</span>
                            <span>{locale === "hi" ? "प्रभाव" : locale === "bn" ? "ওজন" : "Weight"}</span>
                          </div>

                          {(r.factors || []).length === 0 ? (
                            <p className="text-[10px] text-neo-muted italic">No isolated risk factors.</p>
                          ) : (
                            <div className="space-y-1.5">
                              {r.factors.map((f, idx) => (
                                <div key={idx} className="bg-[var(--card)] p-1.5 rounded-lg border border-[var(--line)] text-[10px]">
                                  <div className="flex items-center justify-between font-semibold">
                                    <span className="text-neo-text">{factorLabel(f.id, locale, f.label)}</span>
                                    <span className="font-mono text-neo-accent font-bold">{localizeDigits(f.contribution_pct, locale)}%</span>
                                  </div>
                                  <div className="mt-1 h-1 w-full rounded-full bg-[color-mix(in_srgb,var(--line)_60%,transparent)] overflow-hidden">
                                    <div
                                      className="h-full rounded-full bg-neo-accent transition-all duration-300"
                                      style={{ width: `${Math.min(100, Math.max(5, f.contribution_pct))}%` }}
                                    />
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}

                          <div className="flex items-center justify-between pt-1 text-[9px] text-neo-muted font-mono">
                            {r.confidence_pct != null && <span>{locale === "hi" ? "विश्वसनीयता" : locale === "bn" ? "নির্ভরযোগ্যতা" : "Confidence"}: {localizeDigits(r.confidence_pct, locale)}%</span>}
                            {r.horizon_hours != null && <span>{locale === "hi" ? "अवधि" : locale === "bn" ? "মেয়াদ" : "Horizon"}: {localizeDigits(r.horizon_hours, locale)}h</span>}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
              {mesh.length > 0 ? (
                <div className="pt-2 mt-1 border-t border-[var(--line)] space-y-1.5">
                  <p className="text-[9px] font-black uppercase tracking-wider text-neo-muted px-0.5">
                    {t.indiaHqRisks}
                  </p>
                  {mesh.map((row) => {
                    const score = Number(row.flood_score ?? 0);
                    return (
                      <button
                        key={`${row.state}-${row.hq}`}
                        type="button"
                        className="w-full text-left neo-in p-2 rounded-lg flex items-center justify-between gap-2"
                        onClick={() =>
                          handleSwitchLocation({
                            city: row.hq,
                            state: row.state,
                            lat: row.lat,
                            lon: row.lon,
                          })
                        }
                      >
                        <span className="text-[11px] font-bold truncate">
                          {row.hq}
                          {row.state ? `, ${row.state}` : ""}
                        </span>
                        <span className="font-mono text-[11px] font-black text-amber-600">{score}</span>
                      </button>
                    );
                  })}
                </div>
              ) : null}
              <button
                type="button"
                onClick={() => onNavigateData?.("risks")}
                className="w-full text-center text-[10px] font-bold text-neo-accent hover:underline py-1"
              >
                {locale === "hi" ? "पूर्ण जोखिम मैट्रिक्स एवं विश्लेषण देखें →" : locale === "bn" ? "সম্পূর্ণ ঝুঁকি ম্যাট্রিক্স ও বিশ্লেষণ দেখুন →" : "View Full Risk Matrix & Insights →"}
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* In-Depth Warning Details Modal Dialog (Multi-Hazard Cluster, Zero Emojis, Sleek Scrollbar & JSON Cleaner) */}
      {selectedCluster && (
        <AlertDetailModal
          cluster={selectedCluster}
          dash={dash}
          onClose={() => setSelectedCluster(null)}
          onSwitchLocation={handleSwitchLocation}
          onOpenMap={(c) => {
            applySuggestion({ center: c, tab: "map", zoom: 8 });
            setSelectedCluster(null);
          }}
          onAskAssistant={(prompt) => {
            openFloatChat(prompt);
            setSelectedCluster(null);
          }}
        />
      )}
    </>
  );
}


export function AlertDetailModal({
  cluster,
  dash,
  onClose,
  onSwitchLocation,
  onOpenMap,
  onAskAssistant,
}: {
  cluster: AlertCluster;
  dash: DashboardSnapshot;
  onClose: () => void;
  onSwitchLocation: (loc: {
    city: string;
    state: string;
    lat?: number | null;
    lon?: number | null;
    placeFormatted: string;
  }) => void;
  onOpenMap: (center: [number, number]) => void;
  onAskAssistant: (prompt: string) => void;
}) {
  const [activeTab, setActiveTab] = useState<number>(-1); // -1 = Composite Synthesis Overview, 0..N = Individual Bulletin
  const locale = useApp((s) => s.locale);

  const isMulti = cluster.alerts.length > 1;
  const currentHazard = activeTab >= 0 ? cluster.hazardItems[activeTab] : cluster.hazardItems[0];
  const activeAlert = activeTab >= 0 ? cluster.alerts[activeTab] : cluster.alerts[0];
  const theme = activeTab >= 0 ? currentHazard.theme : cluster.primaryTheme;
  const bulletin = formatOfficialBulletin(activeAlert.body, activeAlert.title);

  const cleanSourceName = (src?: string) => {
    const s = (src || "").toLowerCase();
    if (s.includes("rituchakra") || s.includes("prithvi") || s.includes("scan")) {
      return "Prithvi-Netra AI National Radar";
    }
    if (s.includes("imd") || s.includes("cap")) {
      return "IMD CAP National Early Warning Network";
    }
    if (s.includes("cpcb") || s.includes("data.gov")) {
      return "Central Pollution Control Board (CPCB)";
    }
    if (s.includes("flood") || s.includes("discharge")) {
      return "Global Hydrological Discharge Model";
    }
    return src || "Official Early Warning Feed";
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-2xl max-h-[88vh] flex flex-col rounded-3xl border border-[var(--line)] shadow-2xl bg-[var(--card)] select-none text-left overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Header Bar */}
        <div
          className="flex items-start justify-between gap-3 p-5 border-b border-[var(--line)] shrink-0"
          style={{ backgroundColor: theme.cardBg }}
        >
          <div>
            <div className="flex items-center gap-2">
              <IconPin className="w-4 h-4 text-neo-accent" />
              <h2 className="text-lg sm:text-xl font-black text-neo-text tracking-tight">
                {cluster.placeFormatted}
              </h2>
            </div>
            <p className="mt-0.5 text-xs sm:text-sm font-black" style={{ color: theme.color }}>
              {activeTab === -1 ? cluster.compositeTitle : currentHazard.hazardLabel}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`chip text-[9px] font-black uppercase px-2.5 py-1 ${cluster.isExtreme
                  ? "bg-red-500/20 text-red-600 dark:text-red-400 border border-red-500/30 font-extrabold"
                  : cluster.isWarning
                    ? "bg-amber-500/20 text-amber-600 dark:text-amber-400 border border-amber-500/30 font-extrabold"
                    : "bg-blue-500/20 text-blue-600 dark:text-blue-400 border border-blue-500/30 font-extrabold"
                }`}
            >
              {activeTab === -1 ? cluster.highestSeverity : (activeAlert.severity || cluster.highestSeverity)}
            </span>
            <button
              type="button"
              onClick={onClose}
              className="h-8 w-8 rounded-full bg-[color-mix(in_srgb,var(--line)_80%,transparent)] border border-[var(--line)] flex items-center justify-center text-neo-muted hover:text-neo-text hover:bg-[var(--line)] transition-colors"
            >
              <IconCross className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Multi-Hazard Tab Switcher if cluster has multiple active alerts */}
        {isMulti && (
          <div className="flex items-center gap-1.5 px-5 py-2.5 border-b border-[var(--line)] bg-[color-mix(in_srgb,var(--bg)_70%,transparent)] overflow-x-auto modal-scrollbar shrink-0">
            <button
              type="button"
              onClick={() => setActiveTab(-1)}
              className={`px-3 py-1 rounded-xl text-xs font-black transition-all shrink-0 ${activeTab === -1
                  ? "bg-neo-accent text-white shadow-sm"
                  : "bg-[var(--card)] border border-[var(--line)] text-neo-muted hover:text-neo-text"
                }`}
            >
              {locale === "hi" ? "समग्र सारांश" : locale === "bn" ? "সার্বিক সারসংক্ষেপ" : "Overview Synthesis"} ({cluster.alerts.length})
            </button>
            {cluster.hazardItems.map((hi, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setActiveTab(idx)}
                className={`px-3 py-1 rounded-xl text-xs font-bold transition-all shrink-0 border flex items-center gap-1.5 ${activeTab === idx
                    ? "text-white shadow-sm font-black"
                    : "bg-[var(--card)] text-neo-muted hover:text-neo-text"
                  }`}
                style={{
                  borderColor: activeTab === idx ? hi.theme.color : "var(--line)",
                  backgroundColor: activeTab === idx ? hi.theme.color : undefined,
                }}
              >
                <span>{hi.label}</span>
              </button>
            ))}
          </div>
        )}

        {/* Scrollable Content Area with Custom Scrollbar */}
        <div className="modal-scrollbar min-h-0 flex-1 overflow-y-auto p-5 space-y-4">
          {/* Location Switch Banner */}
          <div className="flex items-center justify-between gap-3 p-3 rounded-2xl bg-[color-mix(in_srgb,var(--accent)_10%,transparent)] border border-[color-mix(in_srgb,var(--accent)_30%,transparent)]">
            <div className="text-xs min-w-0">
              <p className="font-black text-neo-text flex items-center gap-1.5">
                <IconMapNavigator className="w-3.5 h-3.5 text-neo-accent shrink-0" />
                <span>{locale === "hi" ? "लक्षित क्षेत्र:" : locale === "bn" ? "টার্গেট অঞ্চল:" : "Target Sector:"}</span>
                <span className="text-neo-accent font-black break-words">{cluster.placeFormatted}</span>
                {cluster.distKm != null && !cluster.isCurrentLoc && (
                  <span className="text-[10px] font-mono text-neo-muted font-normal">
                    ({cluster.distKm} {locale === "hi" ? "किमी दूर" : locale === "bn" ? "কিমি দূরে" : "km away"})
                  </span>
                )}
              </p>
              <p className="text-[10px] text-neo-muted mt-0.5 leading-relaxed">
                {cluster.isCurrentLoc
                  ? (locale === "hi"
                      ? "यह सक्रिय स्थान वर्तमान में डैशबोर्ड में लोड है।"
                      : locale === "bn"
                      ? "এই সক্রিয় স্থানটি বর্তমানে ড্যাশবোর্ডে লোড করা আছে।"
                      : "Active location currently loaded in the dashboard.")
                  : (locale === "hi"
                      ? "स्थानीय रडार, हाइटोमीटर और 7-दिवसीय पूर्वानुमान देखने के लिए पिन बदलें।"
                      : locale === "bn"
                      ? "স্থানীয় রাডার, হাইটোগ্রাফ এবং ৭ দিনের পূর্বাভাসের জন্য পিন পরিবর্তন করুন।"
                      : "Switch active dashboard pin to load localized radar, hyetograph, and 7-day forecast.")}
              </p>
            </div>
            {!cluster.isCurrentLoc && (
              <button
                type="button"
                onClick={() => {
                  onSwitchLocation(cluster);
                  onClose();
                }}
                className="px-3.5 py-1.5 text-xs font-black rounded-xl bg-neo-accent text-white hover:brightness-110 shadow-sm transition-all shrink-0 flex items-center gap-1"
              >
                <span>{locale === "hi" ? "स्थान बदलें" : locale === "bn" ? "পিন পরিবর্তন" : "Switch Pin"}</span>
                <IconExternal className="w-3 h-3" />
              </button>
            )}
          </div>

          {activeTab === -1 ? (
            /* Composite Synthesis Overview Mode */
            <div className="space-y-4">
              {/* Multi-Hazard Matrix */}
              <div className="neo-in p-4 rounded-2xl space-y-3 border border-[var(--line)]">
                <div className="flex items-center gap-2">
                  <IconShieldAlert className="w-4 h-4 text-neo-accent shrink-0" />
                  <h3 className="text-xs font-black uppercase tracking-wider text-neo-accent">
                    {locale === "hi" ? "समग्र आपदा जोखिम आकलन" : locale === "bn" ? "যৌথ দুর্যোগ ঝুঁকি পর্যালোচনা" : "Compound Threat Assessment"}
                  </h3>
                </div>
                <div className="space-y-2.5 text-xs">
                  {cluster.hazardItems.map((hi, i) => (
                    <div
                      key={i}
                      className="p-3 rounded-xl border border-[var(--line)]"
                      style={{ backgroundColor: `color-mix(in srgb, ${hi.theme.color} 6%, var(--card))` }}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-black text-xs" style={{ color: hi.theme.color }}>
                          {hi.hazardLabel}
                        </span>
                        <span className="chip text-[8px] font-extrabold uppercase px-2 py-0.5 rounded-md border border-[var(--line)]">
                          {hi.alert.severity || "Warning"}
                        </span>
                      </div>
                      {formatAlertWindow(hi.alert) ? (
                        <p className="mt-1 text-[10px] font-mono text-neo-muted">{formatAlertWindow(hi.alert)}</p>
                      ) : null}
                      <p className="text-neo-text mt-1 text-xs leading-relaxed font-medium">
                        {hi.guidance.threat} {hi.guidance.guidance}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Integrated Public Directives */}
              <div className="p-3.5 rounded-2xl bg-[color-mix(in_srgb,var(--warn)_10%,transparent)] border border-[color-mix(in_srgb,var(--warn)_25%,transparent)] space-y-2">
                <span className="font-black text-neo-warn text-[11px] uppercase tracking-wider flex items-center gap-1.5">
                  <IconWarningSign className="w-3.5 h-3.5 text-neo-warn shrink-0" />
                  {locale === "hi" ? "एकीकृत आपातकालीन सुरक्षा निर्देश:" : locale === "bn" ? "সম্মিলিত জরুরি পদক্ষেপ নির্দেশিকা:" : "Consolidated Emergency Action Directives:"}
                </span>
                <ul className="space-y-1.5 text-xs text-neo-text font-medium pl-1">
                  {Array.from(new Set(cluster.hazardItems.map((h) => h.guidance.action))).map((action, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="font-bold text-neo-warn">•</span>
                      <span>{action}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            /* Specific Hazard Bulletin View */
            <div className="space-y-4">
              {/* Section 1: Generalized Public Threat Assessment & Safety Protocol */}
              <div className="neo-in p-4 rounded-2xl space-y-2.5 border border-[var(--line)]">
                <div className="flex items-center gap-2">
                  <IconShieldAlert className="w-4 h-4 text-neo-accent shrink-0" />
                  <h3 className="text-xs font-black uppercase tracking-wider text-neo-accent">
                    {currentHazard.guidance.category} — Safety Protocol
                  </h3>
                </div>
                <div className="space-y-2 text-xs">
                  <div>
                    <span className="font-bold text-neo-muted text-[10px] uppercase tracking-wider block">
                      {locale === "hi" ? "जोखिम आकलन:" : locale === "bn" ? "ঝুঁকি পর্যালোচনা:" : "Threat Assessment:"}
                    </span>
                    <p className="text-neo-text leading-relaxed font-semibold mt-0.5">{currentHazard.guidance.threat}</p>
                    {formatAlertWindow(activeAlert) ? (
                      <p className="mt-1 text-[11px] font-mono font-semibold text-neo-accent">{formatAlertWindow(activeAlert)}</p>
                    ) : null}
                  </div>
                  <div>
                    <span className="font-bold text-neo-muted text-[10px] uppercase tracking-wider block">
                      {locale === "hi" ? "पर्यावरणीय प्रभाव:" : locale === "bn" ? "পরিবেশগত প্রভাব:" : "Environmental Impact:"}
                    </span>
                    <p className="text-neo-text leading-relaxed mt-0.5">{currentHazard.guidance.guidance}</p>
                  </div>
                  <div className="p-2.5 rounded-xl bg-[color-mix(in_srgb,var(--warn)_10%,transparent)] border border-[color-mix(in_srgb,var(--warn)_25%,transparent)]">
                    <span className="font-black text-neo-warn text-[10px] uppercase tracking-wider flex items-center gap-1">
                      <IconWarningSign className="w-3 h-3 text-neo-warn" />
                      {locale === "hi" ? "अनुशंसित नागरिक सुरक्षा निर्देश:" : locale === "bn" ? "সুপারিশকৃত নাগরিক সুরক্ষা নির্দেশিকা:" : "Recommended Public Directives:"}
                    </span>
                    <p className="text-neo-text font-medium text-xs leading-relaxed mt-1">{currentHazard.guidance.action}</p>
                  </div>
                </div>
              </div>

              {/* Section 2: Official Agency Bulletin */}
              <div className="neo-in p-4 rounded-2xl space-y-3 border border-[var(--line)]">
                <div className="flex items-center justify-between gap-2 border-b border-[var(--line)] pb-2">
                  <div className="flex items-center gap-2">
                    <IconFileBulletin className="w-4 h-4 text-neo-text shrink-0" />
                    <h3 className="text-xs font-black uppercase tracking-wider text-neo-text">
                      {locale === "hi" ? "आधिकारिक मौसम बुलेटिन" : locale === "bn" ? "সরকারি আবহাওয়া বুলেটিন" : "Official Authority Bulletin"}
                    </h3>
                  </div>
                  <span className="text-[9px] font-mono text-neo-muted uppercase font-bold">
                    {locale === "hi" ? "स्रोत:" : locale === "bn" ? "উৎস:" : "Source:"} {cleanSourceName(activeAlert.source)}
                  </span>
                </div>

                {bulletin.isStructuredJson ? (
                  <div className="space-y-2.5 text-xs">
                    {bulletin.headline && (
                      <div>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-neo-muted block">Headline / Event</span>
                        <p className="font-bold text-neo-text text-sm mt-0.5">{bulletin.headline}</p>
                      </div>
                    )}
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-neo-muted block">Meteorological Summary</span>
                      <p className="text-neo-text leading-relaxed mt-0.5 whitespace-pre-wrap">{bulletin.description}</p>
                    </div>
                    {bulletin.instructions && (
                      <div>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-neo-warn block">Action & Directives</span>
                        <p className="text-neo-text leading-relaxed mt-0.5">{bulletin.instructions}</p>
                      </div>
                    )}
                    {bulletin.areaDesc && (
                      <div>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-neo-muted block">Geographical Coverage</span>
                        <p className="text-neo-muted font-mono text-[11px] mt-0.5">{bulletin.areaDesc}</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-3 rounded-xl bg-[color-mix(in_srgb,var(--bg)_60%,transparent)] border border-[var(--line)]">
                    <p className="text-xs leading-relaxed text-neo-text whitespace-pre-wrap font-sans">
                      {bulletin.description}
                    </p>
                  </div>
                )}

                {activeAlert.url && (
                  <div className="pt-1">
                    <a
                      href={activeAlert.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-xs font-black text-neo-accent hover:underline"
                    >
                      <span>{locale === "hi" ? "आधिकारिक पोर्टल बुलेटिन खोलें" : locale === "bn" ? "অফিসিয়াল পোর্টাল বুলেটিন খুলুন" : "Open Official Portal Bulletin"}</span>
                      <IconExternal className="w-3.5 h-3.5" />
                    </a>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Technical Telemetry & Metadata Parameters */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
            <div className="neo-in p-2.5 rounded-xl text-center border border-[var(--line)]">
              <span className="text-[9px] font-bold text-neo-muted uppercase block">
                {locale === "hi" ? "गंभीरता" : locale === "bn" ? "তীব্রতা" : "Severity"}
              </span>
              <span className="font-mono text-xs font-bold text-neo-accent capitalize mt-0.5 block">{cluster.highestSeverity}</span>
            </div>
            <div className="neo-in p-2.5 rounded-xl text-center border border-[var(--line)]">
              <span className="text-[9px] font-bold text-neo-muted uppercase block">
                {locale === "hi" ? "निर्देशांक" : locale === "bn" ? "স্থানাঙ্ক" : "Coordinates"}
              </span>
              <span className="font-mono text-xs font-bold text-neo-text mt-0.5 block truncate">
                {cluster.lat != null && cluster.lon != null ? `${cluster.lat.toFixed(2)}°, ${cluster.lon.toFixed(2)}°` : (locale === "hi" ? "क्षेत्रीय" : locale === "bn" ? "আঞ্চলিক" : "Regional")}
              </span>
            </div>
            <div className="neo-in p-2.5 rounded-xl text-center border border-[var(--line)]">
              <span className="text-[9px] font-bold text-neo-muted uppercase block">
                {locale === "hi" ? "सक्रिय आपदाएं" : locale === "bn" ? "সক্রিয় দুর্যোগ" : "Active Hazards"}
              </span>
              <span className="font-mono text-xs font-bold text-neo-text capitalize mt-0.5 block">
                {cluster.alerts.length} {locale === "hi" ? "चेतावनियां" : locale === "bn" ? "সতর্কতা" : "Warnings"}
              </span>
            </div>
            <div className="neo-in p-2.5 rounded-xl text-center border border-[var(--line)]">
              <span className="text-[9px] font-bold text-neo-muted uppercase block">
                {locale === "hi" ? "दूरी" : locale === "bn" ? "দূরত্ব" : "Live Distance"}
              </span>
              <span className="font-mono text-xs font-bold text-emerald-600 dark:text-emerald-400 mt-0.5 block">
                {cluster.isCurrentLoc
                  ? (locale === "hi" ? "सक्रिय पिन" : locale === "bn" ? "সক্রিয় পিন" : "Active Pin")
                  : cluster.distKm != null
                  ? `${cluster.distKm} ${locale === "hi" ? "किमी" : locale === "bn" ? "কিমি" : "km"}`
                  : (locale === "hi" ? "राज्यव्यापी" : locale === "bn" ? "রাজ্যব্যাপী" : "Statewide")}
              </span>
            </div>
          </div>
        </div>

        {/* Fixed Bottom Action Bar */}
        <div className="flex items-center justify-between gap-2 p-4 border-t border-[var(--line)] bg-[color-mix(in_srgb,var(--card)_95%,transparent)] shrink-0 flex-wrap">
          <div className="flex items-center gap-2">
            {cluster.lat != null && cluster.lon != null && (
              <button
                type="button"
                onClick={() => onOpenMap([cluster.lat!, cluster.lon!])}
                className="px-3.5 py-2 text-xs font-bold rounded-xl border border-[var(--line)] bg-[var(--card)] hover:bg-[var(--line)] transition-all flex items-center gap-1.5 shadow-sm"
              >
                <IconMapNavigator className="w-3.5 h-3.5 text-neo-accent" />
                <span>{locale === "hi" ? "मानचित्र पर देखें" : locale === "bn" ? "মানচিত্রে দেখুন" : "View on Map"}</span>
              </button>
            )}
            <button
              type="button"
              onClick={() =>
                onAskAssistant(
                  `Explain the emergency hazard protocol and localized weather conditions for the alert at ${cluster.placeFormatted}`
                )
              }
              className="px-3.5 py-2 text-xs font-bold rounded-xl border border-[var(--line)] bg-[var(--card)] hover:bg-[var(--line)] transition-all flex items-center gap-1.5 shadow-sm text-neo-text"
            >
              <IconSparkle className="w-3.5 h-3.5 text-neo-accent" />
              <span>{locale === "hi" ? "PRITHVI-AI से पूछें" : locale === "bn" ? "PRITHVI-AI কে জিজ্ঞাসা" : "Ask PRITHVI-AI"}</span>
            </button>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2 text-xs font-bold rounded-xl bg-[color-mix(in_srgb,var(--line)_80%,transparent)] hover:bg-[var(--line)] transition-all"
          >
            {locale === "hi" ? "बंद करें" : locale === "bn" ? "বন্ধ করুন" : "Close"}
          </button>
        </div>
      </div>
    </div>
  );
}


export function AlertStat({ label, value }: { label: string; value: string }) {
  const displayNull = useApp((s) => s.settings.displayNullValues);
  if (!displayNull && (value == null || value === "—" || value === "" || value === "undefined" || value === "null")) {
    return null;
  }
  return (
    <div className="neo-in rounded-xl px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-widest text-neo-muted">{label}</p>
      <p className="mt-0.5 truncate font-mono text-xs font-semibold">{value}</p>
    </div>
  );
}


export function HomeHazardStrip({
  dash,
  locale,
  units,
  onNavigateData,
  forceSummary,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  units: "metric" | "imperial";
  onNavigateData?: (subTab: string) => void;
  forceSummary?: boolean;
}) {
  return (
    <div className="space-y-3">
      {/* 3 Innovative Environmental & Earth Science Cards */}
      <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 items-start">
        <AirCard dash={dash} locale={locale} onNavigateData={onNavigateData} forceSummary={forceSummary} />
        <LandWeatherCard dash={dash} locale={locale} units={units} onNavigateData={onNavigateData} forceSummary={forceSummary} />
        <MarineWeatherCard dash={dash} locale={locale} units={units} onNavigateData={onNavigateData} forceSummary={forceSummary} className="sm:col-span-2 lg:col-span-1" />
      </div>

      {/* 3 Dedicated Geo-Hazard & Disaster Early Warning Cards (Cyclone, Seismic/Tsunami, Nowcasting / Next 6h) */}
      <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 items-start">
        <TropicalCycloneCard dash={dash} locale={locale} units={units} onNavigateData={onNavigateData} forceSummary={forceSummary} />
        <EarthquakeTsunamiCard dash={dash} locale={locale} units={units} onNavigateData={onNavigateData} forceSummary={forceSummary} />
        <NowcastSection dash={dash} locale={locale} units={units} className="w-full sm:col-span-2 lg:col-span-1" forceSummary={forceSummary} />
      </div>
    </div>
  );
}

