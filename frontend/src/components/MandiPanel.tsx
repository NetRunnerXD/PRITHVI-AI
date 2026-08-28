"use client";

import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { COPY, type Locale } from "@/i18n/copy";
import type { DashboardSnapshot } from "@/types/dashboard";

export function MandiPanel({ dash, locale }: { dash: DashboardSnapshot; locale: Locale }) {
  const t = COPY[locale];
  const rows = dash.ogd?.mandi || [];
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"name" | "price">("price");
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const list = needle
      ? rows.filter((r) => `${r.commodity} ${r.variety || ""} ${r.market || ""}`.toLowerCase().includes(needle))
      : [...rows];
    list.sort((a, b) =>
      sort === "price" ? (b.modal_price || 0) - (a.modal_price || 0) : (a.commodity || "").localeCompare(b.commodity || "")
    );
    return list;
  }, [rows, q, sort]);
  if (!rows.length) return <p className="neo p-4 text-sm text-neo-muted">{t.noPrices}</p>;
  const chart = filtered.slice(0, 8).map((r) => ({
    name: `${r.commodity}`.slice(0, 12),
    price: r.modal_price,
  }));
  return (
    <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
      <section className="neo p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-bold">{t.mandi}</h3>
          <span className="chip">₹ / quintal</span>
        </div>
        <div className="mb-2 flex flex-wrap gap-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t.searchPrices} className="neo-in flex-1 px-3 py-2 text-sm" />
          <button className={`neo-btn text-xs ${sort === "price" ? "neo-btn-on" : ""}`} onClick={() => setSort("price")}>
            ₹
          </button>
          <button className={`neo-btn text-xs ${sort === "name" ? "neo-btn-on" : ""}`} onClick={() => setSort("name")}>
            A–Z
          </button>
        </div>
        <div className="max-h-80 overflow-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-neo-muted">
              <tr>
                <th className="py-1 font-medium">{t.searchPrices.replace("…", "")}</th>
                <th className="py-1 font-medium"></th>
                <th className="py-1 font-medium">₹</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r, i) => (
                <tr key={`${r.commodity}-${r.market}-${i}`} className="border-t border-neo-line">
                  <td className="py-1.5">
                    {r.commodity}
                    {r.variety ? <span className="text-neo-muted"> · {r.variety}</span> : null}
                  </td>
                  <td className="py-1.5 text-neo-muted">{r.market}</td>
                  <td className="py-1.5 font-mono font-bold text-neo-accent">{r.modal_price}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="neo p-4">
        <h3 className="mb-2 text-sm font-bold">{t.mandi}</h3>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chart} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid stroke="var(--line)" horizontal={false} />
              <XAxis type="number" stroke="var(--muted)" fontSize={10} />
              <YAxis type="category" dataKey="name" stroke="var(--muted)" fontSize={10} width={80} />
              <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--line)", borderRadius: 12, color: "var(--text)" }} />
              <Bar dataKey="price" fill="var(--accent)" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}
