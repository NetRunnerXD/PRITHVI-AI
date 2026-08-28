"use client";

import { useEffect } from "react";
import { applyTheme, readSettings, useApp } from "@/lib/store";

export function ThemeBoot() {
  const setSettings = useApp((s) => s.setSettings);
  const setTab = useApp((s) => s.setTab);
  const setSidebarOpen = useApp((s) => s.setSidebarOpen);
  useEffect(() => {
    const s = readSettings();
    setSettings(s);
    applyTheme(s);
    setTab(s.defaultTab);
    if (window.matchMedia("(max-width: 1023px)").matches) setSidebarOpen(false);
  }, [setSettings, setTab, setSidebarOpen]);

  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const id = window.setTimeout(() => {
      void navigator.serviceWorker.register("/sw.js").catch(() => undefined);
    }, 800);
    return () => window.clearTimeout(id);
  }, []);

  return null;
}
