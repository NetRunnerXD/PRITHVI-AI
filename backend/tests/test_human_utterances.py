"""Matrix of real, misspelled, fictitious, and junk lines a human can throw at chat.

Each row has a contradiction sibling so a lucky pass cannot hide a cousin miss.
"""

from app.agents.utterance import interpret
from app.services.location_svc import resolve_named_place


def test_human_matrix():
    rows = [
        # q, mode, need_or_none, place_district_or_none
        ("Puruliya", "data", "forecast", "Purulia"),
        ("Puri", "data", "forecast", "Puri"),
        ("weather in Puruliya", "data", "forecast", "Purulia"),
        ("weather in Puri", "data", "forecast", "Puri"),
        ("Cherrapunjee", "data", "forecast", None),
        ("Calcutta", "data", "forecast", "Kolkata"),
        ("Calicut", "data", "forecast", "Kozhikode"),
        ("Noida", "data", "forecast", None),
        ("Odisha", "data", "forecast", "Khordha"),
        ("Delhi", "data", "forecast", "New Delhi"),
        ("hello there", "chat", None, None),
        ("Atlantis", "refuse", None, None),
        ("weather in Atlantis", "refuse", None, None),
        ("Hogwarts", "refuse", None, None),
        ("Paris", "refuse", None, None),
        ("Can I take my elephant to the islands?", "refuse", None, None),
        ("AQI in Jaipur", "data", "aqi", None),
        ("Flood ranking of Odisha", "data", "rank", None),
    ]
    bad = []
    for q, mode, need, district in rows:
        p = interpret(q)
        if p.mode != mode:
            bad.append((q, "mode", p.mode, mode))
            continue
        if need and need not in p.needs:
            bad.append((q, "need", p.needs, need))
        if district:
            loc = resolve_named_place(q if q.split()[0][0].isupper() and " " not in q.strip() else (p.asked or q))
            if loc is None or loc.district != district:
                # fall back: resolve the asked span
                loc = resolve_named_place(p.asked or q)
            if loc is None or loc.district != district:
                bad.append((q, "district", loc.district if loc else None, district))
    assert not bad, bad


def test_contradiction_pairs():
    pairs = [
        ("Puruliya", "Puri", "Purulia", "Puri"),
        ("Calcutta", "Calicut", "Kolkata", "Kozhikode"),
        ("Howrah", "Hogwarts", "Howrah", None),
        ("Nadia", "Narnia", "Nadia", None),
        ("Patna", "Paris", "Patna", None),
        ("Cherra", "Cherry", None, None),
    ]
    for real_q, fake_q, real_dist, fake_dist in pairs:
        r = resolve_named_place(real_q)
        f = resolve_named_place(fake_q)
        if real_dist:
            assert r is not None and r.district == real_dist, (real_q, r)
        if fake_dist:
            assert f is not None and f.district == fake_dist, (fake_q, f)
        else:
            if fake_q in {"Puri", "Calicut"}:
                assert f is not None
                assert r is not None
                assert (r.district, r.state) != (f.district, f.state)
            elif fake_q == "Cherry":
                assert f is None
                assert r is not None and r.place_name == "Cherrapunji"
            else:
                assert f is None, (fake_q, f)
                assert r is not None, real_q
