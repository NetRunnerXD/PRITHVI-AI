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

const tip = { background: "#e8eef4", border: "none", borderRadius: 12, fontSize: 12 };

export function ForecastCharts({ dash, locale }: { dash: DashboardSnapshot; locale: Locale }) {
  const t = COPY[locale];
  const days = (dash.predictive.outlook_days || []).map((d) => ({
    d: d.date.slice(5),
    rain: d.precip_mm,
    et0: d.et0_mm,
    tmax: d.temp_max_c,
    tmin: d.temp_min_c,
    soil: d.soil_m3m3,
    prob: d.precip_prob_pct,
    wb: d.water_balance_mm,
  }));
  const ncHours = dash.science?.nowcast?.hours || [];
  const hourly = (
    ncHours.length
      ? ncHours.map((h) => ({ t: h.t.slice(11, 16), mm: h.mm, engine: h.engine }))
      : (dash.descriptive.series.precip_hourly || []).slice(0, 36).map((p) => ({
          t: p.t.slice(11, 16),
          mm: p.value,
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
              <CartesianGrid stroke="#d5dde6" vertical={false} />
              <XAxis dataKey="d" stroke="#6b7c93" fontSize={10} />
              <YAxis stroke="#6b7c93" fontSize={10} width={28} />
              <Tooltip contentStyle={tip} />
              <Legend />
              <Bar dataKey="rain" fill="#3a7ca5" radius={[6, 6, 0, 0]} />
              <Bar dataKey="et0" fill="#2a9d8f" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
      <section className="neo p-4">
        <h3 className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">°C</h3>
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={days}>
              <CartesianGrid stroke="#d5dde6" vertical={false} />
              <XAxis dataKey="d" stroke="#6b7c93" fontSize={10} />
              <YAxis stroke="#6b7c93" fontSize={10} width={28} />
              <Tooltip contentStyle={tip} />
              <Line type="monotone" dataKey="tmax" stroke="#c47b17" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="tmin" stroke="#3a7ca5" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
      <section className="neo p-4">
        <h3 className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.soil} + {t.chanceOfRain}</h3>
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={days}>
              <CartesianGrid stroke="#d5dde6" vertical={false} />
              <XAxis dataKey="d" stroke="#6b7c93" fontSize={10} />
              <YAxis stroke="#6b7c93" fontSize={10} width={28} />
              <Tooltip contentStyle={tip} />
              <Line type="monotone" dataKey="soil" stroke="#2a9d8f" strokeWidth={2} />
              <Line type="monotone" dataKey="prob" stroke="#3a7ca5" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
      <section className="neo p-4">
        <h3 className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.nextHours}</h3>
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={hourly}>
              <CartesianGrid stroke="#d5dde6" vertical={false} />
              <XAxis dataKey="t" stroke="#6b7c93" fontSize={9} interval={3} />
              <YAxis stroke="#6b7c93" fontSize={10} width={28} />
              <Tooltip contentStyle={tip} />
              <Bar dataKey="mm" fill="#3a7ca5" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}
