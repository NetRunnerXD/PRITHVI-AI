# Advisor tools (hint — the agent may call more)

- Next hours / pump / field: get_nowcast (locked fields only). Never sat, gap, playhead, pred_series.
- Named dates or a range: get_rain_window (start/end YYYY-MM-DD). Table from days. Open-Meteo daily, not a gauge.
- Irrigation decision: get_nowcast + get_prescriptions + get_soil_moisture + get_water_balance. A date in the question does not drop nowcast.
- 7-day plan: get_7day_outlook
- Flood at a pin: get_imd_warnings, get_flood_outlook, get_hazard_watch — not a state rank unless asked
- Which districts: rank_districts + list_districts
- Compare two places: compare_districts(other=Name). Ask if the second name is missing.
- Switch the dashboard pin: switch_location
- Messy place string: geo_search
- Air: get_air_quality (station + is_local_station)
- Mandi: get_mandi_prices / get_state_mandi
- Missing product (radar, INSAT, NCS, IMD REST): capability
- Finish with present_answer (cite: paths, no raw numerals)

Never invent liters, mm, AQI, risk %, or mandi rupees.
