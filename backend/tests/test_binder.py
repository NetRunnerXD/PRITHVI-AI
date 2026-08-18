from app.agents.binder import bind, fallback_spec, looks_like_dump, parse_spec, resolve_cite
from app.agents.views import snapshot_index, strip_forbidden


def test_resolve_cite_nested_and_deep():
    collected = {
        "get_nowcast": {
            "nowcast": {"p_interrupt_90m": 0.62, "onset": "2026-08-18T16:00:00"},
            "pump": {"action": "hold", "p_interrupt_90m": 0.62},
        },
        "get_rain_window": {"total_mm": 41.2, "days": [{"date": "2026-08-23", "precip_mm": 4.2}]},
    }
    assert resolve_cite(collected, "get_nowcast.p_interrupt_90m") == 0.62
    assert resolve_cite(collected, "cite:get_rain_window.total_mm") == 41.2
    assert resolve_cite(collected, "get_rain_window.days")[0]["precip_mm"] == 4.2


def test_bind_table_verbatim_and_strips_invented_mm():
    collected = {
        "get_rain_window": {
            "days": [
                {"date": "2026-08-23", "precip_mm": 4.2, "precip_prob_pct": 70},
                {"date": "2026-08-24", "precip_mm": 8.0, "precip_prob_pct": 80},
            ],
            "total_mm": 12.2,
        }
    }
    spec = {
        "format": "table",
        "blocks": [
            {"type": "prose", "text": "It will dump 81.3 mm on Tuesday."},
            {
                "type": "table",
                "from": "get_rain_window.days",
                "columns": ["date", "precip_mm"],
            },
            {"type": "metrics", "items": [{"label": "Total", "cite": "get_rain_window.total_mm", "unit": "mm"}]},
        ],
    }
    out = bind(spec, collected)
    assert "81.3" not in out["content_en"]
    table = next(b for b in out["blocks"] if b["type"] == "table")
    assert table["rows"] == [
        {"date": "2026-08-23", "precip_mm": 4.2},
        {"date": "2026-08-24", "precip_mm": 8.0},
    ]
    metrics = next(b for b in out["blocks"] if b["type"] == "metrics")
    assert metrics["items"][0]["value"] == 12.2


def test_parse_spec_from_fenced_json():
    raw = """Here you go
```json
{"format": "briefing", "blocks": [{"type": "prose", "text": "Open-Meteo daily, not a gauge."}]}
```
"""
    spec = parse_spec(raw)
    assert spec is not None
    assert spec.format == "briefing"


def test_fallback_injects_window_and_nowcast():
    spec = fallback_spec(
        {
            "get_rain_window": {"days": [{"date": "2026-08-23", "precip_mm": 1}]},
            "get_nowcast": {"pump": {"action": "hold"}, "nowcast": {"p_interrupt_90m": 0.5}},
        }
    )
    kinds = [b["type"] for b in spec.blocks]
    assert "table" in kinds
    assert "metrics" in kinds
    assert "decision" in kinds


def test_strip_forbidden_drops_kalman():
    blob = {"nowcast": {"mm": 1}, "sat": {"pred_series": [9.9]}, "gap": [], "playhead": {}}
    clean = strip_forbidden(blob)
    assert "sat" not in clean
    assert "pred_series" not in str(clean)
    assert clean["nowcast"]["mm"] == 1


DUMP = (
    'present_answer { format: briefing, title: Rainfall Prediction for Haldia, 23 to 28 August 2026, '
    'blocks: [ prose {text: "The forecast indicates significant rainfall in Haldia over the next few days."}, '
    'metrics { items: [ {label: "Date", cite: "get_rain_window.days.date"}, '
    '{label: "Precipitation (mm)", cite: "get_rain_window.days.precip_mm"} ] }, '
    'table { from: "get_rain_window.days", columns: ["date", "precip_mm", "precip_prob_pct"] }, '
    'prose {text: "Farmers should prepare for water management challenges."}, '
    'decision { action: "Prepare for heavy rainfall", why: "" }, sources ] }'
)

ELEPHANT = (
    "present_answer: - format: decision - title: Elephant Outing Decision - blocks: "
    '- prose {text: "To ensure your safety and that of the elephant, please provide more details about your destination in the city."} '
    "- ui {tab: overview, highlight: true}"
)


def test_parse_qwen_present_answer_dump():
    assert looks_like_dump(DUMP)
    spec = parse_spec(DUMP)
    assert spec is not None
    kinds = [b.get("type") if isinstance(b, dict) else None for b in spec.blocks]
    assert "prose" in kinds
    assert "table" in kinds
    collected = {
        "get_rain_window": {
            "days": [
                {"date": "2026-08-23", "precip_mm": 4.2, "precip_prob_pct": 70},
                {"date": "2026-08-28", "precip_mm": 18.0, "precip_prob_pct": 90},
            ],
            "total_mm": 22.2,
        }
    }
    out = bind(spec, collected)
    assert "present_answer" not in out["content_en"]
    assert "get_rain_window" not in out["content_en"]
    table = next(b for b in out["blocks"] if b["type"] == "table")
    assert table["rows"][0]["precip_mm"] == 4.2
    assert not any(b["type"] == "metrics" and any("days.date" in str(it) for it in b.get("items") or []) for b in out["blocks"])


def test_parse_elephant_dump_not_shown_raw():
    spec = parse_spec(ELEPHANT)
    assert spec is not None
    out = bind(spec, {})
    assert "present_answer" not in out["content_en"]
    assert "elephant" in out["content_en"].lower()
    assert not out["ui"] or out["ui"][0].get("op") == "tab"


def test_snapshot_index_has_no_sat(monkeypatch):
    from app.schemas.dashboard import (
        CurrentConditions,
        DashboardSnapshot,
        Descriptive,
        Diagnostic,
        MapState,
        Predictive,
        Prescriptive,
    )
    from app.schemas.location import Location

    snap = DashboardSnapshot(
        location=Location(
            id="x",
            label="Haldia, West Bengal",
            state="West Bengal",
            district="Purba Medinipur",
            lat=22.07,
            lon=88.07,
            place_kind="city",
            place_name="Haldia",
        ),
        generated_at="t",
        sources=[],
        descriptive=Descriptive(current=CurrentConditions(temp_c=28)),
        diagnostic=Diagnostic(),
        predictive=Predictive(precip_next_3d_mm=10),
        prescriptive=Prescriptive(),
        risks=[],
        map=MapState(center=[22.07, 88.07]),
        science={
            "nowcast": {
                "locked": {"p_interrupt_90m": 0.4},
                "sat": {"pred_series": [1.2]},
                "playhead": {"rate": 9},
            }
        },
    )
    idx = snapshot_index(snap)
    dumped = str(idx)
    assert "pred_series" not in dumped
    assert "playhead" not in dumped
    assert idx["nowcast"]["p_interrupt_90m"] == 0.4
