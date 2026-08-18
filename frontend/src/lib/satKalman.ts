/** Client twin of backend sat_kalman.predict_rate (decay_bias_v1). */

export type SatFormula = {
  kind?: string;
  eps?: number;
  adv_mm_h?: number;
  x?: number[];
  last_obs_t?: string | null;
  last_obs_mm_h?: number | null;
};

export type SatKnot = { t: string; mm?: number; mm_h?: number };

export type SatHistoryRow = {
  t: string;
  pred?: number | null;
  held?: number | null;
  obs?: number | null;
  y?: number | null;
  after?: number | null;
  scene?: boolean;
};

export type SatHistChart = {
  label: string;
  ms: number;
  pred: number | null;
  held: number | null;
  obs: number | null;
  after: number | null;
  y: number | null;
};

export type SatPoint = {
  t: string;
  ms: number;
  mmh: number | null;
  obs: number | null;
  future: boolean;
};

export function parseIso(t?: string | null): Date | null {
  if (!t) return null;
  const d = new Date(t.includes("T") ? t : `${t}+05:30`);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function predictRate(form: SatFormula, dtS: number): number {
  const x = form.x || [Math.log(0.05), 0, 0.45];
  const eps = form.eps ?? 0.05;
  const adv = form.adv_mm_h ?? 0;
  const lam = Math.min(2.5, Math.max(0.05, Number(x[2] ?? 0.45)));
  const hours = Math.max(0, dtS) / 3600;
  const r0 = Math.max(0, Math.exp(Number(x[0] ?? Math.log(eps))) - eps);
  return Math.max(0, r0 * Math.exp(-lam * hours) + Number(x[1] ?? 0) + 0.15 * adv);
}

export function rateAt(form: SatFormula, at: Date): number | null {
  const last = parseIso(form.last_obs_t);
  if (!last) return predictRate(form, 0);
  const dtS = (at.getTime() - last.getTime()) / 1000;
  if (dtS < 0) return null;
  return predictRate(form, dtS);
}

export function buildHistoryChart(series: SatHistoryRow[] = []): SatHistChart[] {
  return series.map((row) => {
    const dt = parseIso(row.t);
    return {
      label: dt
        ? dt.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit" })
        : row.t,
      ms: dt?.getTime() || 0,
      pred: row.pred == null ? null : Number(row.pred),
      held: row.held == null ? null : Number(row.held),
      obs: row.obs == null ? null : Number(row.obs),
      after: row.after == null ? null : Number(row.after),
      y: row.y == null ? null : Number(row.y),
    };
  });
}

function tickLabel(d: Date, strideS: number) {
  return d.toLocaleTimeString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    second: strideS <= 1 ? "2-digit" : undefined,
  });
}

export type ServerPoint = { t: string; mm_h?: number; pred?: number | null; mm?: number };

export function interpSeries(rows: ServerPoint[] | undefined, at: Date): number | null {
  if (!rows?.length) return null;
  const pts: { ms: number; v: number }[] = [];
  for (const r of rows) {
    const dt = parseIso(r.t);
    const v = r.mm_h ?? r.pred;
    if (!dt || v == null) continue;
    pts.push({ ms: dt.getTime(), v: Number(v) });
  }
  if (!pts.length) return null;
  const t = at.getTime();
  if (t <= pts[0].ms) return pts[0].v;
  if (t >= pts[pts.length - 1].ms) return pts[pts.length - 1].v;
  for (let i = 0; i < pts.length - 1; i++) {
    if (t >= pts[i].ms && t <= pts[i + 1].ms) {
      const span = Math.max(1, pts[i + 1].ms - pts[i].ms);
      const u = (t - pts[i].ms) / span;
      return pts[i].v * (1 - u) + pts[i + 1].v * u;
    }
  }
  return pts[pts.length - 1].v;
}

export function chartFromPredSeries(
  rows: ServerPoint[] | undefined,
  strideS: number,
  obs: SatKnot[] = []
): SatPoint[] {
  if (!rows?.length) return [];
  const obsByMs = new Map<number, number>();
  for (const k of obs) {
    const dt = parseIso(k.t);
    if (!dt) continue;
    obsByMs.set(dt.getTime(), Number(k.mm_h ?? k.mm ?? 0));
  }
  return rows.map((r) => {
    const dt = parseIso(r.t);
    const ms = dt?.getTime() || 0;
    let obsVal: number | null = null;
    if (dt) {
      const hit = obsByMs.get(ms);
      if (hit != null) obsVal = hit;
      else {
        obsByMs.forEach((v, oms) => {
          if (obsVal == null && Math.abs(oms - ms) < 45_000) obsVal = v;
        });
      }
    }
    return {
      t: dt ? tickLabel(dt, strideS) : r.t,
      ms,
      mmh: r.mm_h == null ? null : Number(r.mm_h),
      obs: obsVal,
      future: false,
    };
  });
}

export function buildLiveChart(
  form: SatFormula,
  now: Date,
  strideS: number,
  obs: SatKnot[] = []
): SatPoint[] {
  const stride = strideS <= 1 ? 1 : 60;
  const back = stride <= 1 ? 180 : 3600;
  const fwd = stride <= 1 ? 180 : 7200;
  const last = parseIso(form.last_obs_t);
  const startMs = now.getTime() - back * 1000;
  const endMs = now.getTime() + fwd * 1000;
  const originMs = last ? Math.max(last.getTime(), startMs) : startMs;
  const obsByMs = new Map<number, number>();
  for (const k of obs) {
    const dt = parseIso(k.t);
    if (!dt) continue;
    obsByMs.set(dt.getTime(), Number(k.mm_h ?? k.mm ?? 0));
  }
  const rows: SatPoint[] = [];
  for (let ms = originMs; ms <= endMs; ms += stride * 1000) {
    const d = new Date(ms);
    const mmh = rateAt(form, d);
    let obsVal: number | null = null;
    if (stride <= 1) {
      const hit = obsByMs.get(ms);
      if (hit != null) obsVal = hit;
    } else {
      obsByMs.forEach((v, oms) => {
        if (obsVal == null && Math.abs(oms - ms) < 30_000) obsVal = v;
      });
    }
    rows.push({
      t: tickLabel(d, stride),
      ms,
      mmh: mmh == null ? null : Number(mmh.toFixed(3)),
      obs: obsVal,
      future: ms > now.getTime(),
    });
  }
  return rows;
}
