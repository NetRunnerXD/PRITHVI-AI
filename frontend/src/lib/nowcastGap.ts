/** Client-side 1-min gap so the Nowcasting tab works even if /nowcast/live 404s. */

export type GapPoint = { t: string; mm: number; mm_h: number; p_wet: number };

export function gapFromHours(
  hours: { t: string; mm?: number; p_wet?: number }[] | undefined,
  dtS = 60
): GapPoint[] {
  if (!hours?.length) return [];
  const knots = hours
    .map((h) => ({ t: h.t, mm: Math.max(0, Number(h.mm) || 0), p_wet: Number(h.p_wet) || 0.12, dt: Date.parse(h.t) }))
    .filter((k) => Number.isFinite(k.dt));
  if (!knots.length) return [];
  const steps = Math.max(1, Math.round(3600 / dtS));
  const out: GapPoint[] = [];
  for (let i = 0; i < knots.length; i++) {
    const cur = knots[i];
    const nxt = knots[i + 1]?.mm ?? cur.mm * 0.55;
    const raw: number[] = [];
    for (let s = 0; s < steps; s++) {
      const t = s / steps;
      raw.push(Math.max(0, cur.mm * (1 - t) + nxt * t));
    }
    const tot = raw.reduce((a, b) => a + b, 0);
    const scaled = tot <= 1e-9 ? raw.map(() => cur.mm / steps) : raw.map((v) => (v * cur.mm) / tot);
    for (let s = 0; s < steps; s++) {
      const ms = cur.dt + s * dtS * 1000;
      out.push({
        t: new Date(ms).toISOString(),
        mm: scaled[s],
        mm_h: scaled[s] * (3600 / dtS),
        p_wet: cur.p_wet,
      });
    }
  }
  return out;
}
