from app.agents.intent_router import classify, required_tools


def test_classify_family():
    assert classify("Should I irrigate if it rains?") == "irrigation"
    assert classify("আগামী তিন দিনে বৃষ্টি? সেচ?") == "irrigation"
    assert classify("flood warning for my village") == "flood"
    assert classify("Which districts in West Bengal are more likely to get flooded list them.") == "rank"
    assert classify("compare Nadia vs Pune") == "compare"
    assert classify("7 day outlook water balance") == "outlook"
    assert classify("mandi rice price") == "price"
    assert classify("AQI pollution today") == "aqi"
    assert classify("list all districts in Odisha") == "list"
    assert classify("hello there") == "general"
    assert classify("any earthquake near Nadia?") == "seismic"
    assert classify("tsunami warning INCOIS") == "tsunami"


def test_required_tools_include_core_and_specialized():
    irrig = required_tools("irrigation")
    assert "get_weather_forecast" in irrig
    assert "get_water_balance" in irrig
    assert required_tools("rank") == ["list_districts", "rank_districts"]
    assert "get_7day_outlook" in required_tools("outlook")
    assert "get_nowcast" in required_tools("rain")
    assert "get_nowcast" in required_tools("irrigation")
    assert "get_mandi_prices" in required_tools("price")
