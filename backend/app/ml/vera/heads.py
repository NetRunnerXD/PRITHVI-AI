"""RCEPF 12-parameter heads wired from snapshot + EQMN."""

from __future__ import annotations

from typing import Any

from app.ml.vera.fusion import blend_quantiles, member_quantiles, p_from_quantiles


def _n(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)) and v == v:
        return float(v)
    if isinstance(v, list):
        for x in v:
            if x is not None:
                try:
                    return float(x)
                except (TypeError, ValueError):
                    continue
    if isinstance(v, dict):
        for k in ("value", "q50", "pm25", "aqi", "wave_height", "n_strokes", "p"):
            if v.get(k) is not None:
                try:
                    return float(v[k])
                except (TypeError, ValueError):
                    continue
    return None


def _series_now(f: dict[str, Any], key: str) -> float | None:
    ser = f.get(key)
    if not isinstance(ser, list) or not ser:
        return _n(f.get(key.replace("hourly_", "")))
    i = int(f.get("hourly_now_i") or 0)
    i = max(0, min(i, len(ser) - 1))
    try:
        return float(ser[i]) if ser[i] is not None else None
    except (TypeError, ValueError):
        return None


def _head(status: str, q50: float | None, source: str, **extra: Any) -> dict[str, Any]:
    out = {"status": status, "q50": None if q50 is None else round(float(q50), 3), "source": source}
    out.update(extra)
    return out


def _eqmn(members: dict, weights: dict, key: str, thresh: float | None = None) -> dict[str, Any]:
    mus, ws = [], []
    for sid, pack in members.items():
        ser = pack.get(key) or []
        if ser and sid in weights:
            mus.append(float(ser[0]))
            ws.append(float(weights[sid]))
    if not mus:
        return _head("not_wired", None, f"no member {key}")
    sigs = [max(1.0, abs(m) * 0.15 + 0.6) for m in mus]
    blended = blend_quantiles([member_quantiles(m, s) for m, s in zip(mus, sigs)], ws)
    out = _head("wired", blended[0.5], key, method="EQMN", q10=blended[0.1], q90=blended[0.9], q95=blended[0.95], q99=blended[0.99])
    if thresh is not None:
        out["p_exceed"] = p_from_quantiles(blended, thresh)
        out["threshold"] = thresh
    return out


def _blend_now(members: dict, weights: dict, key: str) -> dict[str, Any] | None:
    mus, ws = [], []
    for sid, pack in (members or {}).items():
        if sid not in weights:
            continue
        ser = pack.get(key) or []
        if not ser:
            continue
        v = ser[0]
        if isinstance(v, (int, float)):
            mus.append(float(v))
            ws.append(float(weights[sid]))
    if not mus:
        return None
    return _eqmn({sid: {key: [m]} for sid, m in zip([f"m{i}" for i in range(len(mus))], mus)}, {f"m{i}": w for i, w in enumerate(ws)}, key)


def _fog(f: dict[str, Any], members: dict | None = None, weights: dict | None = None) -> dict[str, Any]:
    vis = _series_now(f, "hourly_vis")
    blended = _eqmn(members or {}, weights or {}, "hourly_vis") if members else None
    if vis is None and blended and blended.get("q50") is not None:
        vis = blended["q50"]
    rh = _series_now(f, "hourly_rh")
    dew = _series_now(f, "hourly_dew")
    temp = _series_now(f, "hourly_temp")
    wind = _series_now(f, "hourly_wind")
    code = _series_now(f, "hourly_weather_code")
    is_day = _series_now(f, "hourly_is_day")
    dep = (temp - dew) if temp is not None and dew is not None else None
    p = 0.05
    if vis is not None and vis < 1000:
        p += 0.45
    if vis is not None and vis < 200:
        p += 0.25
    if rh is not None and rh >= 90:
        p += 0.15
    if dep is not None and dep <= 2.0:
        p += 0.2
    if wind is not None and wind < 8:
        p += 0.1
    if code is not None and 45 <= code <= 49:
        p += 0.35
    if is_day == 0:
        p += 0.08
    p = min(0.98, p)
    status = "wired" if vis is not None or code is not None or dep is not None else "not_wired"
    return _head(
        status,
        vis,
        "visibility + dewpoint depression + WMO 45–49" + (" + member EQMN vis" if blended and blended.get("q50") is not None else ""),
        p_fog=round(p, 3),
        dewpoint_depression_c=None if dep is None else round(dep, 2),
        unit="m visibility",
        night=is_day == 0,
        method="EQMN" if blended and blended.get("q50") is not None else "diagnostic",
        q50_blend=None if not blended else blended.get("q50"),
    )


def _tc(f: dict[str, Any]) -> dict[str, Any]:
    best = None
    for g in f.get("gdacs") or []:
        if not isinstance(g, dict):
            continue
        et = str(g.get("event_type") or g.get("eventtype") or "").upper()
        if et not in {"TC", "CYCLONE"} and "cyclone" not in str(g.get("name") or "").lower():
            continue
        best = g
        break
    if not best:
        return _head("not_wired", None, "GDACS TC", need="active tropical cyclone in India box")
    mag = _n(best.get("severity") or best.get("alertlevel") or best.get("episodealertlevel"))
    return _head(
        "wired",
        mag,
        "GDACS tropical cyclone",
        name=best.get("name") or best.get("eventname"),
        lat=best.get("lat") or best.get("latitude"),
        lon=best.get("lon") or best.get("longitude"),
        event_id=best.get("id") or best.get("eventid"),
    )


def _lightning(f: dict[str, Any]) -> dict[str, Any]:
    cape = _series_now(f, "hourly_cape")
    n = _n(f.get("lightning"))
    th = f.get("thunder") if isinstance(f.get("thunder"), dict) else {}
    code = _series_now(f, "hourly_weather_code")
    p = 0.02
    if cape is not None:
        p = min(0.95, max(0.02, cape / 2500.0))
    if n and n > 0:
        p = min(0.98, p + 0.25)
    if th.get("thunder") or (code is not None and code >= 95):
        p = min(0.98, p + 0.2)
    status = "wired" if cape is not None or n is not None or code is not None else "not_wired"
    return _head(
        status,
        n if n is not None else cape,
        "CAPE + OM thunder codes + strokes (not Damini-2.0)",
        p_lightning=round(p, 3),
        cape_jkg=cape,
        n_strokes=n,
        thunder=bool(th.get("thunder")),
    )


def _aqi(f: dict[str, Any]) -> dict[str, Any]:
    cpcb = _n(f.get("naqi"))
    pm_cpcb = None
    pols = f.get("naqi_pollutants") if isinstance(f.get("naqi_pollutants"), dict) else {}
    if pols:
        pm_cpcb = _n(pols.get("pm2.5") or pols.get("PM2.5") or pols.get("pm25"))
    cams = _series_now(f, "hourly_us_aqi") or _n(f.get("om_us_aqi"))
    pm = None
    pm_s = f.get("hourly_pm10")
    if isinstance(pm_s, list) and pm_s:
        i = int(f.get("hourly_aqi_now_i") or 0)
        i = max(0, min(i, len(pm_s) - 1))
        pm = _n(pm_s[i])
    waqi = f.get("waqi") if isinstance(f.get("waqi"), dict) else {}
    if cams is None:
        cams = _n(waqi.get("aqi") if isinstance(waqi, dict) else None)
    if cpcb is not None:
        return _head("wired", cpcb, "CPCB NAQI (data.gov.in)", method="station", pm25=pm_cpcb, cams_us_aqi=cams, category=f.get("naqi_category"))
    if cams is None:
        return _head("not_wired", None, "CPCB / CAMS", need="DATA_GOV_IN_API_KEY or Open-Meteo air-quality")
    return _head("wired", cams, "Open-Meteo CAMS US AQI (forecast, not SAFAR)", pm10=pm, method="CAMS")


def _waves(f: dict[str, Any]) -> dict[str, Any]:
    hs = _n(f.get("wave_height_m"))
    if hs is None:
        hs = _series_now(f, "hourly_wave") if isinstance(f.get("hourly_wave"), list) else None
        if hs is None and isinstance(f.get("hourly_wave"), list) and f["hourly_wave"]:
            i = int(f.get("hourly_wave_now_i") or 0)
            i = max(0, min(i, len(f["hourly_wave"]) - 1))
            hs = _n(f["hourly_wave"][i])
    if hs is None:
        return _head("not_wired", None, "OM marine / INCOIS-class Hs", need="coastal pin")
    return _head("wired", hs, "Open-Meteo marine wave_height (INCOIS-class Hs)", inland=bool(f.get("marine_inland")), unit="m")


def _hub(f: dict[str, Any], members: dict | None = None, weights: dict | None = None) -> dict[str, Any]:
    w120 = _series_now(f, "hourly_wind_120")
    w80 = _series_now(f, "hourly_wind_80")
    w180 = _series_now(f, "hourly_wind_180")
    w10 = _series_now(f, "hourly_wind")
    zref, wref = None, None
    if w120 is not None:
        zref, wref = 120.0, w120
    elif w80 is not None:
        zref, wref = 80.0, w80
    elif w180 is not None:
        zref, wref = 180.0, w180
    elif w10 is not None:
        zref, wref = 10.0, w10
    else:
        b = _eqmn(members or {}, weights or {}, "wind_max")
        if b.get("q50") is not None:
            zref, wref = 10.0, float(b["q50"])
    if wref is None:
        return _head("not_wired", None, "hub-height wind")
    hub = wref * (100.0 / zref) ** 0.14
    return _head("wired" if zref > 10 else "derived", hub, f"log-law from {int(zref)} m → 100 m α=0.14", unit="km/h", z_m=100, z_src=zref, method="EQMN+log-law")


def _solar(f: dict[str, Any], members: dict | None = None, weights: dict | None = None) -> dict[str, Any]:
    sw = _series_now(f, "hourly_shortwave")
    dni = _series_now(f, "hourly_dni")
    b = _eqmn(members or {}, weights or {}, "shortwave_sum")
    if sw is None:
        sw = _n(f.get("shortwave_sum"))
    if sw is None and b.get("q50") is not None:
        sw = b["q50"]
    if sw is None:
        return _head("not_wired", None, "shortwave", need="Open-Meteo shortwave_radiation")
    return _head(
        "wired",
        sw,
        "EQMN member shortwave + DNI",
        unit="W/m²",
        daily_sum=f.get("shortwave_sum"),
        dni=dni,
        method="EQMN" if b.get("q50") is not None else "OM",
        q50_blend=b.get("q50"),
    )


def _gusts(f: dict[str, Any], members: dict, weights: dict) -> dict[str, Any]:
    g = _eqmn(members, weights, "gust_max", 80.0)
    if g.get("q50") is not None:
        return {**g, "unit": "km/h", "source": "member EQMN wind_gusts_10m_max"}
    now = _series_now(f, "hourly_gust")
    if now is not None:
        return _head("wired", now, "Open-Meteo wind_gusts_10m", unit="km/h")
    return _eqmn(members, weights, "wind_max", 80.0)


def _diurnal(f: dict[str, Any], temp: dict[str, Any]) -> dict[str, Any]:
    ht = [float(x) for x in (f.get("hourly_temp") or [])[:24] if x is not None]
    out = dict(temp)
    if len(ht) >= 8:
        out["diurnal_amp_c"] = round(max(ht) - min(ht), 2)
        out["tmin_c"] = round(min(ht), 2)
        out["tmax_c"] = round(max(ht), 2)
        out["source"] = (out.get("source") or "temp") + " + hourly diurnal"
    return out


def run(
    f: dict[str, Any],
    members: dict[str, dict],
    weights: dict[str, float],
    fusion: dict[str, Any],
    extremes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rain = _head("wired", fusion.get("q50"), "fusion EQMN daily precip", method="EQMN", q95=fusion.get("q95"), q99=fusion.get("q99"))
    temp = fusion.get("temp") or _eqmn(members, weights, "temp_max", 40.0)
    if isinstance(temp, dict):
        temp = {**temp, "status": "wired" if temp.get("q50") is not None else "not_wired"}
        temp = _diurnal(f, temp)
    wind = fusion.get("wind") or _eqmn(members, weights, "wind_max", 60.0)
    if isinstance(wind, dict):
        wind = {**wind, "status": "wired" if wind.get("q50") is not None else "not_wired"}
    heat = _head(
        "wired",
        (extremes or {}).get("heat_wave", {}).get("p") if extremes else None,
        "IMD heat-wave departure",
        level=(extremes or {}).get("heat_wave", {}).get("level"),
    )
    order = [
        ("rainfall", rain),
        ("temperature", temp),
        ("heat_wave", heat),
        ("wind", wind),
        ("gusts", _gusts(f, members, weights)),
        ("tropical_cyclone", _tc(f)),
        ("lightning", _lightning(f)),
        ("fog", _fog(f, members, weights)),
        ("waves", _waves(f)),
        ("aqi", _aqi(f)),
        ("hub_wind", _hub(f, members, weights)),
        ("solar", _solar(f, members, weights)),
    ]
    return {
        "heads": [{**v, "id": k} for k, v in order],
        "n_wired": sum(1 for _, v in order if v.get("status") in {"wired", "derived"}),
        "n_total": 12,
    }
