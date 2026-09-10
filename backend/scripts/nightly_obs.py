"""Nightly observation ingestion: IMERG Late + MOSDAC HEM + VERA skill."""

from __future__ import annotations

import asyncio

from app.config import get_settings
from app.ml.vera.mlops import registry, update_skill
from app.ml.vera import verify as vera_verify
from app.providers import gpm_imerg, mosdac


async def ingest() -> dict:
    s = get_settings()
    lat, lon = float(s.default_lat), float(s.default_lon)
    pin = f"{s.default_district}:{s.default_place}"
    imerg = await gpm_imerg.fetch_late_pin(lat, lon)
    hem = None
    mos = {"ok": False, "status": "skip"}
    if mosdac.credentials_present():
        mos = await mosdac.download_product("3DIMG_L2B_HEM")
        hem = mosdac.hem_knot(lat, lon)
    mm = None
    src = None
    if hem and hem.get("mm_h") is not None:
        mm = float(hem["mm_h"])
        src = "insat-hem"
    elif imerg.get("mm_h") is not None:
        mm = float(imerg["mm_h"])
        src = str(imerg.get("source") or "gpm-imerg")
    n = 0
    if mm is not None:
        from datetime import datetime, timezone

        t = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0).isoformat()
        n = vera_verify.backfill_obs(pin, [t], [mm], source=src or "independent")
    update_skill(["ecmwf", "gfs", "icon", "graphcast"], "active_monsoon")
    return {
        "imerg": {k: imerg.get(k) for k in ("ok", "mm_h", "source")},
        "mosdac": {k: mos.get(k) for k in ("ok", "status", "path") if k in mos},
        "hem": hem,
        "obs_attached": n,
        "mlops": registry("ViT+Kalman+TV"),
        "scores": vera_verify.scores(pin),
    }


def main() -> dict:
    return asyncio.run(ingest())


if __name__ == "__main__":
    print(main())
