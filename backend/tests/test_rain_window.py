from datetime import date

import pytest

from app.services.rain_window import fetch_window, format_en


@pytest.mark.asyncio
async def test_fetch_window_formats_days(monkeypatch):
    async def fake_daily(lat, lon, start, end):
        return {
            "daily": {
                "time": ["2026-08-23", "2026-08-24", "2026-08-25"],
                "precipitation_sum": [4.2, 8.0, 1.1],
                "precipitation_probability_max": [70, 80, 40],
                "temperature_2m_max": [31.2, 30.5, 32.0],
                "temperature_2m_min": [26.0, 25.5, 26.1],
                "weather_code": [61, 63, 3],
            }
        }

    from app.providers import open_meteo

    monkeypatch.setattr(open_meteo, "daily_window", fake_daily)
    from app.schemas.location import Location

    loc = Location(
        id="t",
        label="Haldia, West Bengal",
        state="West Bengal",
        district="Purba Medinipur",
        lat=22.07,
        lon=88.07,
        timezone="Asia/Kolkata",
        crop_hint="aman_rice",
        place_kind="city",
        place_name="Haldia",
    )
    pack = await fetch_window(loc, date(2026, 8, 23), date(2026, 8, 28))
    assert pack["days"][0]["precip_mm"] == 4.2
    assert pack["total_mm"] == 13.3
    assert "2026-08-26" in pack["missing"]
    text = format_en(pack)
    assert "Haldia" in text
    assert "4.2 mm" in text
    assert "Open-Meteo" in text
    assert "not a rain-gauge" in text
