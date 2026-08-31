"use client";

import { useEffect, useState } from "react";
import { searchPlaces } from "@/lib/api";
import type { Location } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";
import { useApp } from "@/lib/store";

export function DistrictSearch({
  locale,
  onPick,
}: {
  locale: Locale;
  onPick: (l: Location) => void;
}) {
  const { recent } = useApp();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Location[]>([]);
  const [focus, setFocus] = useState(false);
  useEffect(() => {
    if (q.trim().length < 2) {
      setHits([]);
      return;
    }
    const id = setTimeout(() => {
      searchPlaces(q).then(setHits);
    }, 180);
    return () => clearTimeout(id);
  }, [q]);
  return (
    <div className="relative min-w-[220px] flex-1">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={COPY[locale].search}
        className="neo-in w-full px-3 py-2 text-sm outline-none"
        data-testid="district-search"
        onFocus={() => setFocus(true)}
        onBlur={() => window.setTimeout(() => setFocus(false), 180)}
      />
      {focus && !hits.length && recent.length > 0 && q.trim().length < 2 ? (
        <ul className="neo absolute z-[9999] mt-2 max-h-64 w-full overflow-auto">
          {recent.slice(0, 5).map((h) => (
            <li key={h.id}>
              <button
                className="w-full px-3 py-2 text-left text-sm hover:text-neo-accent"
                onMouseDown={() => {
                  onPick(h);
                  setQ(h.label);
                }}
              >
                {h.label}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {hits.length > 0 && (
        <ul className="neo absolute z-[9999] mt-2 max-h-64 w-full overflow-auto">
          {hits.map((h) => (
            <li key={h.id}>
              <button
                className="w-full px-3 py-2 text-left text-sm hover:text-neo-accent"
                onClick={() => {
                  onPick(h);
                  setQ(h.label);
                  setHits([]);
                }}
              >
                <span>{h.label}</span>
                {h.place_kind && h.place_kind !== "district" ? (
                  <span className="ml-2 text-[10px] uppercase tracking-wide text-neo-muted">{h.place_kind}</span>
                ) : (
                  <span className="ml-2 text-[10px] uppercase tracking-wide text-neo-muted">district</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
