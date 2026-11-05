"""Devanagari → casual Hinglish Latin (fallback when no LLM is available for Hinglish replies).

Rule based: inherent 'a' after consonants, word-final schwa dropped, anusvara → n/m,
long vowels flattened the way people text ("baarish" → "barish"). Digits become ASCII.
"""

from __future__ import annotations

import re

_CONS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh",
    "ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d",
    "ध": "dh", "न": "n", "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r",
    "ल": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h", "ळ": "l",
}
_NUKTA = {"क": "q", "ख": "kh", "ग": "gh", "ज": "z", "ड": "d", "ढ": "dh", "फ": "f", "य": "y"}
_VOW = {
    "अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u", "ऋ": "ri", "ए": "e", "ऐ": "ai",
    "ओ": "o", "औ": "au", "ऑ": "o", "ॲ": "e",
}
_MATRA = {
    "ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "ृ": "ri", "े": "e", "ै": "ai", "ो": "o",
    "ौ": "au", "ॉ": "o", "ॅ": "e",
}
_VIRAMA = "्"
_NUKTA_SIGN = "़"
_LABIAL = set("pbm")
_DIGITS = {chr(0x0966 + i): str(i) for i in range(10)}


def _word(w: str) -> str:
    out: list[str] = []
    i = 0
    n = len(w)
    while i < n:
        ch = w[i]
        if ch in _CONS:
            base = _CONS[ch]
            j = i + 1
            if j < n and w[j] == _NUKTA_SIGN:
                base = _NUKTA.get(ch, base)
                j += 1
            if j < n and w[j] == _VIRAMA:
                out.append(base)
                i = j + 1
                continue
            if j < n and w[j] in _MATRA:
                out.append(base + _MATRA[w[j]])
                i = j + 1
                continue
            # inherent schwa; dropped at word end below
            out.append(base + "a")
            i = j
            continue
        if ch in _VOW:
            out.append(_VOW[ch])
        elif ch in ("ं", "ँ"):
            out.append("\x00")  # resolved after we know the next consonant
        elif ch == "ः":
            out.append("h")
        elif ch in _DIGITS:
            out.append(_DIGITS[ch])
        elif ch == _NUKTA_SIGN:
            pass
        else:
            out.append(ch)
        i += 1
    s = "".join(out)
    s = re.sub(r"\x00(?=[pbm])", "m", s)
    s = s.replace("\x00", "n")
    letters = re.sub(r"[^a-z]", "", s)
    if len(letters) > 2 and s.endswith("a") and not s.endswith("aa") and w and (w[-1] in _CONS or w[-1] == _NUKTA_SIGN):
        s = s[:-1]
    return s


def deva_to_latin(text: str) -> str:
    blob = (text or "").replace("।", ".").replace("॥", ".")
    for deva, latin in (("मिमी", "mm"), ("किमी", "km"), ("सेमी", "cm"), ("डिग्री", "degree")):
        blob = blob.replace(deva, latin)
    return re.sub(r"[\u0900-\u097F]+", lambda m: _word(m.group(0)), blob)
