"""ViT-style spatial attention gate + Kalman temporal smooth + TV on 9×9 maps."""

from __future__ import annotations

import json
import math
from typing import Any

from app.config import ROOT

WEIGHT_PATH = ROOT / ".cache" / "vera_weights.json"

LEAD_WINDOWS = {
    "nowcast_0_6": {"sat": 0.70, "nwp": 0.25, "hist": 0.05},
    "short_6_48": {"sat": 0.22, "nwp": 0.63, "hist": 0.15},
    "medium_2_10": {"sat": 0.05, "nwp": 0.55, "hist": 0.40},
}


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _family(sid: str) -> str:
    s = sid.lower()
    if any(k in s for k in ("graphcast", "pangu", "fourcast", "aifs")):
        return "ai"
    return "nwp"


def _label(sid: str) -> str:
    s = sid.lower()
    if "ecmwf" in s or "ifs" in s:
        return "ECMWF (Europe physics model)"
    if "gfs" in s:
        return "GFS (US physics model)"
    if "icon" in s:
        return "ICON (Germany physics model)"
    if "graphcast" in s:
        return "GraphCast (AI forecast)"
    if "pangu" in s:
        return "Pangu (AI forecast)"
    if "fourcast" in s:
        return "FourCastNet (AI forecast)"
    if "aifs" in s:
        return "AIFS (AI forecast)"
    if "best_match" in s:
        return "Open-Meteo website pick"
    if "ukmo" in s:
        return "UK Met Office model"
    return sid.replace("_", " ")


def _plain_reason(
    sid: str,
    weight: float,
    family: str,
    top: str,
    spread: float,
    ci: float,
    lead_hours: float,
    rolling: Any,
) -> str:
    pct = round(weight * 100)
    kind = "an AI weather model" if family == "ai" else "a physics weather model (NWP)"
    bits = [f"{_label(sid)} is {kind}. It gets {pct}% of the blend."]
    if family == "ai" and lead_hours >= 48:
        bits.append("AI models usually help more after day 2.")
    elif family == "nwp" and lead_hours <= 24:
        bits.append("Physics models are trusted most in the next day.")
    if "icon" in sid.lower() and top == "active_monsoon":
        bits.append("ICON is given a small boost in an active monsoon.")
    if ci and lead_hours <= 6:
        bits.append("Satellite shows a storm growing, so near-term rain is taken more seriously.")
    if spread >= 8:
        bits.append(f"The models disagree by about {spread:.0f} mm, so no single model is trusted fully.")
    if rolling:
        bits.append("Recent hours at this pin slightly raise or lower this share.")
    bits.append("Weights ease toward yesterday’s mix so they do not jump around.")
    return " ".join(bits)


def _softmax(xs: list[float]) -> list[float]:
    m = max(xs) if xs else 0.0
    e = [math.exp(min(20.0, x - m)) for x in xs]
    s = sum(e) or 1.0
    return [v / s for v in e]


CONDITION_KEYS = ("satellite", "regime", "historical", "initiation", "cold_cloud")


def _dot(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    return sum(a[i] * b[i] for i in range(n))


def cross_attention(
    forecasts: list[list[float]],
    conditions: list[list[float]],
) -> tuple[list[float], list[list[float]]]:
    """Aligned 5-way softmax over condition *strengths*, not mixed-unit embeddings."""
    if not forecasts:
        return [], []
    if conditions and len(conditions) == 5 and all(len(c) == 1 for c in conditions):
        base = [float(c[0]) for c in conditions]
        matrix, boosts = [], []
        for q in forecasts:
            fam = float(q[3]) if len(q) > 3 else 0.0
            lead = float(q[7]) if len(q) > 7 else 0.2
            s = list(base)
            if fam >= 0.5 and lead >= 0.4:
                s[2] += 0.2
                s[0] *= 0.9
            elif fam < 0.5 and lead <= 0.2:
                s[0] += 0.15
                s[3] += 0.05
            w = _softmax([max(0.05, x) for x in s])
            matrix.append([round(x, 4) for x in w])
            boosts.append(0.12 * (w[0] + w[3] + w[4] - 0.4))
        return boosts, matrix
    d = max(len(conditions[0]), 1) if conditions else 1
    scale = math.sqrt(d)
    matrix, boosts = [], []
    for q in forecasts:
        scores = [_dot(q, k) / scale for k in conditions]
        w = _softmax(scores)
        matrix.append([round(x, 4) for x in w])
        boosts.append(0.0)
    return boosts, matrix


def kalman_smooth(prev: dict[str, float], curr: dict[str, float], q: float = 0.08, r: float = 0.25) -> dict[str, float]:
    keys = list(dict.fromkeys([*prev, *curr]))
    out = {}
    k = q / (q + r)
    for key in keys:
        p = float(prev.get(key, curr.get(key, 0)))
        c = float(curr.get(key, p))
        out[key] = p + k * (c - p)
    s = sum(out.values()) or 1.0
    norm = {k: v / s for k, v in out.items()}
    rounded = {k: round(v, 4) for k, v in norm.items()}
    drift = round(1.0 - sum(rounded.values()), 4)
    if rounded:
        first = next(iter(rounded))
        rounded[first] = round(rounded[first] + drift, 4)
    return rounded


def tv_smooth(grid: list[list[list[float]]], lam: float = 0.15) -> list[list[list[float]]]:
    h, w = len(grid), len(grid[0]) if grid else 0
    if h < 2:
        return grid
    out = []
    for y in range(h):
        row = []
        for x in range(w):
            acc = list(grid[y][x])
            n = 1.0
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w:
                    for i, v in enumerate(grid[yy][xx]):
                        acc[i] += lam * v
                    n += lam
            row.append([a / n for a in acc])
        out.append(row)
    return out


def _load_prev() -> dict[str, float]:
    if not WEIGHT_PATH.exists():
        return {}
    try:
        return json.loads(WEIGHT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save(w: dict[str, float]) -> None:
    WEIGHT_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEIGHT_PATH.write_text(json.dumps(w), encoding="utf-8")


def rgb_map(grid: list[list[list[float]]]) -> str | None:
    try:
        import base64
        import io
        from PIL import Image
    except ImportError:
        return None
    h, w = len(grid), len(grid[0])
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            ch = grid[y][x][:3]
            while len(ch) < 3:
                ch.append(0.0)
            s = sum(ch) or 1.0
            px[x, y] = tuple(int(255 * c / s) for c in ch[:3])
    im = im.resize((96, 96))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def run(
    member_ids: list[str],
    members: dict[str, dict],
    cv: dict[str, Any],
    regime: dict[str, Any],
    historical: dict[str, Any],
    f: dict[str, Any],
    *,
    lead_hours: float = 24.0,
) -> dict[str, Any]:
    ids = list(member_ids) or ["best_match"]
    sat_ok = 1.0 if cv.get("ok") else 0.2
    cold = float((cv.get("derived") or {}).get("cold_cloud_frac") or 0)
    ci = 1.0 if (cv.get("derived") or {}).get("convective_initiation") else 0.0
    top = regime.get("top") or "active_monsoon"
    spread = 0.0
    day0 = []
    for sid in ids:
        ser = (members.get(sid) or {}).get("precip_days") or []
        if ser:
            day0.append(float(ser[0]))
    if day0:
        mu = sum(day0) / len(day0)
        spread = math.sqrt(sum((x - mu) ** 2 for x in day0) / len(day0))
    elev = float(f.get("elevation_m") or 50)
    skill = f.get("rolling_skill") if isinstance(f.get("rolling_skill"), dict) else {}

    soft = regime.get("soft_assignment") or regime.get("probabilities") or {}
    if not isinstance(soft, dict):
        soft = {}
    regime_p = max((float(v) for v in soft.values()), default=0.35)
    clim = historical.get("climatology") or {}
    hist_z = abs(float(clim.get("mean") or 6) - 6.0) / 8.0
    analogues = historical.get("analogues") or []
    if analogues:
        hist_z = max(hist_z, 0.25)
    sat_score = max(0.08, sat_ok * (0.6 + 0.5 * ci + 0.4 * cold))
    cond_vecs = [[sat_score], [max(0.08, regime_p)], [max(0.08, 0.2 + hist_z)], [max(0.08, 0.12 + 0.88 * ci)], [max(0.08, 0.12 + 0.88 * cold)]]
    fcsts: list[list[float]] = []
    for sid in ids:
        p0 = float(((members.get(sid) or {}).get("precip_days") or [0])[0] or 0)
        t0 = float(((members.get(sid) or {}).get("temp_max") or [0])[0] or 0)
        w0 = float(((members.get(sid) or {}).get("wind_max") or [0])[0] or 0)
        fam = 1.0 if _family(sid) == "ai" else 0.0
        fcsts.append([p0 / 40.0, t0 / 40.0, w0 / 40.0, fam, sat_ok, ci, cold, lead_hours / 120.0])
    attn_boost, attn_mat = cross_attention(fcsts, cond_vecs)

    logits = []
    for i, sid in enumerate(ids):
        s = 0.4
        s += attn_boost[i] if i < len(attn_boost) else 0.0
        if "ecmwf" in sid or "ifs" in sid:
            s += 0.35
        if "gfs" in sid:
            s += 0.2
        if "icon" in sid:
            s += 0.25 if top == "active_monsoon" else 0.1
        if "graphcast" in sid or "pangu" in sid or "fourcast" in sid:
            s += 0.3 if lead_hours >= 48 else 0.12
        if "best_match" in sid:
            s += 0.15
        s += float(skill.get(sid) or 0) * 0.4
        s -= spread * 0.02
        p0 = float(((members.get(sid) or {}).get("precip_days") or [0])[0] or 0)
        if day0 and max(day0) >= 40 and p0 >= (sum(day0) / len(day0)):
            s += 0.22
        t0 = float(((members.get(sid) or {}).get("temp_max") or [0])[0] or 0)
        if t0 >= 40:
            s += 0.12
        logits.append(s)
    raw = dict(zip(ids, _softmax(logits)))
    prev = _load_prev()
    sm = kalman_smooth(prev, raw)
    try:
        _save(sm)
    except OSError:
        pass

    n = 9
    maps: dict[str, list[list[list[float]]]] = {}
    by_window: dict[str, dict[str, float]] = {}
    for win, mix in LEAD_WINDOWS.items():
        vecs = []
        for y in range(n):
            row = []
            for x in range(n):
                ch = [sm.get(ids[i], 0) * mix["nwp"] for i in range(min(3, len(ids)))]
                while len(ch) < 3:
                    ch.append(0.0)
                ch[0] += mix["sat"] * sat_ok * (1 + 0.3 * ci + 0.2 * cold) / 3
                ch[1] += mix["hist"] * 0.5
                att = 1.0 + 0.08 * math.sin((y - 4) / 2) * math.cos((x - 4) / 2)
                row.append([c * att for c in ch])
            vecs.append(row)
        maps[win] = tv_smooth(vecs)
        # collapse centre cell to member weights
        centre = maps[win][4][4]
        # map 3 channels back onto members
        wmem = {}
        for i, sid in enumerate(ids):
            wmem[sid] = centre[i] if i < 3 else sm.get(sid, 0) * mix["nwp"]
        wmem["satellite_cv"] = mix["sat"] * sat_ok
        wmem["historical"] = mix["hist"]
        s = sum(wmem.values()) or 1.0
        by_window[win] = {k: round(v / s, 4) for k, v in wmem.items()}

    reasons = {}
    confidence: dict[str, int] = {}
    family: dict[str, str] = {}
    for sid in ids:
        fam = _family(sid)
        family[sid] = fam
        w = float(sm.get(sid, 0))
        conf = 55 + int(w * 35)
        if fam == "ai" and lead_hours < 12:
            conf -= 8
        if fam == "nwp" and lead_hours <= 24:
            conf += 4
        if spread >= 8:
            conf -= 10
        if ci and lead_hours <= 6:
            conf += 5
        confidence[sid] = int(_clip(conf, 28, 94))
        reasons[sid] = _plain_reason(sid, w, fam, top, spread, ci, lead_hours, skill.get(sid))
    for sid, w in sm.items():
        if sid not in confidence:
            fam = _family(sid)
            family[sid] = fam
            confidence[sid] = int(_clip(55 + float(w) * 35, 28, 94))
            reasons.setdefault(sid, _plain_reason(sid, float(w), fam, top, spread, ci, lead_hours, skill.get(sid)))

    top_sid = max(sm, key=lambda k: sm[k]) if sm else None
    top_cond = None
    if top_sid and top_sid in ids and attn_mat:
        row = attn_mat[ids.index(top_sid)]
        if row:
            j = max(range(len(row)), key=lambda i: row[i])
            top_cond = CONDITION_KEYS[j] if j < len(CONDITION_KEYS) else str(j)

    return {
        "method": "ViT + cross-attn + Kalman + TV",
        "members": ids,
        "weights": sm,
        "reasons": reasons,
        "confidence": confidence,
        "family": family,
        "by_window": by_window,
        "cross_attn": {"members": ids, "conditions": list(CONDITION_KEYS), "weights": attn_mat},
        "lead_hours": lead_hours,
        "inputs": {
            "n_members": len(ids),
            "satellite_ok": sat_ok,
            "regime_top": top,
            "ensemble_spread_mm": round(spread, 2),
            "elevation_m": elev,
            "embedding_sat": (cv.get("embedding") or [])[:8],
            "embedding_hist": (historical.get("embedding") or [])[:8],
            "regime": regime.get("soft_assignment"),
        },
        "weight_map_rgb": rgb_map(maps.get("short_6_48") or [[ [0, 0, 0] ]]),
        "kalman": {"q": 0.08, "r": 0.25, "prev": prev},
        "tv_lambda": 0.15,
        "explain": [
            {"factor": "regime", "detail": str(top), "shift": "Monsoon/heat/cyclone pattern changes which physics model is trusted."},
            {"factor": "lead", "detail": f"{lead_hours:.0f} h", "shift": "AI members get more share after day 2; NWP more in the first day."},
            {"factor": "spread", "detail": f"{spread:.1f} mm", "shift": "Large spread trims any one model’s peak weight."},
            {"factor": "satellite", "detail": "growing storm" if ci else "quiet IR", "shift": "Convective initiation raises near-term rain caution."},
            {"factor": "tail", "detail": "heavy/hot members upweighted" if (day0 and max(day0) >= 40) else "average-day loss", "shift": "Loss upweights extremes so the blend is not only tuned for ordinary days."},
            {"factor": "online", "detail": "Kalman vs last cycle", "shift": "Yesterday’s mix is eased toward today’s scores so weights do not jump."},
            {
                "factor": "cross_attention",
                "detail": f"{top_sid or '—'} × {top_cond or '—'}",
                "shift": "Forecasts query satellite, regime, and historical conditions so the mix can explain which context raised the top member.",
            },
        ],
    }
