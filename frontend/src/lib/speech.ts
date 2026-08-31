/** India's 22 scheduled (official) languages for Web Speech STT/TTS. */

export type ScheduledLang = {
  id: string;
  bcp: string;
  name: string;
  native: string;
};

export const SCHEDULED_LANGS: ScheduledLang[] = [
  { id: "as", bcp: "as-IN", name: "Assamese", native: "অসমীয়া" },
  { id: "bn", bcp: "bn-IN", name: "Bengali", native: "বাংলা" },
  { id: "brx", bcp: "brx-IN", name: "Bodo", native: "बड़ो" },
  { id: "doi", bcp: "doi-IN", name: "Dogri", native: "डोगरी" },
  { id: "gu", bcp: "gu-IN", name: "Gujarati", native: "ગુજરાતી" },
  { id: "hi", bcp: "hi-IN", name: "Hindi", native: "हिन्दी" },
  { id: "kn", bcp: "kn-IN", name: "Kannada", native: "ಕನ್ನಡ" },
  { id: "ks", bcp: "ks-IN", name: "Kashmiri", native: "کٲشُر" },
  { id: "kok", bcp: "kok-IN", name: "Konkani", native: "कोंकणी" },
  { id: "mai", bcp: "mai-IN", name: "Maithili", native: "मैथिली" },
  { id: "ml", bcp: "ml-IN", name: "Malayalam", native: "മലയാളം" },
  { id: "mni", bcp: "mni-IN", name: "Manipuri", native: "মৈতৈলোন্" },
  { id: "mr", bcp: "mr-IN", name: "Marathi", native: "मराठी" },
  { id: "ne", bcp: "ne-NP", name: "Nepali", native: "नेपाली" },
  { id: "or", bcp: "or-IN", name: "Odia", native: "ଓଡ଼ିଆ" },
  { id: "pa", bcp: "pa-IN", name: "Punjabi", native: "ਪੰਜਾਬੀ" },
  { id: "sa", bcp: "sa-IN", name: "Sanskrit", native: "संस्कृतम्" },
  { id: "sat", bcp: "sat-IN", name: "Santali", native: "ᱥᱟᱱᱛᱟᱲᱤ" },
  { id: "sd", bcp: "sd-IN", name: "Sindhi", native: "سنڌي" },
  { id: "ta", bcp: "ta-IN", name: "Tamil", native: "தமிழ்" },
  { id: "te", bcp: "te-IN", name: "Telugu", native: "తెలుగు" },
  { id: "ur", bcp: "ur-IN", name: "Urdu", native: "اردو" },
];

export function bcpForSpeech(id: string): string {
  if (id === "en") return "en-IN";
  return SCHEDULED_LANGS.find((l) => l.id === id)?.bcp ?? "hi-IN";
}

export function defaultSpeechLang(ui: string): string {
  if (ui === "en") return "en";
  if (SCHEDULED_LANGS.some((l) => l.id === ui)) return ui;
  return "hi";
}

const SCRIPT_LANGS: { re: RegExp; langs: string[] }[] = [
  { re: /[\u0980-\u09FF]/, langs: ["bn", "as", "mni"] },
  { re: /[\u0900-\u097F]/, langs: ["hi", "mr", "ne", "kok", "mai", "sa", "doi", "brx"] },
  { re: /[\u0A00-\u0A7F]/, langs: ["pa"] },
  { re: /[\u0A80-\u0AFF]/, langs: ["gu"] },
  { re: /[\u0B00-\u0B7F]/, langs: ["or"] },
  { re: /[\u0B80-\u0BFF]/, langs: ["ta"] },
  { re: /[\u0C00-\u0C7F]/, langs: ["te"] },
  { re: /[\u0C80-\u0CFF]/, langs: ["kn"] },
  { re: /[\u0D00-\u0D7F]/, langs: ["ml"] },
  { re: /[\u0600-\u06FF]/, langs: ["ur", "sd", "ks"] },
  { re: /[\u1C50-\u1C7F]/, langs: ["sat"] },
];

export function detectSpeechLang(text: string, hint?: string): string {
  for (const row of SCRIPT_LANGS) {
    if (row.re.test(text || "")) {
      if (hint && row.langs.includes(hint)) return hint;
      return row.langs[0];
    }
  }
  if (hint === "en" || (hint && SCHEDULED_LANGS.some((l) => l.id === hint))) return hint;
  return "en";
}

export function hasIndicScript(text: string): boolean {
  return SCRIPT_LANGS.some((row) => row.re.test(text || ""));
}

function speechRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export function speechSupported(): { stt: boolean; tts: boolean } {
  if (typeof window === "undefined") return { stt: false, tts: false };
  return {
    stt: Boolean(speechRecognitionCtor()),
    tts: Boolean(window.speechSynthesis),
  };
}

type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((ev: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal?: boolean }> }) => void) | null;
  onerror: ((ev: { error?: string }) => void) | null;
  onend: (() => void) | null;
};

export function startDictation(
  langId: string,
  onText: (text: string, final: boolean) => void,
  onEnd: (err?: string) => void
): () => void {
  const Ctor = speechRecognitionCtor();
  if (!Ctor) {
    onEnd("unsupported");
    return () => {};
  }
  const rec = new Ctor();
  rec.lang = bcpForSpeech(langId);
  rec.interimResults = true;
  rec.continuous = false;
  rec.maxAlternatives = 1;
  rec.onresult = (ev) => {
    const last = ev.results[ev.results.length - 1];
    const piece = last?.[0]?.transcript || "";
    onText(piece, Boolean(last && (last as { isFinal?: boolean }).isFinal));
  };
  rec.onerror = (ev) => onEnd(ev.error || "error");
  rec.onend = () => onEnd();
  rec.start();
  return () => {
    try {
      rec.abort();
    } catch {
      /* ignore */
    }
  };
}

function normalizeLangTag(tag: string): string {
  return (tag || "").toLowerCase().replace(/_/g, "-");
}

function isEnglishVoice(v: SpeechSynthesisVoice): boolean {
  const tag = normalizeLangTag(v.lang);
  return tag.startsWith("en") || /(english|david|zira|mark|aria|guy)/i.test(v.name);
}

export function pickVoice(voices: SpeechSynthesisVoice[], langId: string): SpeechSynthesisVoice | null {
  if (!voices.length) return null;
  const bcp = normalizeLangTag(bcpForSpeech(langId));
  const prefix = bcp.split("-")[0];
  const scored = voices
    .map((v) => {
      const tag = normalizeLangTag(v.lang);
      let score = 0;
      if (tag === bcp) score = 100;
      else if (tag.startsWith(`${prefix}-`)) score = 85;
      else if (tag === prefix) score = 80;
      else if (new RegExp(`\\b${prefix}\\b`, "i").test(v.name)) score = 70;
      if (langId !== "en" && isEnglishVoice(v)) score = Math.min(score, 5);
      return { v, score };
    })
    .filter((row) => row.score >= 70)
    .sort((a, b) => b.score - a.score);
  return scored[0]?.v || null;
}

function loadVoices(): Promise<SpeechSynthesisVoice[]> {
  if (typeof window === "undefined" || !window.speechSynthesis) return Promise.resolve([]);
  const read = () => window.speechSynthesis.getVoices() || [];
  const now = read();
  if (now.length) return Promise.resolve(now);
  return new Promise((resolve) => {
    const finish = () => {
      window.speechSynthesis.removeEventListener("voiceschanged", finish);
      resolve(read());
    };
    window.speechSynthesis.addEventListener("voiceschanged", finish);
    window.setTimeout(finish, 700);
  });
}

function splitForSpeech(text: string): string[] {
  const blob = (text || "").trim();
  if (blob.length <= 220) return blob ? [blob] : [];
  const parts = blob.split(/(?<=[।.!?])\s+/);
  const out: string[] = [];
  let buf = "";
  for (const p of parts) {
    if ((buf + " " + p).trim().length > 220 && buf) {
      out.push(buf.trim());
      buf = p;
    } else {
      buf = buf ? `${buf} ${p}` : p;
    }
  }
  if (buf.trim()) out.push(buf.trim());
  return out.length ? out : [blob];
}

export function speakText(
  text: string,
  langHint: string,
  onEnd?: () => void,
  englishFallback?: string
): void {
  if (typeof window === "undefined" || !window.speechSynthesis) {
    onEnd?.();
    return;
  }
  const synth = window.speechSynthesis;
  synth.cancel();
  void loadVoices().then((voices) => {
    const plain = plainForSpeech(text);
    let lang = detectSpeechLang(plain, langHint);
    let spoken = plain;
    let voice = pickVoice(voices, lang);
    if (hasIndicScript(plain) && !voice && englishFallback) {
      spoken = plainForSpeech(englishFallback);
      lang = "en";
      voice = pickVoice(voices, "en");
    }
    if (!voice && lang !== "en") {
      voice = pickVoice(voices, "hi") || pickVoice(voices, "bn");
    }
    const chunks = splitForSpeech(spoken);
    if (!chunks.length) {
      onEnd?.();
      return;
    }
    let i = 0;
    const next = () => {
      if (i >= chunks.length) {
        onEnd?.();
        return;
      }
      const u = new SpeechSynthesisUtterance(chunks[i++]);
      u.lang = bcpForSpeech(lang);
      u.rate = 0.95;
      if (voice) u.voice = voice;
      u.onend = next;
      u.onerror = () => next();
      synth.speak(u);
    };
    window.setTimeout(next, 60);
  });
}

export function stopSpeaking(): void {
  if (typeof window !== "undefined" && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}

export function plainForSpeech(md: string): string {
  return (md || "")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[*_~]+/g, "")
    .replace(/\s+/g, " ")
    .trim();
}
