/** Pin-local public feeds fetched from the browser so Render’s IP is not used. */

export type ClientObsPack = {
  usgs_csv?: string | null;
  nasa_power?: Record<string, unknown> | null;
};

export async function fetchUsgsIndiaCsv(): Promise<string | null> {
  const end = new Date();
  const start = new Date();
  start.setUTCDate(start.getUTCDate() - 14);
  const q = new URLSearchParams({
    format: "csv",
    minlatitude: "6.5",
    maxlatitude: "37.5",
    minlongitude: "68",
    maxlongitude: "97.5",
    orderby: "time",
    limit: "20",
    starttime: start.toISOString().slice(0, 10),
  });
  try {
    const r = await fetch(`https://earthquake.usgs.gov/fdsnws/event/1/query?${q}`);
    if (!r.ok) return null;
    const text = await r.text();
    return text.includes("latitude") ? text : null;
  } catch {
    return null;
  }
}

export async function fetchNasaPowerDaily(lat: number, lon: number, days = 16): Promise<Record<string, unknown> | null> {
  const end = new Date();
  end.setUTCDate(end.getUTCDate() - 2);
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - days);
  const ymd = (d: Date) => d.toISOString().slice(0, 10).replace(/-/g, "");
  const q = new URLSearchParams({
    parameters: "PRECTOTCORR,T2M,RH2M,ALLSKY_SFC_SW_DWN",
    community: "AG",
    longitude: String(lon),
    latitude: String(lat),
    start: ymd(start),
    end: ymd(end),
    format: "JSON",
  });
  try {
    const r = await fetch(`https://power.larc.nasa.gov/api/temporal/daily/point?${q}`);
    if (!r.ok) return null;
    const data = await r.json();
    return data && typeof data === "object" ? data : null;
  } catch {
    return null;
  }
}

export async function fetchClientObs(
  lat: number,
  lon: number,
  disabled: string[] = []
): Promise<ClientObsPack> {
  const nasaOn = !disabled.includes("nasa-power");
  const [usgs_csv, nasa_power] = await Promise.all([
    fetchUsgsIndiaCsv(),
    nasaOn ? fetchNasaPowerDaily(lat, lon) : Promise.resolve(null),
  ]);
  return { usgs_csv, nasa_power: nasaOn ? nasa_power : null };
}
