"""Build an import graph of app source for AI agents.

Walks backend/app, frontend/src, clients/js/src, mobile/src.
Writes docs/codegraph.json and docs/codegraph.md.
"""

from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_JSON = ROOT / "docs" / "codegraph.json"
OUT_MD = ROOT / "docs" / "codegraph.md"

SKIP_DIR = {
    "node_modules",
    "__pycache__",
    ".next",
    "dist",
    "build",
    ".git",
    ".venv",
}

SCOPES = (
    ROOT / "backend" / "app",
    ROOT / "frontend" / "src",
    ROOT / "clients" / "js" / "src",
    ROOT / "mobile",
)

TS_FROM = re.compile(r"""(?:from|import)\s+['"]([^'"]+)['"]""")
TS_EXPORT = re.compile(
    r"^\s*export\s+(?:async\s+)?(?:function|const|class|type|interface|enum)\s+(\w+)",
    re.M,
)
PY_EXT = {".py"}
TS_EXT = {".ts", ".tsx", ".js", ".jsx"}


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def iter_files() -> list[Path]:
    out: list[Path] = []
    for scope in SCOPES:
        if not scope.exists():
            continue
        for path in scope.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR for part in path.parts):
                continue
            if path.suffix in PY_EXT or path.suffix in TS_EXT:
                if path.name.endswith(".d.ts"):
                    continue
                out.append(path)
    return sorted(out)


def py_exports_and_imports(src: str, path: Path) -> tuple[list[str], list[str]]:
    exports: list[str] = []
    imports: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return exports, imports
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                exports.append(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper() and not t.id.startswith("_"):
                    exports.append(t.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            else:
                mod = node.module or ""
                if node.level:
                    pkg = path.parent
                    for _ in range(node.level):
                        pkg = pkg.parent
                    if mod:
                        imports.append(str((pkg / mod.replace(".", "/")).as_posix()))
                    else:
                        imports.append(str(pkg.as_posix()))
                else:
                    imports.append(mod)
    return exports[:40], imports


def resolve_py(mod: str, src_file: Path) -> str | None:
    if mod.startswith("app."):
        p = ROOT / "backend" / "/".join(mod.split("."))
        for cand in (p.with_suffix(".py"), p / "__init__.py"):
            if cand.exists():
                return rel(cand)
        return "backend/" + "/".join(mod.split("."))
    if "/" in mod or mod.startswith(str(ROOT).replace("\\", "/")):
        try:
            pp = Path(mod)
            if pp.suffix != ".py":
                for cand in (pp.with_suffix(".py"), pp / "__init__.py"):
                    if cand.exists():
                        return rel(cand)
        except Exception:
            return None
    return None


def resolve_ts(spec: str, src_file: Path) -> str | None:
    if spec.startswith("@/"):
        base = ROOT / "frontend" / "src" / spec[2:]
    elif spec.startswith("."):
        base = (src_file.parent / spec)
    else:
        return None
    candidates = [
        base.with_suffix(".ts"),
        base.with_suffix(".tsx"),
        base.with_suffix(".js"),
        base / "index.ts",
        base / "index.tsx",
        Path(str(base) + ".ts"),
        Path(str(base) + ".tsx"),
    ]
    for c in candidates:
        if c.exists():
            return rel(c)
    try:
        r = rel(base)
        if r.startswith("frontend") or r.startswith("clients") or r.startswith("mobile"):
            return r
    except ValueError:
        return None
    return None


def ts_exports_and_imports(src: str) -> tuple[list[str], list[str]]:
    exports = TS_EXPORT.findall(src)[:40]
    imports = TS_FROM.findall(src)
    return exports, imports


def bucket(path: str) -> str:
    parts = path.split("/")
    if path.startswith("backend/app/"):
        if len(parts) >= 3:
            return parts[2]
        return "backend"
    if path.startswith("frontend/src/"):
        if len(parts) >= 4:
            return "fe-" + parts[2]
        return "frontend"
    if path.startswith("clients/"):
        return "clients"
    if path.startswith("mobile/"):
        return "mobile"
    return "other"


def main() -> None:
    nodes = []
    edges = []
    seen_edge: set[tuple[str, str]] = set()
    by_bucket: dict[str, list[str]] = defaultdict(list)

    for path in iter_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
        nid = rel(path)
        if path.suffix == ".py":
            exports, raw_imps = py_exports_and_imports(text, path)
            resolved = []
            for m in raw_imps:
                t = resolve_py(m, path)
                if t:
                    resolved.append(t)
        else:
            exports, raw_imps = ts_exports_and_imports(text)
            resolved = []
            for m in raw_imps:
                t = resolve_ts(m, path)
                if t:
                    resolved.append(t)
        nodes.append(
            {
                "id": nid,
                "lines": lines,
                "lang": path.suffix.lstrip("."),
                "exports": exports,
                "bucket": bucket(nid),
            }
        )
        by_bucket[bucket(nid)].append(nid)
        for t in resolved:
            key = (nid, t)
            if key not in seen_edge:
                seen_edge.add(key)
                edges.append({"from": nid, "to": t})

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "root": "Prithvi AI",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    large = sorted(nodes, key=lambda n: n["lines"], reverse=True)[:25]
    md = [
        "# Code graph (generated)",
        "",
        f"Generated `{payload['generated_at']}`. {payload['node_count']} files, {payload['edge_count']} import edges.",
        "Refresh: `python backend/scripts/codebase_graph.py`.",
        "",
        "## Largest files",
        "",
        "| Lines | Path |",
        "|---|---|",
    ]
    for n in large:
        md.append(f"| {n['lines']} | `{n['id']}` |")
    md += ["", "## Buckets", ""]
    for b, ids in sorted(by_bucket.items()):
        md.append(f"- **{b}**: {len(ids)} files")
    md += [
        "",
        "## How agents should use this",
        "",
        "1. Read `docs/CODEMAP.md` for “where to change X”.",
        "2. Open `docs/codegraph.json` and filter `nodes`/`edges` by path prefix.",
        "3. Follow `from` → `to` edges to see what a change will touch.",
        "",
    ]
    # mermaid of backend packages only (keep small)
    md += ["## Backend package edges (collapsed)", "", "```mermaid", "flowchart LR"]
    pkg_edges: set[tuple[str, str]] = set()
    for e in edges:
        if not e["from"].startswith("backend/app/") or not e["to"].startswith("backend/app/"):
            continue
        a = e["from"].split("/")[2]
        b = e["to"].split("/")[2]
        if a != b:
            pkg_edges.add((a, b))
    for a, b in sorted(pkg_edges):
        md.append(f"  {a} --> {b}")
    md += ["```", ""]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {OUT_JSON} ({len(nodes)} nodes, {len(edges)} edges)")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
