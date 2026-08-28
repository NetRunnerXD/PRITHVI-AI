"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardSnapshot } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";
import { useApp } from "@/lib/store";
import { rainUnit, tempUnit } from "@/lib/units";

const tip = {
  background: "var(--card)",
  border: "1px solid var(--line)",
  borderRadius: 12,
  fontSize: 12,
  color: "var(--text)",
};

export function ForecastCharts({ dash, locale }: { dash: DashboardSnapshot; locale: Locale }) {
  const t = COPY[locale];
  const units = useApp((s) => s.settings.units);
  const toR = (mm: number) => (units === "imperial" ? mm / 25.4 : mm);
  const toT = (c?: number | null) => (c == null ? c : units === "imperial" ? (c * 9) / 5 + 32 : c);
  const days = (dash.predictive.outlook_days || []).map((d) => ({
    d: d.date.slice(5),
    rain: toR(d.precip_mm),
    et0: toR(d.et0_mm),
    tmax: toT(d.temp_max_c),
    tmin: toT(d.temp_min_c),
    soil: d.soil_m3m3,
    prob: d.precip_prob_pct,
    wb: toR(d.water_balance_mm),
  }));
  const ncHours = dash.science?.nowcast?.hours || [];
  const hourly = (
    ncHours.length
      ? ncHours.map((h) => ({ t: h.t.slice(11, 16), mm: toR(h.mm), engine: h.engine }))
      : (dash.descriptive.series.precip_hourly || []).slice(0, 36).map((p) => ({
          t: p.t.slice(11, 16),
          mm: toR(p.value),
          engine: "",
        }))
  );
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="neo p-4">
        <h3 className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">
          {t.rainVsDry}
        </h3>
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={days}>
              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis dataKey="d" stroke="var(--muted)" fontSize={10} />
              <YAxis stroke="var(--muted)" fontSize={10} width={28} unit={` ${rainUnit(units)}`} />
              <Tooltip contentStyle={tip} />
              <Legend />
              <Bar dataKey="rain" fill="var(--rain)" radius={[6, 6, 0, 0]} />
              <Bar dataKey="et0" fill="var(--accent)" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
      <section className="neo p-4">
        <h3 className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{tempUnit(units)}</h3>
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={days}>
              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis dataKey="d" stroke="var(--muted)" fontSize={10} />
              <YAxis stroke="var(--muted)" fontSize={10} width={28} />
              <Tooltip contentStyle={tip} />
              <Line type="monotone" dataKey="tmax" stroke="var(--gold)" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="tmin" stroke="var(--rain)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
      <section className="neo p-4">
        <h3 className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.soil} + {t.chanceOfRain}</h3>
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={days}>
              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis dataKey="d" stroke="var(--muted)" fontSize={10} />
              <YAxis yAxisId="soil" stroke="var(--accent)" fontSize={9} width={32} domain={[0, 0.5]} />
              <YAxis yAxisId="prob" orientation="right" stroke="var(--rain)" fontSize={9} width={28} domain={[0, 100]} />
              <Tooltip contentStyle={tip} />
              <Line yAxisId="soil" type="monotone" dataKey="soil" stroke="var(--accent)" strokeWidth={2} name={t.soil} />
              <Line yAxisId="prob" type="monotone" dataKey="prob" stroke="var(--rain)" strokeWidth={2} name={t.chanceOfRain} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
      <section className="neo p-4">
        <h3 className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.nextHours}</h3>
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={hourly}>
              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis dataKey="t" stroke="var(--muted)" fontSize={9} interval={3} />
              <YAxis stroke="var(--muted)" fontSize={10} width={28} />
              <Tooltip contentStyle={tip} />
              <Bar dataKey="mm" fill="var(--rain)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}
