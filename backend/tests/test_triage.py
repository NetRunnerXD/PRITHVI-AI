from app.agents.triage import classify
from app.agents.utterance import interpret


def test_emergency_no_data_mode():
    plan = interpret("help me someone is drowning in the flood")
    t = classify("help me someone is drowning in the flood", plan)
    assert t.kind == "emergency"
    assert t.message and "112" in t.message


def test_chat_hello():
    plan = interpret("hello")
    t = classify("hello", plan)
    assert t.kind in {"chat", "refuse"}
