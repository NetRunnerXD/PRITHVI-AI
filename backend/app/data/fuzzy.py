"""India-name fold + Damerau–Levenshtein.

Puruliya hits Purulia. Puri, Pure, and Calicut must not.
"""

from __future__ import annotations

import re

_NON = re.compile(r"[^a-z0-9\s]")
_SPACE = re.compile(r"\s+")
_PLACE_NOISE = re.compile(
    r"\b(district|city|town|village|tehsil|taluk|municipality|weather|forecast|aqi|rain)\b",
    re.I,
)


def clean_place_query(name: str) -> str:
    s = _PLACE_NOISE.sub(" ", name or "")
    s = _NON.sub(" ", s.lower())
    return _SPACE.sub(" ", s).strip()


def fold(name: str) -> str:
    s = clean_place_query(name)
    if not s:
        return ""
    # Census / postal romanizations: Puruliya → Purulia
    if s.endswith("iya") and len(s) > 5:
        s = s[:-3] + "ia"
    elif s.endswith("eya") and len(s) > 5:
        s = s[:-3] + "ea"
    for src, dst in (("ee", "i"), ("oo", "u"), ("kh", "k"), ("gh", "g")):
        s = s.replace(src, dst)
    return s


def damerau(a: str, b: str) -> int:
    a, b = a or "", b or ""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if not la:
        return lb
    if not lb:
        return la
    dp = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        dp[i][0] = i
    for j in range(lb + 1):
        dp[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                dp[i][j] = min(dp[i][j], dp[i - 2][j - 2] + 1)
    return dp[la][lb]


def ratio(a: str, b: str) -> float:
    fa, fb = fold(a), fold(b)
    if not fa or not fb:
        return 0.0
    if fa == fb:
        return 1.0
    d = damerau(fa, fb)
    return 1.0 - d / max(len(fa), len(fb))


def close_enough(query: str, candidate: str) -> bool:
    """True for Puruliya~Purulia. False for Puri~Purulia, Pure~Purulia, Calicut~Calcutta."""
    q, c = fold(query), fold(candidate)
    if not q or not c:
        return False
    if q == c:
        return True
    shorter, longer = (q, c) if len(q) <= len(c) else (c, q)
    # Stem trap: "puri" is a prefix of "purulia", not a spelling of it.
    if longer.startswith(shorter) and (len(longer) - len(shorter)) >= 2:
        return False
    if longer.endswith(shorter) and (len(longer) - len(shorter)) >= 2 and len(shorter) < 6:
        return False
    if q in c and len(q) >= 6:
        return len(c) - len(q) <= 2
    if c in q and len(c) >= 6:
        return len(q) - len(c) <= 2
    n = max(len(q), len(c))
    if n <= 6:
        # Cherry ≠ Cherra ≠ Cherrapunji. Six letters need a fold-equal hit.
        return q == c
    d = damerau(q, c)
    if min(len(q), len(c)) < 4:
        return False
    if n <= 8:
        return d <= 1
    return d <= 2 and ratio(q, c) >= 0.84


def match_rank(query: str, candidate: str) -> int | None:
    """0 fold-equal, 1 close spelling, None = no match. Never a prefix stem."""
    q, c = fold(query), fold(candidate)
    if not q or not c:
        return None
    if q == c:
        return 0
    if close_enough(query, candidate):
        return 1
    return None


def tokens(text: str) -> list[str]:
    return [t for t in fold(text).split() if len(t) >= 4]


def best_fuzzy(query: str, candidates: list[str]) -> tuple[str, float] | None:
    q = (query or "").strip()
    if not q:
        return None
    best: tuple[str, float] | None = None
    for cand in candidates:
        if match_rank(q, cand) is None:
            continue
        sc = ratio(q, cand)
        if best is None or sc > best[1]:
            best = (cand, sc)
    return best
