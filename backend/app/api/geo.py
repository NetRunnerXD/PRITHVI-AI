from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

import httpx

from app.http_urls import api_url
from app.services.location_svc import nearby, resolve_location, search_places

BHUVAN_WMS = "https://bhuvan-vec3.nrsc.gov.in/bhuvan/ows"
BHUVAN_WB = "gw_wfs:WB_LGEOM"
BHUVAN_IN = ",".join(
    [
        "gw_wfs:AN_LGEOM",
        "gw_wfs:AP_LGEOM",
        "gw_wfs:AS_LGEOM",
        "gw_wfs:BR_LGEOM",
        "gw_wfs:GA_LGEOM",
        "gw_wfs:JH_LGEOM",
        "gw_wfs:KA_LGEOM",
        "gw_wfs:KL_LGEOM",
        "gw_wfs:MH_LGEOM",
        "gw_wfs:MP_LGEOM",
        "gw_wfs:OR_LGEOM",
        "gw_wfs:PB_LGEOM",
        "gw_wfs:RJ_LGEOM",
        "gw_wfs:TN_LGEOM",
        "gw_wfs:TS_LGEOM",
        "gw_wfs:UK_LGEOM",
        "gw_wfs:UP_LGEOM",
        "gw_wfs:WB_LGEOM",
    ]
)

router = APIRouter()


@router.get("/geo/search")
async def geo_search(q: str = Query(min_length=1), limit: int = 8):
    found = await search_places(q, limit=limit)
    return {"results": [l.model_dump() for l in found]}


@router.get("/geo/reverse")
async def geo_reverse(lat: float, lon: float):
    return resolve_location(lat=lat, lon=lon).model_dump()


@router.get("/geo/nearby")
async def geo_nearby(lat: float, lon: float, limit: int = 8):
    return {"results": [l.model_dump() for l in nearby(lat, lon, limit=limit)]}


@router.get("/map/layers")
async def map_layers(request: Request):
    wms = api_url("/map/wms", request)
    return {
        "basemaps": [
            {
                "id": "positron",
                "label": "Light",
                "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                "attribution": "© OpenStreetMap © CARTO",
            },
            {
                "id": "streets",
                "label": "Streets",
                "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                "attribution": "© OpenStreetMap",
            },
            {
                "id": "satellite",
                "label": "Satellite",
                "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                "attribution": "Tiles © Esri",
            },
            {
                "id": "terrain",
                "label": "Terrain",
                "url": "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
                "attribution": "© OpenTopoMap",
            },
        ],
        "overlays": [
            {
                "id": "gibs_truecolor",
                "label": "NASA GIBS True Color",
                "type": "wms",
                "url": "https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi",
                "layers": "MODIS_Terra_CorrectedReflectance_TrueColor",
            },
            {
                "id": "bhuvan_geomorph",
                "label": "Bhuvan / NRSC geomorphology (West Bengal)",
                "type": "wms",
                "url": wms,
                "path": "/api/map/wms",
                "layers": BHUVAN_WB,
                "href": "https://bhuvan.nrsc.gov.in/ngmaps/thematic?theme1=geomorphology.wb_gm50k_0506_new&tlp=vector&state=WEST+BENGAL&district=ALL",
            },
            {
                "id": "bhuvan_geomorph_in",
                "label": "Bhuvan / NRSC litho-geomorphology (India states)",
                "type": "wms",
                "url": wms,
                "path": "/api/map/wms",
                "layers": BHUVAN_IN,
                "href": "https://www.nrsc.gov.in/nrscnew/Dataproducts_Thematic_overview.php",
            },
        ],
    }


@router.api_route("/map/wms", methods=["GET", "HEAD"])
async def bhuvan_wms_proxy(request: Request):
    """Browser-safe proxy. Bhuvan TLS/CORS often blocks direct Leaflet WMS."""
    params = dict(request.query_params)
    layers = params.get("layers") or BHUVAN_WB
    if layers in {"geomorphology", "geomorphology.wb_gm50k_0506_new"}:
        params["layers"] = BHUVAN_WB if "wb" in layers else BHUVAN_IN
    if layers == "bhuvan_geomorph":
        params["layers"] = BHUVAN_WB
    if layers == "bhuvan_geomorph_in":
        params["layers"] = BHUVAN_IN
    params.setdefault("service", "WMS")
    params.setdefault("request", "GetMap")
    params.setdefault("version", "1.1.1")
    params.setdefault("format", "image/png")
    params.setdefault("transparent", "true")
    if "srs" not in {k.lower() for k in params} and "crs" not in {k.lower() for k in params}:
        params["srs"] = "EPSG:3857"
    try:
        async with httpx.AsyncClient(timeout=25.0, verify=False, follow_redirects=True) as client:
            r = await client.get(BHUVAN_WMS, params=params)
        ctype = r.headers.get("content-type") or "image/png"
        return Response(content=r.content, media_type=ctype, status_code=r.status_code)
    except Exception:
        return Response(status_code=502, content=b"bhuvan proxy failed")
