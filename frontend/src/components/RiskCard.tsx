"use client";

import type { RiskCard as Risk } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";
import { levelOf, riskTitle } from "@/lib/plain";
import { Pill } from "./ui";

export function RiskCard({
  risk,
  locale,
  highlight = false,
}: {
  risk: Risk;
  locale: Locale;
  highlight?: boolean;
}) {
  const t = COPY[locale];
  const level = levelOf(risk.score_pct);
  const title = riskTitle(risk.id, locale, risk.label);
  const share = Math.max(risk.score_pct, 1);
  return (
    <article className={`neo p-4 ${highlight ? "ring-2 ring-neo-accent" : ""}`}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-bold">{title}</h3>
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm text-neo-muted">{risk.score_pct}%</span>
          <Pill level={level} locale={locale} />
        </div>
      </div>
      <p className="mt-3 text-[11px] font-bold uppercase tracking-wide text-neo-muted">{t.factors}</p>
      <ul className="mt-2 space-y-2">
        {risk.factors.map((f) => {
          const pct = Math.max(4, Math.round((f.contribution_pct / share) * 100));
          return (
            <li key={f.id}>
              <div className="mb-1 flex justify-between text-sm">
                <span>{f.label}</span>
                <span className="font-mono text-neo-accent">{f.contribution_pct}%</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full" style={{ background: "var(--line)" }}>
                <div
                  className="h-full rounded-full"
                  style={{ width: `${Math.min(100, pct)}%`, background: "var(--accent)" }}
                />
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-xs text-neo-muted">
        {t.howSure}: {risk.confidence_pct}% · {risk.horizon_hours} h
      </p>
    </article>
  );
}
