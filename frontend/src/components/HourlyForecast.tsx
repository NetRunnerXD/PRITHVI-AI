"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HourlySlot } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";
import { rain, rainUnit, speed, temp, tempUnit } from "@/lib/units";
import { useApp } from "@/lib/store";

const tip = {
  background: "var(--card)",
  border: "1px solid var(--line)",
  borderRadius: 12,
  fontSize: 12,
  color: "var(--text)",
};

export function HourlyForecast({
  date,
  hours,
  locale,
}: {
  date: string;
  hours: HourlySlot[];
  locale: Locale;
}) {
  const t = COPY[locale];
  const units = useApp((s) => s.settings.units);
  const rows = hours.filter((h) => h.date === date);
  const chart = rows.map((h) => ({
    h: (h.hour || "").slice(0, 5),
    rain: units === "imperial" ? (h.precip_mm || 0) / 25.4 : h.precip_mm || 0,
    temp: h.temp_c == null ? null : units === "imperial" ? (h.temp_c * 9) / 5 + 32 : h.temp_c,
    wind: h.wind_kmh == null ? null : units === "imperial" ? h.wind_kmh * 0.621 : h.wind_kmh,
  }));
  return (
    <section className="neo mt-3 overflow-auto p-4" data-testid="hourly-forecast">
      <h4 className="text-sm font-bold">
        {t.hourlyForecast} · {date}
      </h4>
      <p className="mb-3 text-[11px] text-neo-muted">{t.hourlyHint}</p>
      {rows.length ? (
        <>
          <div className="mb-3 grid gap-3 lg:grid-cols-2">
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chart}>
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="h" stroke="var(--muted)" fontSize={9} interval={2} />
                  <YAxis stroke="var(--muted)" fontSize={9} width={28} unit={` ${rainUnit(units)}`} />
                  <Tooltip contentStyle={tip} />
                  <Bar dataKey="rain" fill="var(--rain)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chart}>
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="h" stroke="var(--muted)" fontSize={9} interval={2} />
                  <YAxis stroke="var(--muted)" fontSize={9} width={28} />
                  <Tooltip contentStyle={tip} />
                  <Line type="monotone" dataKey="temp" stroke="var(--accent)" dot={false} name={tempUnit(units)} />
                  <Line type="monotone" dataKey="wind" stroke="var(--muted)" dot={false} name="wind" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
          <table className="w-full text-left text-xs">
            <thead className="text-neo-muted">
              <tr>
                <th className="py-1">{t.colHour}</th>
                <th>{t.sky}</th>
                <th>{t.colRain.replace("mm", rainUnit(units))}</th>
                <th>%</th>
                <th>{tempUnit(units)}</th>
                <th>{t.windSpeed}</th>
                <th>{t.gust}</th>
                <th>{t.humidity}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((h) => (
                <tr key={h.t} className="border-t border-neo-line font-mono">
                  <td className="py-1">{(h.hour || "").slice(0, 5)}</td>
                  <td className="font-sans">{h.sky_label || "—"}</td>
                  <td>{rain(h.precip_mm, units)}</td>
                  <td>{h.precip_prob_pct == null ? "—" : `${h.precip_prob_pct}%`}</td>
                  <td>{temp(h.temp_c, units)}</td>
                  <td>{speed(h.wind_kmh, units)}</td>
                  <td>{speed(h.wind_gust_kmh, units)}</td>
                  <td>{h.rh_pct == null ? "—" : `${h.rh_pct}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : (
        <p className="text-sm text-neo-muted">{t.noHourly}</p>
      )}
    </section>
  );
}
