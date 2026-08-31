"use client";

import { useEffect, useState } from "react";
import { COPY } from "@/i18n/copy";
import { useApp } from "@/lib/store";
import { ChatDock } from "./ChatDock";
import { IconAdvisor } from "./Icons";

export function ChatFloat() {
  const { locale, setTab } = useApp();
  const t = COPY[locale];
  const [open, setOpen] = useState(false);
  const [bounce, setBounce] = useState(true);

  useEffect(() => {
    const id = window.setTimeout(() => setBounce(false), 4200);
    return () => window.clearTimeout(id);
  }, []);

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[1200] flex flex-col items-end gap-2">
      {open ? (
        <div className="pointer-events-auto w-[min(100vw-1.5rem,24rem)] overflow-hidden rounded-organ shadow-neo">
          <ChatDock compact />
        </div>
      ) : null}
      <button
        type="button"
        className={`pointer-events-auto flex h-14 w-14 items-center justify-center rounded-full bg-neo-accent text-white shadow-neo ${
          bounce ? "assistant-bob" : ""
        }`}
        onClick={() => setOpen((v) => !v)}
        title={t.assistant}
        aria-label={t.assistant}
      >
        <IconAdvisor className="h-6 w-6" />
      </button>
    </div>
  );
}
