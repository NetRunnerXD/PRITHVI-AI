"""Resolve AnswerSpec cites against tool JSON. The only place numbers enter prose."""

from __future__ import annotations

import json
import re
from typing import Any

from app.i18n.number_lock import NUM, allowed_from_tools, ungrounded
from app.schemas.answer import TAB_IDS, AnswerSpec, UiAction

CITE_TOKEN = re.compile(r"(?:cite:|\{\{cite:)([a-zA-Z0-9_.\[\]]+)(?:\}\})?")
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_BLOCK_KINDS = ("prose", "metrics", "table", "decision", "timeline", "compare", "ui", "sources")
_DUMP_MARKERS = (
    "present_answer",
    "blocks:",
    "prose {",
    "metrics {",
    "table {",
    "decision {",
    "cite:",
    "get_rain_window",
    "get_nowcast",
)


def looks_like_dump(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    low = t.lower()
    if "present_answer" in low:
        return True
    if re.search(r"\bblocks\s*[:=]", low) and any(k in low for k in _BLOCK_KINDS):
        return True
    if low.startswith("{") and '"blocks"' in low:
        return False
    if re.search(r"\b(prose|table|metrics|decision)\s*\{", low):
        return True
    if re.search(r"\bdata\s*\(\s*need\s*=", low):
        return True
    if re.match(r"^data\s*:?\s*[a-z_]+", low) and len(t) < 160:
        return True
    return False


def _brace_body(text: str, open_at: int) -> tuple[str, int] | None:
    if open_at >= len(text) or text[open_at] != "{":
        return None
    depth = 0
    i = open_at
    in_str = False
    quote = ""
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == "\\" and i + 1 < len(text):
                i += 2
                continue
            if ch == quote:
                in_str = False
            i += 1
            continue
        if ch in "\"'":
            in_str = True
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[open_at + 1 : i], i + 1
        i += 1
    return None


def _parse_dialect(text: str) -> dict[str, Any] | None:
    """qwen often writes `present_answer { format: briefing, blocks: [ prose {text: "..."} ] }`."""
    t = (text or "").strip()
    t = re.sub(r"^present_answer\s*:?\s*", "", t, flags=re.I)
    if not t:
        return None
    fmt = "free"
    m = re.search(r"format:\s*[\"']?([A-Za-z0-9_+-]+)", t)
    if m:
        fmt = m.group(1)
    title = None
    m = re.search(
        r"title:\s*(?:\"([^\"]+)\"|'([^']+)'|(.+?))(?=\s*,\s*blocks\b|\s+-\s*blocks\b|\s+blocks\s*:)",
        t,
        re.I | re.S,
    )
    if m:
        title = (m.group(1) or m.group(2) or m.group(3) or "").strip().rstrip(",")
    blocks: list[dict[str, Any]] = []
    kind_re = re.compile(r"(?:^|[\s,\[\]-])(" + "|".join(_BLOCK_KINDS) + r")(?=\s*[\{\[:,\]]|\s*$)", re.I)
    pos = 0
    while True:
        m = kind_re.search(t, pos)
        if not m:
            break
        kind = m.group(1).lower()
        pos = m.end()
        body = ""
        j = pos
        while j < len(t) and t[j].isspace():
            j += 1
        if j < len(t) and t[j] == "{":
            grabbed = _brace_body(t, j)
            if grabbed:
                body, pos = grabbed
            else:
                pos = j + 1
        if kind == "sources":
            blocks.append({"type": "sources"})
            continue
        if kind == "prose":
            tm = re.search(r"text:\s*\"(.*?)\"", body, re.S)
            if not tm:
                tm = re.search(r"text:\s*'(.*?)'", body, re.S)
            if tm:
                blocks.append({"type": "prose", "text": tm.group(1)})
            continue
        if kind == "table":
            frm = re.search(r"from:\s*\"([^\"]+)\"", body)
            cols_m = re.search(r"columns:\s*\[(.*?)\]", body, re.S)
            columns = re.findall(r"[\"']([^\"']+)[\"']", cols_m.group(1)) if cols_m else []
            blocks.append({"type": "table", "from": frm.group(1) if frm else "", "columns": columns})
            continue
        if kind == "metrics":
            items = []
            for im in re.finditer(
                r"\{\s*label:\s*\"([^\"]+)\"\s*,\s*cite:\s*\"([^\"]+)\"(?:\s*,\s*unit:\s*\"([^\"]*)\")?\s*\}",
                body,
            ):
                items.append({"label": im.group(1), "cite": im.group(2), "unit": im.group(3) or ""})
            if items:
                blocks.append({"type": "metrics", "items": items})
            continue
        if kind == "decision":
            act = re.search(r"action:\s*\"([^\"]*)\"", body)
            why = re.search(r"why:\s*\"([^\"]*)\"", body)
            action = act.group(1) if act else ""
            if action:
                blocks.append({"type": "decision", "action": action, "why": (why.group(1) if why else "") or None})
            continue
        if kind == "ui":
            tab = re.search(r"tab:\s*[\"']?([A-Za-z0-9_-]+)", body)
            hl = re.search(r"highlight:\s*[\"']?([^,}\s]+)", body)
            highlight = hl.group(1).strip() if hl else None
            if highlight and highlight.lower() in {"true", "false", "1", "0"}:
                highlight = None
            blocks.append({"type": "ui", "tab": tab.group(1) if tab else None, "highlight": highlight})
            continue
        if kind == "timeline":
            frm = re.search(r"from:\s*\"([^\"]+)\"", body)
            blocks.append({"type": "timeline", "from": frm.group(1) if frm else "get_nowcast.hours"})
    if not blocks:
        return None
    return {"format": fmt, "title": title, "blocks": blocks}


def _walk_get(obj: Any, parts: list[str]) -> Any:
    cur = obj
    for p in parts:
        if cur is None:
            return None
        if isinstance(cur, list):
            if p.isdigit() and int(p) < len(cur):
                cur = cur[int(p)]
                continue
            return None
        if isinstance(cur, dict):
            if p in cur:
                cur = cur[p]
                continue
            return None
        return None
    return cur


def _deep_find(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        if key in obj and obj[key] is not None:
            return obj[key]
        for v in obj.values():
            hit = _deep_find(v, key)
            if hit is not None:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = _deep_find(v, key)
            if hit is not None:
                return hit
    return None


def resolve_cite(collected: dict[str, Any], path: str) -> Any:
    raw = (path or "").strip()
    if raw.startswith("cite:"):
        raw = raw[5:]
    raw = raw.strip("{}")
    if not raw:
        return None
    parts = [p for p in raw.replace("]", "").split(".") if p]
    flat: list[str] = []
    for p in parts:
        if "[" in p:
            a, b = p.split("[", 1)
            if a:
                flat.append(a)
            flat.append(b)
        else:
            flat.append(p)
    if not flat:
        return None
    if flat[0] in collected:
        hit = _walk_get(collected[flat[0]], flat[1:])
        if hit is not None:
            return hit
        if len(flat) == 2:
            found = _deep_find(collected[flat[0]], flat[1])
            if found is not None:
                return found
    if "." not in raw and "[" not in raw:
        return _deep_find(collected, raw)
    for name, payload in collected.items():
        hit = _walk_get(payload, flat)
        if hit is not None:
            return hit
        if flat[0] == name:
            continue
        found = _deep_find(payload, flat[-1])
        if found is not None and len(flat) == 1:
            return found
    return None


def parse_spec(raw: Any) -> AnswerSpec | None:
    if raw is None:
        return None
    if isinstance(raw, AnswerSpec):
        return raw
    data = raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
        if fence:
            text = fence.group(1)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            loaded = None
            if start >= 0 and end > start:
                try:
                    loaded = json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    loaded = None
            if isinstance(loaded, dict):
                data = loaded
            else:
                dialect = _parse_dialect(raw)
                if dialect:
                    data = dialect
                else:
                    return None
    if not isinstance(data, dict):
        return None
    if "spec" in data and isinstance(data["spec"], dict):
        data = data["spec"]
    if "blocks" not in data and "type" in data:
        data = {"blocks": [data]}
    if "blocks" not in data:
        dialect = _parse_dialect(json.dumps(data) if not isinstance(raw, str) else str(raw))
        if dialect:
            data = dialect
        else:
            return None
    try:
        return AnswerSpec.model_validate(data)
    except Exception:
        return AnswerSpec(format=str(data.get("format") or "free"), blocks=list(data.get("blocks") or []))


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _drop_ungrounded(text: str, allowed: set[str]) -> tuple[str, list[str]]:
    if not (text or "").strip():
        return "", []
    parts = [p for p in SENTENCE.split(text) if p is not None]
    if len(parts) <= 1:
        chunks = [s.strip() for s in re.split(r"\n+", text) if s.strip()]
    else:
        chunks = [p.strip() for p in parts if p and p.strip()]
    keep: list[str] = []
    rejected: list[str] = []
    for chunk in chunks:
        bad = ungrounded(chunk, allowed)
        if bad:
            rejected.extend(bad)
            continue
        keep.append(chunk)
    return (" ".join(keep)).strip(), rejected


def _table_rows(src: Any, columns: list[str] | None) -> list[dict[str, Any]]:
    rows = src if isinstance(src, list) else []
    out: list[dict[str, Any]] = []
    cols = columns or []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if cols:
            out.append({c: row.get(c) for c in cols if c in row})
        else:
            out.append(dict(row))
    return out


def _ui_from_block(block: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    tab = block.get("tab")
    if tab in TAB_IDS:
        actions.append({"op": "tab", "tab": tab})
    hl = block.get("highlight")
    if hl and str(hl).lower() not in {"true", "false", "1", "0", "none"}:
        actions.append({"op": "highlight", "target": str(hl)})
    if block.get("center") and isinstance(block["center"], list) and len(block["center"]) >= 2:
        actions.append(
            {
                "op": "map",
                "center": [float(block["center"][0]), float(block["center"][1])],
                "zoom": block.get("zoom"),
            }
        )
    return actions


def fallback_spec(collected: dict[str, Any], grounded: str = "") -> AnswerSpec:
    blocks: list[dict[str, Any]] = []
    win = collected.get("get_rain_window") or {}
    if win.get("days") or win.get("missing"):
        blocks.append(
            {
                "type": "table",
                "from": "get_rain_window.days",
                "columns": ["date", "precip_mm", "precip_prob_pct", "temp_max_c"],
            }
        )
    nc = collected.get("get_nowcast") or {}
    if nc:
        blocks.append(
            {
                "type": "metrics",
                "items": [
                    {"label": "90 min interrupt", "cite": "get_nowcast.p_interrupt_90m"},
                    {"label": "Onset", "cite": "get_nowcast.onset"},
                    {"label": "Field 2h", "cite": "get_nowcast.enterable_2h"},
                ],
            }
        )
        pump = nc.get("pump") or {}
        if pump.get("action") == "hold":
            blocks.append({"type": "decision", "action": "hold_pump", "why": "cite:get_nowcast.p_interrupt_90m"})
    rank = collected.get("rank_districts") or {}
    if rank.get("ranked"):
        blocks.append(
            {
                "type": "table",
                "from": "rank_districts.ranked",
                "columns": ["district", "flood_score", "precip_3d_mm"],
            }
        )
    if grounded:
        blocks.append({"type": "prose", "text": grounded})
    if not blocks:
        blocks.append({"type": "prose", "text": grounded or "No tool numbers for this question."})
    return AnswerSpec(format="fallback", blocks=blocks)


def ensure_window_table(spec: AnswerSpec, collected: dict[str, Any]) -> AnswerSpec:
    win = collected.get("get_rain_window") or {}
    if not (win.get("days") or win.get("missing")):
        return spec
    for b in spec.blocks:
        if isinstance(b, dict) and b.get("type") == "table" and "rain_window" in str(b.get("from") or ""):
            return spec
    spec.blocks = [
        {
            "type": "table",
            "from": "get_rain_window.days",
            "columns": ["date", "precip_mm", "precip_prob_pct", "temp_max_c"],
        },
        *list(spec.blocks),
    ]
    return spec


def bind(
    spec: AnswerSpec | dict | None,
    collected: dict[str, Any],
    extra_allowed: list[Any] | None = None,
    _retry: bool = False,
) -> dict[str, Any]:
    parsed = parse_spec(spec) if not isinstance(spec, AnswerSpec) else spec
    if parsed is None:
        parsed = fallback_spec(collected)
    parsed = ensure_window_table(parsed, collected)

    payloads: list[Any] = list(collected.values())
    if extra_allowed:
        payloads.extend(extra_allowed)
    allowed = allowed_from_tools(payloads)

    bound_blocks: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    rejected: list[str] = []
    ui_actions: list[dict[str, Any]] = []
    prose_parts: list[str] = []

    if parsed.title:
        title, bad = _drop_ungrounded(parsed.title, allowed)
        rejected.extend(bad)
        parsed.title = title or None

    for raw_block in parsed.blocks:
        block = raw_block if isinstance(raw_block, dict) else {}
        kind = str(block.get("type") or "prose")
        if kind == "ui":
            ui_actions.extend(_ui_from_block(block))
            continue
        if kind == "table":
            path = block.get("from") or block.get("frm") or ""
            src = resolve_cite(collected, str(path))
            rows = _table_rows(src, block.get("columns"))
            bound_blocks.append(
                {
                    "type": "table",
                    "from": path,
                    "columns": block.get("columns") or (list(rows[0].keys()) if rows else []),
                    "rows": rows,
                }
            )
            if path:
                citations.append({"tool": str(path).split(".")[0], "field": path, "n": len(rows)})
            continue
        if kind == "timeline":
            path = block.get("from") or "get_nowcast.hours"
            src = resolve_cite(collected, str(path))
            rows = _table_rows(src, block.get("columns"))
            bound_blocks.append({"type": "timeline", "from": path, "rows": rows})
            citations.append({"tool": str(path).split(".")[0], "field": path, "n": len(rows)})
            continue
        if kind == "metrics":
            items = []
            for it in block.get("items") or []:
                if not isinstance(it, dict):
                    continue
                cite = str(it.get("cite") or "")
                val = resolve_cite(collected, cite)
                if val is None or isinstance(val, (list, dict)):
                    rejected.append(cite or "?")
                    continue
                items.append(
                    {
                        "label": it.get("label") or cite,
                        "cite": cite,
                        "unit": it.get("unit") or "",
                        "value": val,
                    }
                )
                citations.append({"tool": cite.split(".")[0] if cite else "", "field": cite, "value": val})
            if items:
                bound_blocks.append({"type": "metrics", "items": items})
            continue
        if kind == "decision":
            why = block.get("why")
            why_val = resolve_cite(collected, str(why)) if why else None
            action = str(block.get("action") or "").strip()
            if not action or looks_like_dump(action):
                continue
            bound_blocks.append(
                {
                    "type": "decision",
                    "action": action,
                    "when": block.get("when"),
                    "why": why_val if why_val is not None else None,
                }
            )
            continue
        if kind == "sources":
            bound_blocks.append({"type": "sources", "items": block.get("items") or parsed.sources})
            continue
        if kind == "compare":
            bound_blocks.append(block)
            continue
        text = str(block.get("text") or "")
        if looks_like_dump(text):
            continue
        def _sub(m: re.Match[str]) -> str:
            val = resolve_cite(collected, m.group(1))
            if val is None:
                rejected.append(m.group(1))
                return ""
            citations.append({"tool": m.group(1).split(".")[0], "field": m.group(1), "value": val})
            return _fmt(val)

        filled = CITE_TOKEN.sub(_sub, text)
        cleaned, bad = _drop_ungrounded(filled, allowed)
        rejected.extend(bad)
        if cleaned:
            bound_blocks.append({"type": "prose", "text": cleaned})
            prose_parts.append(cleaned)

    if parsed.title and looks_like_dump(parsed.title):
        parsed.title = None

    content_en = _content_from_blocks(parsed.title, bound_blocks)
    if looks_like_dump(content_en) and not _retry:
        return bind(fallback_spec(collected), collected, extra_allowed=extra_allowed, _retry=True)
    if looks_like_dump(content_en):
        bound_blocks = [
            b
            for b in bound_blocks
            if not (b.get("type") == "prose" and looks_like_dump(str(b.get("text") or "")))
        ]
        content_en = _content_from_blocks(None, bound_blocks)
    leftover = [m.group(0) for m in NUM.finditer(content_en) if ungrounded(m.group(0), allowed)]
    # leftover already handled per-sentence; keep list unique
    bad_unique = []
    for x in rejected + leftover:
        if x and x not in bad_unique:
            bad_unique.append(x)

    return {
        "spec": {"format": parsed.format, "title": parsed.title, "blocks": bound_blocks, "sources": parsed.sources},
        "blocks": bound_blocks,
        "content_en": content_en,
        "citations": citations,
        "rejected": bad_unique,
        "ui": [UiAction.model_validate(a).model_dump(exclude_none=True) for a in ui_actions],
    }


def _content_from_blocks(title: str | None, blocks: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    if title:
        lines.append(title)
    for b in blocks:
        kind = b.get("type")
        if kind == "prose" and b.get("text"):
            lines.append(str(b["text"]))
        elif kind == "metrics":
            for it in b.get("items") or []:
                unit = f" {it['unit']}" if it.get("unit") else ""
                lines.append(f"{it.get('label')}: {_fmt(it.get('value'))}{unit}".rstrip())
        elif kind == "table":
            cols = b.get("columns") or []
            rows = b.get("rows") or []
            if cols:
                lines.append(" | ".join(cols))
            for row in rows:
                if isinstance(row, dict):
                    keys = cols or list(row.keys())
                    lines.append(" | ".join(_fmt(row.get(c)) for c in keys))
        elif kind == "timeline":
            for row in b.get("rows") or []:
                if isinstance(row, dict):
                    lines.append(" | ".join(f"{k}={_fmt(v)}" for k, v in row.items()))
        elif kind == "decision":
            bit = f"Decision: {b.get('action') or ''}".strip()
            if b.get("why") is not None:
                bit += f" ({_fmt(b['why'])})"
            lines.append(bit)
        elif kind == "compare":
            lines.append(str(b.get("text") or "Comparison from tool JSON."))
    return "\n".join(lines).strip()


def spec_from_prose(text: str) -> AnswerSpec:
    blob = text or ""
    if looks_like_dump(blob):
        parsed = parse_spec(blob)
        if parsed:
            return parsed
        return AnswerSpec(format="prose", blocks=[])
    return AnswerSpec(format="prose", blocks=[{"type": "prose", "text": blob}])
