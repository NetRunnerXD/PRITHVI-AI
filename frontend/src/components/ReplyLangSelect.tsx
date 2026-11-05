"use client";

import { useEffect, useState } from "react";

import { loadSpeechStatus, REPLY_LANGS, replyOptionLabel, voicedReplyIds } from "@/lib/speech";

/** One compact picker: reply language, dictation language and the input-language hint. */
export function ReplyLangSelect({
  value,
  onChange,
  autoLabel = "Auto",
  className = "",
}: {
  value: string;
  onChange: (v: string) => void;
  autoLabel?: string;
  className?: string;
}) {
  const [voiced, setVoiced] = useState<Set<string>>(new Set());

  useEffect(() => {
    let live = true;
    void loadSpeechStatus().then((status) => {
      if (live) setVoiced(voicedReplyIds(status));
    });
    return () => {
      live = false;
    };
  }, []);

  return (
    <select
      value={value || "auto"}
      onChange={(e) => onChange(e.target.value)}
      className={className}
      aria-label="Language"
      title="Language"
      data-testid="reply-lang"
    >
      <option value="auto">{autoLabel}</option>
      {REPLY_LANGS.map((l) => (
        <option key={l.id} value={l.id}>
          {replyOptionLabel(l.native, voiced.has(l.id))}
        </option>
      ))}
    </select>
  );
}
