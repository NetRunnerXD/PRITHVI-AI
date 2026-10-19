/** Static 0.25° India terrain (Open-Meteo Elevation API / Copernicus GLO-90), ~18 KB gzip.
 * Loaded lazily, only when the temperature layer is shown. Used to lapse-correct the
 * coarse model grid to the real ground height of each painted pixel. */
export type Dem = { south: number; west: number; step: number; ny: number; nx: number; z: number[] };

let demP: Promise<Dem | null> | null = null;

export function loadDem(): Promise<Dem | null> {
  if (!demP) {
    demP = fetch("/india_dem_025.json")
      .then((r) => (r.ok ? (r.json() as Promise<Dem>) : null))
      .then((d) => (d && Array.isArray(d.z) && d.z.length === d.nx * d.ny ? d : null))
      .catch(() => {
        demP = null;
        return null;
      });
  }
  return demP;
}

export function demAt(d: Dem, lat: number, lon: number): number | null {
  const fi = (lat - d.south) / d.step;
  const fj = (lon - d.west) / d.step;
  if (fi < 0 || fj < 0 || fi > d.ny - 1 || fj > d.nx - 1) return null;
  const i0 = Math.min(d.ny - 2, Math.floor(fi));
  const j0 = Math.min(d.nx - 2, Math.floor(fj));
  const ti = fi - i0;
  const tj = fj - j0;
  const z = d.z;
  const n = d.nx;
  const a = z[i0 * n + j0] * (1 - tj) + z[i0 * n + j0 + 1] * tj;
  const b = z[(i0 + 1) * n + j0] * (1 - tj) + z[(i0 + 1) * n + j0 + 1] * tj;
  return a * (1 - ti) + b * ti;
}

/** Standard-atmosphere lapse rate, K per metre. */
export const LAPSE_K_PER_M = 0.0065;
