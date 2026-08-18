"use client";

import { Markdown } from "./Markdown";
import type { ChatBlock } from "@/types/dashboard";

function cell(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") return String(v);
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "object") return "";
  return String(v);
}

function isDump(text?: string): boolean {
  const t = (text || "").toLowerCase();
  if (!t) return false;
  if (t.includes("present_answer")) return true;
  if (/\b(prose|metrics|table|decision)\s*\{/.test(t)) return true;
  if (/\bblocks\s*[:=]/.test(t) && /\b(prose|table|metrics)\b/.test(t)) return true;
  return false;
}

export function ChatBlocks({ blocks, prose }: { blocks?: ChatBlock[]; prose?: string }) {
  const visible = (blocks || []).filter((b) => !(b.type === "prose" && isDump(b.text)));
  const lead = prose && !isDump(prose) ? prose : "";
  if (!visible.length) {
    return lead ? <Markdown text={lead} /> : null;
  }
  return (
    <div className="space-y-2">
      {lead ? <Markdown text={lead} /> : null}
      {visible.map((b, i) => {
        if (b.type === "prose" && b.text && !isDump(b.text)) {
          return <Markdown key={i} text={b.text} />;
        }
        if (b.type === "metrics" && b.items?.length) {
          return (
            <ul key={i} className="grid grid-cols-2 gap-1.5">
              {b.items.map((it, j) => (
                <li key={j} className="rounded-xl bg-neo-bg px-2 py-1.5">
                  <p className="text-[10px] uppercase tracking-wide text-neo-muted">{it.label}</p>
                  <p className="font-mono text-sm">
                    {cell(it.value)}
                    {it.unit ? ` ${it.unit}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          );
        }
        if (b.type === "table" && (b.rows?.length || b.columns?.length)) {
          const cols = b.columns?.length ? b.columns : Object.keys(b.rows?.[0] || {});
          return (
            <div key={i} className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-neo-muted">
                    {cols.map((c) => (
                      <th key={c} className="py-1 pr-2 font-medium">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(b.rows || []).map((row, r) => (
                    <tr key={r} className="border-t border-neo-line">
                      {cols.map((c) => (
                        <td key={c} className="py-1 pr-2 font-mono">
                          {cell(row[c])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        if (b.type === "timeline" && b.rows?.length) {
          return (
            <ol key={i} className="space-y-1 text-xs">
              {b.rows.map((row, r) => (
                <li key={r} className="font-mono">
                  {Object.entries(row)
                    .map(([k, v]) => `${k} ${cell(v)}`)
                    .join(" · ")}
                </li>
              ))}
            </ol>
          );
        }
        if (b.type === "decision") {
          return (
            <p key={i} className="rounded-xl bg-neo-rain/15 px-2 py-1.5 text-sm font-semibold">
              {b.action}
              {b.why != null ? <span className="ml-2 font-mono font-normal text-neo-muted">{cell(b.why)}</span> : null}
            </p>
          );
        }
        return null;
      })}
    </div>
  );
}
