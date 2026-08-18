"""Names we will never geocode: invented worlds and foreign cities/countries."""

from __future__ import annotations

FICTION = {
    "atlantis", "wakanda", "hogwarts", "narnia", "mordor", "gondor",
    "asgard", "gotham", "metropolis", "westeros", "springfield",
    "neverland", "pandora", "valhalla", "camelot", "rivendell",
    "shire", "the shire", "tatooine", "whoville", "el dorado",
    "middle earth", "gotham city", "wakanda forever", "latveria",
    "krypton", "vulcan", "arrakis",
}

FOREIGN = {
    "paris", "london", "tokyo", "new york", "beijing", "berlin",
    "rome", "dubai", "singapore", "bangkok", "sydney", "moscow",
    "cairo", "nairobi", "toronto", "chicago", "los angeles",
    "madrid", "lisbon", "seoul", "osaka", "vancouver", "boston",
    "florida", "california", "texas", "england", "france", "japan",
    "china", "germany", "italy", "australia", "canada", "brazil",
}


def is_blocked_name(name: str | None) -> bool:
    n = (name or "").strip().lower()
    if not n:
        return False
    blocked = FICTION | FOREIGN
    if n in blocked:
        return True
    return any(n == x or n.startswith(x + " ") or n.endswith(" " + x) for x in blocked)
