# Rituchakra API — frontend and app implementation

JSON HTTP API. No web assets. The Next.js dashboard (`frontend/`) and Expo app (`mobile/`) are clients of the same origin.

Live contract: `GET /openapi.json` and Swagger at `/docs`. This file is the implementation guide (boot order, screens, chat, location).

Default origin (local): `http://127.0.0.1:8000`  
Published (when Render is connected): `https://<service>.onrender.com`

---

## 1. Base URL and surfaces

Four prefixes run the **same handlers**. Do not mix prefixes in one client.

| Prefix | Use |
|---|---|
| `/api` | Canonical. Next.js, pytest, `clients/js` default. **Use this.** |
| `/v1` | Same JSON, versioned public alias |
| `/web/v1` | Optional for a second website |
| `/app/v1` | Optional for Expo / React Native |

Examples (equivalent):

```
GET {origin}/api/health
GET {origin}/app/v1/health
GET {origin}/web/v1/dashboard?place=Haldia
```

Join rule used by `clients/js` and the Next app: if the path does not already start with `/api`, prepend `/api`.

| Client | Env |
|---|---|
| Next.js | `NEXT_PUBLIC_API_BASE` (empty = same-origin `/api`) |
| Expo | `EXPO_PUBLIC_API_BASE` (HTTPS in production; Android blocks cleartext) |
| TypeScript package | `createClient({ baseUrl })` |

---

## 2. Rules that apply to every client

- **India only.** Search and reverse-geocode reject points outside India (`400`).
- **Do not invent millimetres, AQI, rupees, or risk %.** Display numbers from JSON. The Advisor LLM only narrates.
- **Location query** on GET routes: `district`, `place`, `lat`, `lon`. Omit all of them → default **Haldia, Purba Medinipur** (`22.0667, 88.0698`).
- **Locale:** `locale=en|hi|bn` where supported (`/dashboard`, `POST /brief`). Chat uses `locale_hint` / `output_locale` in the body.
- **CORS** is enabled. Optional request header `X-Rituchakra-Client: web|app|local`. Response headers: `X-API-Version`, `X-Client-Surface`.
- **One replica / in-process cache.** Snapshot routes can take several seconds on a cold host.
- **Auth:** none. Public JSON.

---

## 3. Boot sequence (web and app)

Do this once at launch, then keep `Location` in client state.

```
1. GET /api/ready          → liveness (cheap)
2. GET /api/bootstrap      → default_location, locales, tabs, capabilities
3. GET /api/geo/search?q=  → user picked a place  (or reverse from GPS)
4. GET /api/alerts         → first paint (warnings + live hazards)
5. GET /api/dashboard      → full snapshot for the rest of the screens
6. Poll GET /api/nowcast/live  every ~60s while Nowcast is visible
7. POST /api/chat          when Advisor is used
```

GPS: `GET /api/geo/reverse?lat=&lon=` then store the returned `Location`. If `400`, the pin is outside India — keep the last India location.

---

## 4. Location object

Returned by search, reverse, nearby, and every snapshot route.

```json
{
  "id": "in-wb-purba-medinipur-haldia",
  "label": "Haldia, West Bengal",
  "country": "IN",
  "state": "West Bengal",
  "district": "Purba Medinipur",
  "lat": 22.0667,
  "lon": 88.0698,
  "timezone": "Asia/Kolkata",
  "place_kind": "place",
  "place_name": "Haldia"
}
```

Pass on later GETs:

```
?district=Purba%20Medinipur&place=Haldia&lat=22.0667&lon=88.0698
```

---

## 5. Screen → route map

Use **slice** routes on phones (smaller JSON). Use `/dashboard` on web overview if you want one round-trip.

| Screen | Route | Notes |
|---|---|---|
| Splash / settings | `GET /api/bootstrap` | tabs, locales, `capabilities` |
| Search | `GET /api/geo/search?q=` | `results[]` |
| GPS | `GET /api/geo/reverse` | `400` outside India |
| Nearby chips | `GET /api/geo/nearby` | |
| Overview | `GET /api/dashboard` or `POST /api/brief` | brief is SMS-sized |
| Nowcast | `GET /api/nowcast/live` | poll; aliases `/nowcast-live`, `/live-nowcast` |
| Nowcast Kalman | `GET /api/nowcast/sat?stride=60` | `stride` 1 or 60 |
| Storm map | `GET /api/nowcast/storm-map?state=` | `state=India` or a state name |
| Alerts | `GET /api/alerts` | warnings, quakes, tsunami, air, flood |
| Forecast | `GET /api/forecast` | Open-Meteo / descriptive |
| Dual 7-day | `GET /api/predictions?source=both` | `ours` \| `trusted` \| `both` |
| Outlook dates | `GET /api/outlook` | irrigate / flood-watch dates |
| Risks | `GET /api/risks` | `score_pct`, `factors` |
| Science / XAI | `GET /api/science` | large |
| Market / mandi | `GET /api/market` | `ogd` |
| Map | `GET /api/map/layers` | Leaflet/RN map tiles + WMS path |
| Advisor | `POST /api/chat` | JSON on app; SSE on web |
| Compare two places | `GET /api/compare?a=&b=` | |
| District scan | `GET /api/scan?state=&metric=flood` | |

---

## 6. Endpoints

All paths below are under `{origin}` plus prefix `/api` (or `/app/v1`, `/web/v1`).

### Meta

| Method | Path | Response |
|---|---|---|
| GET | `/` | Service card |
| GET | `/api` | Service card + `routes[]` |
| GET | `/api/health` | `ok`, `default_location`, `ollama`, `keys`, `surfaces` |
| HEAD | `/api/health` | `200` empty |
| GET | `/api/ready` | `{ "ok": true, "service": "rituchakra-api", "version" }` |
| GET | `/api/bootstrap` | Boot pack (see below) |
| GET | `/docs` | Swagger UI |
| GET | `/openapi.json` | OpenAPI 3 |

`GET /api/bootstrap` (first request):

```json
{
  "ok": true,
  "version": "0.4.0",
  "default_location": {},
  "locales": ["en", "hi", "bn"],
  "tabs": ["overview", "nowcast", "alerts", "map", "forecast", "predicted", "risks", "market", "advisor", "settings"],
  "capabilities": {
    "sse_chat": true,
    "json_chat": true,
    "storm_map": true,
    "nowcast_live": true,
    "geo_india_only": true,
    "concurrent_web_and_app": true
  },
  "chat": {
    "sse": "POST /api/chat with Accept: text/event-stream",
    "json": "POST /api/chat with {\"stream\": false}"
  }
}
```

### Geo

| Method | Path | Query | Status |
|---|---|---|---|
| GET | `/geo/search` | `q` (required), `limit` default 8 | `200` `{ results: Location[] }` |
| GET | `/geo/reverse` | `lat`, `lon` | `200` Location or `400` outside India |
| GET | `/geo/nearby` | `lat`, `lon`, `limit` | `{ results }` |
| GET | `/states` | | `{ states: string[] }` |
| GET | `/districts` | `state` optional | `{ districts: Location[], count }` |
| GET | `/map/layers` | | basemaps + overlays; WMS `path` `/api/map/wms` |
| GET/HEAD | `/map/wms` | standard WMS | PNG proxy (Bhuvan) |

### Snapshot slices

Location query: `district`, `place`, `lat`, `lon`. Optional `locale` on dashboard/brief.

**`GET /dashboard`** — full `DashboardSnapshot`:

```
location, generated_at, sources,
descriptive.current.{temp_c, precip_1h_mm, humidity_pct, wind_ms, sky_label, aqi, ...},
descriptive.series,
diagnostic.{anomalies, stories},
predictive.{precip_7d_mm, outlook_days, irrigate_dates, flood_watch_dates, ...},
prescriptive.{warnings[], actions[]},
risks[], live, predictions, ogd, map, vegetation, science, quality, provider_status
```

**`GET /alerts`** — `warnings`, `actions`, `quakes`, `tsunami`, `air`, `flood`, `generated_at`.

**`GET /market`** — `ogd` (mandi).

**`GET /forecast`** — `predictive`, `descriptive`, `sources`.

**`GET /predictions`** — `source=both|ours|trusted`.

**`GET /outlook`** — 7-day water-balance fields + date lists.

**`GET /risks`** — `{ location, risks: [{ id, label, severity, score_pct, confidence_pct, factors[] }] }`.

**`GET /science`** — `{ location, science }` (nowcast, monsoon, provenance, …). Large; cache it.

**`GET /insights`** — warnings, actions, diagnostic, vegetation.

**`GET /nowcast`** — locked 0–6 h object plus hours, gap, pump, sat, convective.

**`GET /nowcast/live`** — poll this. Includes `knots`, `gap`, `playhead`, `locked`, `actions`.

**`GET /nowcast/sat`** — `stride=1|60`. Kalman pack in `sat`. Do not quote as a rain-gauge.

**`GET /nowcast/storm-map?state=`** — All-India or state IR cells + lightning. `state=India` is valid.

**`POST /brief`** — query location + `locale`. Body unused. Returns `{ brief, sms, template_id, slots, risks, outlook_days, nowcast }`.

**`GET /compare?a=&b=`** — two place names (min length 2).

**`GET /scan?state=&metric=flood&limit=30`** — ranked districts.

**`GET /agent/tools`** — Advisor tool names (debug / settings).

### Advisor

`POST /api/chat`

```json
{
  "message": "Should I irrigate in Haldia?",
  "locale_hint": "en",
  "output_locale": "en",
  "conversation_id": "optional-uuid",
  "location": { "id": "...", "label": "...", "state": "...", "district": "...", "lat": 22.07, "lon": 88.07 },
  "history": [],
  "regenerate": false,
  "stream": false
}
```

| Client | How |
|---|---|
| **App (Expo)** | `"stream": false` **or** `Accept: application/json`. Response `{ ok, stream: false, events[], message }`. |
| **Web** | `Accept: text/event-stream` (and omit `stream: false`). Each line `data: {json}\n\n`. Last useful event `type: "final"` with `message`. |

`message` fields: `id`, `role`, `content` (display this), `content_en`, `locale`, `blocks[]`, `suggestions[]`, `citations[]`. Render `content`; use `blocks` for tables; never parse millimetres out of prose if a block has a number.

Keep `history` to the last ~6 turns.

---

## 7. TypeScript (recommended)

From a web app or React Native, do not import `frontend/`. Use `clients/js`:

```ts
import { createClient } from "../clients/js/src";

const api = createClient({
  baseUrl: process.env.EXPO_PUBLIC_API_BASE || "http://127.0.0.1:8000",
});

const boot = await api.bootstrap();
const places = await api.searchPlaces("Haldia");
const loc = places[0];
const dash = await api.dashboard(loc);
const live = await api.nowcastLive(loc);
const { message } = await api.chat({
  message: "Irrigate today?",
  location: loc,
  stream: false,
});
```

Web streaming:

```ts
await api.streamChat({ message: "What is the sky now?", location: loc }, (ev) => {
  if (ev.type === "token") append(ev.text);
  if (ev.type === "final") setMessage(ev.message);
});
```

---

## 8. Minimal fetch examples

```http
GET /api/health HTTP/1.1
Origin: http://localhost:3000
```

```http
GET /api/geo/search?q=Pune HTTP/1.1
```

```http
GET /api/alerts?place=Haldia&lat=22.0667&lon=88.0698 HTTP/1.1
X-Rituchakra-Client: app
```

```http
POST /api/chat HTTP/1.1
Accept: application/json
Content-Type: application/json

{"message":"Hold the pump?","stream":false,"locale_hint":"en"}
```

---

## 9. Errors

| Code | When |
|---|---|
| 400 | Reverse geocode outside India; invalid query |
| 404 | Unknown path |
| 422 | Missing required query (`q`, `state`, `a`/`b`) |
| 502/timeout | Upstream weather providers; retry; show last good snapshot |

No envelope besides FastAPI `{ "detail": ... }` on errors. Success bodies are the resource itself.

---

## 10. What not to do

- Do not mount this API under a Next rewrite unless `NEXT_PUBLIC_API_BASE` is empty on purpose.
- Do not call IMD millimetres from chat text; use `nowcast.locked` / rain-window tools already in the snapshot.
- Do not label Open-Meteo past hours as station gauges or Kalman scenes as INSAT millimetres.
- Do not run two prefixes for the same UI session.

Interactive explorer: `{origin}/docs`.
