"use client";

import type { DashboardSnapshot } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";
import { rain, rainUnit, temp, tempUnit } from "@/lib/units";
import { useApp } from "@/lib/store";

export function OutlookTable({ dash, locale }: { dash: DashboardSnapshot; locale: Locale }) {
  const t = COPY[locale];
  const units = useApp((s) => s.settings.units);
  const days = dash.predictive.outlook_days || [];
  return (
    <section className="neo overflow-auto p-4">
      <h3 className="text-sm font-bold">{t.tabForecast}</h3>
      <div className="mb-3 mt-2 flex flex-wrap gap-2 text-xs">
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
      <table className="w-full text-left text-sm">
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
            <tr key={d.date} className="border-t border-neo-line">
              <td className="py-2 font-mono">{d.date}</td>
              <td>{rain(d.precip_mm, units)}</td>
              <td>{d.precip_prob_pct}%</td>
              <td>{temp(d.temp_max_c, units)}</td>
              <td>{rain(d.et0_mm, units)}</td>
              <td>{d.soil_m3m3 ?? "—"}</td>
              <td>{rain(d.water_balance_mm, units)}</td>
              <td>
                {d.flood_watch ? <span className="chip level-alert">{t.floodWatch}</span> : null}
                {d.irrigate ? <span className="chip level-ok">{t.applyHint}</span> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
