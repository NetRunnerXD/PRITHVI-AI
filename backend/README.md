# Rituchakra API

Standalone FastAPI service. **No frontend assets.** Publish this process and any web or React Native app can call it.

## Run

```powershell
cd backend
python -m pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- Service card: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Health: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- OpenAPI: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)
- Route catalog: [http://127.0.0.1:8000/api](http://127.0.0.1:8000/api)

Bind `0.0.0.0` if a phone or another machine will call the API. Set `CORS_ORIGINS` / `CORS_ORIGIN_REGEX` and, when publishing, `PUBLIC_BASE_URL`.

Local clients (no frontend rebuild needed):

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# GET  http://127.0.0.1:8000/api/health
# GET  http://127.0.0.1:8000/api/bootstrap
# GET  http://127.0.0.1:8000/api/alerts
# GET  http://127.0.0.1:8000/api/market
# POST http://127.0.0.1:8000/api/chat   JSON body {"message":"...","stream":false}
```

Android / Expo: `EXPO_PUBLIC_API_BASE=http://<LAN-IP>:8000`. Prefer `stream: false` on chat if SSE is unavailable.

## Tests

```powershell
cd backend
python -m pytest -q
```

## Export OpenAPI

```powershell
cd backend
python scripts/export_openapi.py
```

Writes `openapi.json` next to this file.

## Clients

Do not serve `../frontend` from this process. Point a new app at this origin using `../clients/js`.
