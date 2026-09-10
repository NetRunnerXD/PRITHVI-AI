"use client";

import { useEffect, useRef, useState } from "react";
import { searchPlaces } from "@/lib/api";
import type { Location } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";
import { useApp } from "@/lib/store";

export function DistrictSearch({
  locale,
  onPick,
  disabled = false,
}: {
  locale: Locale;
  onPick: (l: Location) => void;
  disabled?: boolean;
}) {
  const { recent } = useApp();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Location[]>([]);
  const [focus, setFocus] = useState(false);
  const [searching, setSearching] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState<number>(-1);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const needle = q.trim();
    if (needle.length < 2) {
      setHits([]);
      setSearching(false);
      setSelectedIndex(-1);
      return;
    }
    setSearching(true);
    const ac = new AbortController();
    const id = setTimeout(() => {
      // 1. Fast local gazetteer search
      searchPlaces(needle, ac.signal, true)
        .then((rows) => {
          if (!ac.signal.aborted && rows.length) {
            setHits(rows);
            setSelectedIndex(0);
          }
        })
        .catch(() => undefined);
      // 2. Full geocoded search
      searchPlaces(needle, ac.signal, false)
        .then((rows) => {
          if (!ac.signal.aborted) {
            setHits(rows);
            if (rows.length > 0) setSelectedIndex((prev) => (prev < 0 ? 0 : Math.min(prev, rows.length - 1)));
            setSearching(false);
          }
        })
        .catch(() => {
          if (!ac.signal.aborted) setSearching(false);
        });
    }, 100);
    return () => {
      clearTimeout(id);
      ac.abort();
    };
  }, [q]);

  const handleSelect = (h: Location) => {
    setQ(h.label);
    setHits([]);
    setFocus(false);
    inputRef.current?.blur();
    onPick(h);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (hits.length > 0) {
        setSelectedIndex((prev) => (prev + 1) % hits.length);
      } else if (recent.length > 0 && q.trim().length < 2) {
        setSelectedIndex((prev) => (prev + 1) % Math.min(5, recent.length));
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (hits.length > 0) {
        setSelectedIndex((prev) => (prev <= 0 ? hits.length - 1 : prev - 1));
      } else if (recent.length > 0 && q.trim().length < 2) {
        const maxR = Math.min(5, recent.length);
        setSelectedIndex((prev) => (prev <= 0 ? maxR - 1 : prev - 1));
      }
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (hits.length > 0) {
        const item = hits[selectedIndex >= 0 ? selectedIndex : 0];
        if (item) handleSelect(item);
      } else if (recent.length > 0 && q.trim().length < 2 && selectedIndex >= 0) {
        const item = recent[selectedIndex];
        if (item) handleSelect(item);
      } else if (q.trim().length >= 2) {
        // Fallback: trigger search on enter immediately
        void searchPlaces(q.trim(), undefined, false).then((rows) => {
          if (rows.length > 0) {
            handleSelect(rows[0]);
          }
        });
      }
    } else if (e.key === "Escape") {
      setFocus(false);
      inputRef.current?.blur();
    }
  };

  return (
    <div className="relative min-w-[120px] sm:min-w-[220px] flex-1">
      <div className="relative flex items-center">
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setFocus(true);
          }}
          onKeyDown={handleKeyDown}
          placeholder={COPY[locale].search}
          className="neo-in w-full pl-3 pr-8 py-2 text-sm outline-none transition-all disabled:opacity-50"
          data-testid="district-search"
          disabled={disabled}
          onFocus={() => setFocus(true)}
          onBlur={() => window.setTimeout(() => setFocus(false), 200)}
        />
        {searching ? (
          <div className="absolute right-2.5 flex items-center justify-center pointer-events-none">
            <div className="h-3.5 w-3.5 rounded-full border-2 border-neo-accent border-t-transparent animate-spin" />
          </div>
        ) : q ? (
          <button
            type="button"
            className="absolute right-2.5 text-xs text-neo-muted hover:text-neo-text transition"
            onClick={() => {
              setQ("");
              setHits([]);
              inputRef.current?.focus();
            }}
          >
            ✕
          </button>
        ) : null}
      </div>

      {/* Recents Dropdown */}
      {focus && !hits.length && recent.length > 0 && q.trim().length < 2 ? (
        <ul className="absolute left-0 right-0 z-[9999] mt-1.5 max-h-64 overflow-y-auto rounded-2xl border border-[var(--line)] bg-[var(--card)] shadow-2xl p-1 divide-y divide-[color-mix(in_srgb,var(--line)_40%,transparent)]">
          <li className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-neo-muted">
            {locale === "hi" ? "हाल के स्थान" : locale === "bn" ? "সাম্প্রতিক স্থান" : "Recent Places"}
          </li>
          {recent.slice(0, 5).map((h, idx) => (
            <li key={h.id}>
              <button
                type="button"
                className={`w-full px-3 py-2 text-left text-sm font-medium rounded-xl transition-colors ${
                  selectedIndex === idx
                    ? "bg-neo-accent text-white"
                    : "hover:text-neo-accent hover:bg-[color-mix(in_srgb,var(--accent)_8%,transparent)]"
                }`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  handleSelect(h);
                }}
              >
                {h.label}
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {/* Search Hits Dropdown */}
      {focus && hits.length > 0 && (
        <ul className="absolute left-0 right-0 z-[9999] mt-1.5 max-h-64 overflow-y-auto rounded-2xl border border-[var(--line)] bg-[var(--card)] shadow-2xl p-1 divide-y divide-[color-mix(in_srgb,var(--line)_40%,transparent)]">
          {hits.map((h, idx) => (
            <li key={h.id}>
              <button
                type="button"
                className={`w-full px-3 py-2 text-left text-sm font-medium rounded-xl transition-colors flex items-center justify-between ${
                  selectedIndex === idx
                    ? "bg-neo-accent text-white"
                    : "hover:text-neo-accent hover:bg-[color-mix(in_srgb,var(--accent)_8%,transparent)]"
                }`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  handleSelect(h);
                }}
              >
                <span className="truncate">{h.label}</span>
                <span
                  className={`ml-2 shrink-0 rounded-md px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider ${
                    selectedIndex === idx
                      ? "bg-white/20 text-white"
                      : "bg-[color-mix(in_srgb,var(--line)_70%,transparent)] text-neo-muted"
                  }`}
                >
                  {h.place_kind || "district"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
