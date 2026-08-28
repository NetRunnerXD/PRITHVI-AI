# Rituchakra mobile (Expo)

Uses `clients/js` against the **same FastAPI** as the web dashboard. Do not import `frontend/`.

```powershell
cd mobile
copy .env.example .env
# set EXPO_PUBLIC_API_BASE to your public HTTPS API (or LAN IP for a physical phone)
npm install
npx expo start
```

- GPS calls `/api/geo/reverse` (India gazetteer).
- Chat uses SSE (`fetch` + `ReadableStream`). Expo Go SDK 52 supports this; if a device cannot stream, upgrade Expo or use a development build.
- Maps: `react-native-maps` (not Leaflet).
- Store privacy text: `../deploy/PRIVACY.md`.
