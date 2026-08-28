# Privacy (store listing stub)

Rituchakra is an India-first weather and farm-advice client. It talks only to your published Rituchakra API.

**Location.** If you grant GPS, the app sends latitude and longitude to `/api/geo/reverse` so the dashboard can pin an Indian district. Location is not sold. You can search a place by name instead.

**Chat.** Advisor messages go to the API, which may call a local Ollama model. Do not send secrets.

**Data sources.** Forecasts and hazards come from Open-Meteo, IMD CAP, NASA, CPCB / data.gov.in, USGS, INCOIS, and similar public feeds. See the product README for attribution.

Replace this file with your legal text before Play / App Store submission.
