"""S2: emergency e-stop and domain class. Code-first; optional 0.5B later."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.agents.utterance import Plan

_EMERGENCY = re.compile(
    r"\b("
    r"help me|i am drowning|someone is drowning|trapped in (?:flood|water)|"
    r"flooded house|house is flooding|cyclone hit|tsunami coming|"
    r"call (?:police|ambulance)|emergency|sos|"
    r"डूब|बाढ़.*फंस|आपातकाल|ঘর ডুব|সাহায্য করুন"
    r")\b",
    re.I,
)

EMERGENCY_EN = (
    "If you are in immediate danger, call local emergency services now "
    "(India: 112). For disaster help, NDMA / state disaster control rooms. "
    "Rituchakra cannot dispatch rescue. Move to higher ground if water is rising."
)


@dataclass
class Triage:
    kind: str  # emergency | refuse | chat | data
    message: str | None = None


def classify(message_en: str, plan: Plan) -> Triage:
    text = message_en or ""
    if _EMERGENCY.search(text):
        return Triage(kind="emergency", message=EMERGENCY_EN)
    if plan.mode == "refuse" and plan.refuse:
        return Triage(kind="refuse", message=plan.refuse)
    if plan.mode == "data" or plan.needs or plan.catalog:
        return Triage(kind="data")
    return Triage(kind="chat")
