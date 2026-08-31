"use client";

import { useEffect, useState } from "react";
import { COPY } from "@/i18n/copy";
import { API_BASE } from "@/lib/config";
import { OM_TOKEN_KEY, startOmRelay } from "@/lib/omRelay";
import { useApp } from "@/lib/store";

export function OmRelay() {
  const locale = useApp((s) => s.locale);
  const t = COPY[locale];
  const [on, setOn] = useState(false);
  useEffect(() => {
    const token = typeof window !== "undefined" ? window.localStorage.getItem(OM_TOKEN_KEY) || "" : "";
    if (!token) return;
    return startOmRelay(API_BASE, token, setOn);
  }, []);
  if (!on) return null;
  return (
    <p className="fixed bottom-2 left-2 z-40 rounded-full bg-[var(--card)] px-3 py-1 text-[10px] uppercase tracking-widest text-neo-muted shadow">
      {t.omRelayOn}
    </p>
  );
}
