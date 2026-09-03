"use client";

import { useMemo, useState } from "react";
import type { DashboardSnapshot } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";
import { rain, rainUnit, temp, tempUnit } from "@/lib/units";
import { useApp } from "@/lib/store";
import { Forecast7DayDeck } from "./Forecast7DayDeck";

export function OutlookTable({ dash, locale }: { dash: DashboardSnapshot; locale: Locale }) {
  const t = COPY[locale];
  const units = useApp((s) => s.settings.units);
  const days = dash.predictive.outlook_days || [];
  const [showRawTable, setShowRawTable] = useState(false);

  return (
    <div className="space-y-4">
      {/* 7-Day Interactive Synoptic & Chrono Deck */}
      <Forecast7DayDeck dash={dash} locale={locale} />

      {/* Raw Outlook Data Table Collapse */}
      <section className="neo overflow-auto p-4">
        <div className="flex items-center justify-between gap-2 flex-wrap mb-3">
          <div>
            <h3 className="text-sm font-bold">
              {t.tabForecast} · {locale === "hi" ? "सारांश खाता" : locale === "bn" ? "সারসংক্ষেপ খতিয়ান" : "Summary Ledger"}
            </h3>
            <p className="mt-0.5 text-[11px] text-neo-muted">
              {locale === "hi"
                ? "7-दिवसीय कृषि व मौसम जल संतुलन बहीखाता"
                : locale === "bn"
                ? "৭ দিনের কৃষি ও আবহাওয়া জল ভারসাম্য খতিয়ান"
                : "7-day agricultural & meteorological water balance ledger"}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowRawTable(!showRawTable)}
            className="neo-btn text-xs font-bold px-3 py-1"
          >
            {showRawTable
              ? (locale === "hi" ? "तालिका छुपाएं" : locale === "bn" ? "সারণী লুকান" : "Hide Raw Table")
              : (locale === "hi" ? "पूर्ण तालिका देखें" : locale === "bn" ? "সম্পূর্ণ সারণী দেখুন" : "Show Raw Table")}
          </button>
        </div>

        <div className="mb-3 flex flex-wrap gap-2 text-xs">
          <span className="chip">
            {t.rain7}: {rain(dash.predictive.precip_7d_mm, units)}
          </span>
          <span className="chip">
            {t.balance}: {rain(dash.predictive.water_balance_7d_mm, units)}
          </span>
          <span className="chip">
            {t.irrigateDays}: {(dash.predictive.irrigate_dates || []).length}
          </span>
          <span className="chip">
            {t.floodDays}: {(dash.predictive.flood_watch_dates || []).length}
          </span>
        </div>

        {showRawTable && (
          <table className="w-full text-left text-sm mt-2">
            <thead className="text-xs text-neo-muted">
              <tr>
                <th className="py-2">{t.colDate}</th>
                <th>{t.colRain.replace("mm", rainUnit(units))}</th>
                <th>{t.colProb}</th>
                <th>{t.colTmax.replace("°C", tempUnit(units))}</th>
                <th>{t.colEt0.replace("mm", rainUnit(units))}</th>
                <th>{t.colSoil}</th>
                <th>{t.colWb}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {days.map((d) => (
                <tr
                  key={d.date}
                  className="border-t border-neo-line hover:bg-[color-mix(in_srgb,var(--accent)_6%,transparent)] transition"
                  data-testid={`forecast-day-${d.date}`}
                >
                  <td className="py-2 font-mono">{d.date}</td>
                  <td className="font-mono text-neo-rain font-bold">{rain(d.precip_mm, units)}</td>
                  <td className="font-mono">{d.precip_prob_pct}%</td>
                  <td className="font-mono text-neo-text font-bold">{temp(d.temp_max_c, units)}</td>
                  <td className="font-mono">{rain(d.et0_mm, units)}</td>
                  <td className="font-mono">{d.soil_m3m3 ?? "—"}</td>
                  <td className={`font-mono font-bold ${d.water_balance_mm >= 0 ? "text-emerald-500" : "text-amber-500"}`}>
                    {rain(d.water_balance_mm, units)}
                  </td>
                  <td>
                    {d.flood_watch ? <span className="chip level-alert text-[10px]">{t.floodWatch}</span> : null}
                    {d.irrigate ? <span className="chip level-ok text-[10px]">{t.applyHint}</span> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
