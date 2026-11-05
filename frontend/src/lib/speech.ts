/** India's 22 scheduled languages. Indic listening uses the Conformer sidecar. Speaking uses FastSpeech2. */

import { apiUrl } from "./config";

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
  { id: "mni", bcp: "mni-IN", name: "Manipuri", native: "ꯃꯤꯇꯩꯂꯣꯟ" },
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

/** Reply / input languages offered in the chat: 22 scheduled + Hinglish. */
export const REPLY_LANGS: { id: string; native: string }[] = [
  { id: "en", native: "English" },
  { id: "hinglish", native: "Hinglish" },
  ...SCHEDULED_LANGS.map((l) => ({ id: l.id, native: l.native })),
];

export function bcpForSpeech(id: string): string {
  if (id === "en" || id === "hinglish") return "en-IN";
  return SCHEDULED_LANGS.find((l) => l.id === id)?.bcp ?? "hi-IN";
}

export function replyOptionLabel(native: string, voiced: boolean): string {
  return voiced ? `${native} (voice)` : native;
}

export function voicedReplyIds(status: SpeechEngineStatus | null): Set<string> {
  const ids = new Set(status?.tts_langs || []);
  if (status?.english?.tts) {
    ids.add("en");
    ids.add("hinglish");
  }
  return ids;
}

export function defaultSpeechLang(ui: string): string {
  if (ui === "en" || ui === "hinglish") return ui;
  if (SCHEDULED_LANGS.some((l) => l.id === ui)) return ui;
  return "hi";
}

// Letter ranges only. U+0964 danda (।) and the digits in each block are not letters.
// A Tamil or Kannada sentence often ends with ।, which sits in the Devanagari block.
const SCRIPT_LANGS: { re: RegExp; langs: string[] }[] = [
  { re: /[\u0980-\u09E3\u09F0-\u09FE]/, langs: ["bn", "as", "mni"] },
  { re: /[\u0900-\u0963\u0970-\u097F]/, langs: ["hi", "mr", "ne", "kok", "mai", "sa", "doi", "brx"] },
  { re: /[\u0A01-\u0A65\u0A70-\u0A75]/, langs: ["pa"] },
  { re: /[\u0A81-\u0AE3\u0AF0-\u0AFF]/, langs: ["gu"] },
  { re: /[\u0B01-\u0B65\u0B70-\u0B77]/, langs: ["or"] },
  { re: /[\u0B82-\u0BE3\u0BF0-\u0BFA]/, langs: ["ta"] },
  { re: /[\u0C00-\u0C63\u0C70-\u0C7F]/, langs: ["te"] },
  { re: /[\u0C80-\u0CE3\u0CF0-\u0CFF]/, langs: ["kn"] },
  { re: /[\u0D00-\u0D63\u0D70-\u0D7F]/, langs: ["ml"] },
  { re: /[\u0600-\u06FF]/, langs: ["ur", "sd", "ks"] },
  { re: /[\u1C5A-\u1C7F]/, langs: ["sat"] },
  { re: /[\uABC0-\uABFF\uAAE0-\uAAFF]/, langs: ["mni"] },
];

function letterCount(re: RegExp, text: string): number {
  const found = text.match(new RegExp(re.source, "g"));
  return found ? found.length : 0;
}

export function detectSpeechLang(text: string, hint?: string): string {
  const blob = text || "";
  const ranked = SCRIPT_LANGS
    .map((row) => ({ langs: row.langs, n: letterCount(row.re, blob) }))
    .filter((row) => row.n > 0)
    .sort((a, b) => b.n - a.n);
  if (ranked.length) {
    const hinted = hint ? ranked.find((row) => row.langs.includes(hint)) : undefined;
    if (hinted && hinted.n >= ranked[0].n) return hint as string;
    return ranked[0].langs[0];
  }
  if (hint === "en" || hint === "hinglish") return hint;
  // Latin text is never read with an Indic voice.
  return "en";
}

export function hasIndicScript(text: string): boolean {
  return SCRIPT_LANGS.some((row) => letterCount(row.re, text || "") > 0);
}

function speechRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export type SpeechEngineStatus = {
  stt: boolean;
  tts: boolean;
  stt_langs: string[];
  tts_langs: string[];
  fallback?: string;
  english?: { stt: boolean; tts: boolean };
};

let sidecar: SpeechEngineStatus | null = null;

export function sidecarStatus(): SpeechEngineStatus | null {
  return sidecar;
}

export async function loadSpeechStatus(): Promise<SpeechEngineStatus | null> {
  try {
    const r = await fetch(apiUrl("/speech/status"));
    if (!r.ok) return sidecar;
    sidecar = (await r.json()) as SpeechEngineStatus;
    return sidecar;
  } catch {
    return sidecar;
  }
}

function webSpeechSupported(): { stt: boolean; tts: boolean } {
  if (typeof window === "undefined") return { stt: false, tts: false };
  return {
    stt: Boolean(speechRecognitionCtor()),
    tts: Boolean(window.speechSynthesis),
  };
}

export function speechSupported(): { stt: boolean; tts: boolean } {
  const web = webSpeechSupported();
  return {
    stt: web.stt || Boolean(sidecar?.stt) || Boolean(sidecar?.english?.stt),
    tts: web.tts || Boolean(sidecar?.tts) || Boolean(sidecar?.english?.tts),
  };
}

function useServerStt(langId: string): boolean {
  if (langId === "en" || langId === "hinglish" || langId === "auto") {
    return Boolean(sidecar?.english?.stt);
  }
  if (!sidecar?.stt) return false;
  return sidecar.stt_langs.includes(langId);
}

function useServerTts(langId: string): boolean {
  if (langId === "en" || langId === "hinglish") return Boolean(sidecar?.english?.tts);
  return Boolean(sidecar?.tts_langs?.includes(langId));
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

function floatTo16BitPcm(input: Float32Array): Int16Array {
  const out = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i] || 0));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

function resample(input: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate) return input;
  const ratio = fromRate / toRate;
  const n = Math.max(1, Math.round(input.length / ratio));
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const src = i * ratio;
    const i0 = Math.floor(src);
    const i1 = Math.min(i0 + 1, input.length - 1);
    const f = src - i0;
    out[i] = (input[i0] || 0) * (1 - f) + (input[i1] || 0) * f;
  }
  return out;
}

function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const pcm = floatTo16BitPcm(samples);
  const buf = new ArrayBuffer(44 + pcm.length * 2);
  const view = new DataView(buf);
  const write = (off: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i));
  };
  write(0, "RIFF");
  view.setUint32(4, 36 + pcm.length * 2, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, pcm.length * 2, true);
  new Int16Array(buf, 44).set(pcm);
  return new Blob([buf], { type: "audio/wav" });
}

function startSidecarDictation(
  langId: string,
  onText: (text: string, final: boolean) => void,
  onEnd: (err?: string) => void
): () => void {
  let stopped = false;
  let ctx: AudioContext | null = null;
  let stream: MediaStream | null = null;
  const chunks: Float32Array[] = [];
  const ac = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!ac || !navigator.mediaDevices?.getUserMedia) {
    onEnd("unsupported");
    return () => {};
  }
  const finish = async (err?: string) => {
    if (stopped) return;
    stopped = true;
    try {
      stream?.getTracks().forEach((t) => t.stop());
      await ctx?.close();
    } catch {
      /* ignore */
    }
    if (err) {
      onEnd(err);
      return;
    }
    const total = chunks.reduce((n, c) => n + c.length, 0);
    if (!total) {
      onEnd("no-speech");
      return;
    }
    const merged = new Float32Array(total);
    let o = 0;
    for (const c of chunks) {
      merged.set(c, o);
      o += c.length;
    }
    const rate = ctx?.sampleRate || 48000;
    const wav = encodeWav(resample(merged, rate, 16000), 16000);
    try {
      const fd = new FormData();
      fd.append("file", wav, "clip.wav");
      fd.append("language", langId);
      const r = await fetch(apiUrl("/speech/stt"), { method: "POST", body: fd });
      if (!r.ok) {
        onEnd(r.status === 501 || r.status === 503 ? "server" : "network");
        return;
      }
      const body = (await r.json()) as { text?: string };
      const text = (body.text || "").trim();
      if (text) onText(text, true);
      onEnd();
    } catch {
      onEnd("network");
    }
  };
  void navigator.mediaDevices
    .getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } })
    .then((ms) => {
      if (stopped) {
        ms.getTracks().forEach((t) => t.stop());
        return;
      }
      stream = ms;
      ctx = new ac();
      const src = ctx.createMediaStreamSource(ms);
      const node = ctx.createScriptProcessor(4096, 1, 1);
      node.onaudioprocess = (ev) => {
        chunks.push(new Float32Array(ev.inputBuffer.getChannelData(0)));
      };
      const mute = ctx.createGain();
      mute.gain.value = 0;
      src.connect(node);
      node.connect(mute);
      mute.connect(ctx.destination);
      window.setTimeout(() => void finish(), 20000);
    })
    .catch(() => onEnd("not-allowed"));
  return () => {
    void finish();
  };
}

export function startDictation(
  langId: string,
  onText: (text: string, final: boolean) => void,
  onEnd: (err?: string) => void,
  webLang?: string
): () => void {
  if (useServerStt(langId)) {
    return startSidecarDictation(langId, onText, onEnd);
  }
  const Ctor = speechRecognitionCtor();
  if (!Ctor) {
    onEnd("unsupported");
    return () => {};
  }
  const rec = new Ctor();
  rec.lang = bcpForSpeech(langId === "auto" ? webLang || "en" : langId);
  rec.interimResults = true;
  rec.continuous = true;
  rec.maxAlternatives = 1;
  let stopped = false;
  rec.onresult = (ev) => {
    let blob = "";
    const list = ev.results;
    for (let i = 0; i < list.length; i++) {
      blob += list[i]?.[0]?.transcript || "";
    }
    const last = list[list.length - 1];
    onText(blob, Boolean(last && (last as { isFinal?: boolean }).isFinal));
  };
  rec.onerror = (ev) => {
    const err = ev.error || "error";
    if (err === "no-speech" || err === "aborted") return;
    if (!stopped) onEnd(err);
  };
  rec.onend = () => {
    if (stopped) {
      onEnd();
      return;
    }
    try {
      rec.start();
    } catch {
      onEnd();
    }
  };
  rec.start();
  return () => {
    stopped = true;
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

let htmlAudio: HTMLAudioElement | null = null;
let audioCtx: AudioContext | null = null;
let audioNode: AudioBufferSourceNode | null = null;

const SILENT_WAV =
  "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";

function primeSpeaker(): void {
  // Runs inside the click. FastSpeech answers after that gesture, so playback has to
  // be unlocked here. A blocked play() used to fall through to the browser and report
  // that the Indic voice does not exist.
  if (typeof window === "undefined") return;
  const Ctor = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (Ctor) {
    if (!audioCtx || audioCtx.state === "closed") audioCtx = new Ctor();
    void audioCtx.resume();
    try {
      const silence = audioCtx.createBuffer(1, 1, audioCtx.sampleRate);
      const src = audioCtx.createBufferSource();
      src.buffer = silence;
      src.connect(audioCtx.destination);
      src.start();
    } catch {
      /* resume() was already called in this click */
    }
  }
  if (!htmlAudio) htmlAudio = new Audio();
  htmlAudio.src = SILENT_WAV;
  void htmlAudio.play().catch(() => undefined);
}

function stopBuffer(): void {
  if (!audioNode) return;
  try {
    audioNode.onended = null;
    audioNode.stop();
  } catch {
    /* already stopped */
  }
  try {
    audioNode.disconnect();
  } catch {
    /* already disconnected */
  }
  audioNode = null;
}

function playElement(blob: Blob, onEnd?: () => void): Promise<boolean> {
  const el = htmlAudio;
  if (!el) return Promise.resolve(false);
  const url = URL.createObjectURL(blob);
  el.src = url;
  el.onended = () => {
    URL.revokeObjectURL(url);
    if (htmlAudio === el) onEnd?.();
  };
  el.onerror = () => {
    URL.revokeObjectURL(url);
  };
  return el.play().then(() => true).catch(() => {
    URL.revokeObjectURL(url);
    return false;
  });
}

async function playWav(blob: Blob, onEnd?: () => void): Promise<boolean> {
  const ctx = audioCtx;
  if (ctx) {
    if (ctx.state === "suspended") {
      try {
        await ctx.resume();
      } catch {
        /* the element unlocked in the click is the backup */
      }
    }
    if (ctx.state === "running") {
      try {
        const decoded = await ctx.decodeAudioData((await blob.arrayBuffer()).slice(0));
        stopBuffer();
        const node = ctx.createBufferSource();
        node.buffer = decoded;
        node.connect(ctx.destination);
        node.onended = () => {
          if (audioNode === node) audioNode = null;
          onEnd?.();
        };
        audioNode = node;
        node.start();
        return true;
      } catch {
        /* not a decodable WAV; try the element unlocked in the click */
      }
    }
  }
  return playElement(blob, onEnd);
}

function speakServer(text: string, lang: string, onEnd?: () => void): Promise<boolean> {
  primeSpeaker();
  stopBuffer();
  const code = lang === "hinglish" ? "en" : lang;
  return fetch(apiUrl("/speech/tts"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: plainForSpeech(text), language: code }),
  })
    .then(async (r) => {
      if (!r.ok) throw new Error(String(r.status));
      return r.blob();
    })
    .then((blob) => playWav(blob, onEnd))
    .catch(() => false);
}

function sharesScript(a: string, b: string): boolean {
  return SCRIPT_LANGS.some((row) => row.langs.includes(a) && row.langs.includes(b));
}

function langForSpeech(text: string, hint: string): string {
  const detected = detectSpeechLang(text, hint);
  if ((hint === "en" || hint === "hinglish") && detected === "en") return hint;
  if (useServerTts(detected)) return detected;
  // A picked FastSpeech language stays on that voice when detection lands on a
  // sibling with no voice (Dogri next to Hindi, Sindhi next to Urdu).
  if (useServerTts(hint) && (detected === hint || sharesScript(hint, detected))) return hint;
  return detected;
}

export type SpeakMode = "native" | "none" | "down";

/**
 * Read a reply aloud in its own language. An Indic reply is never swapped for the
 * English draft. With no voice for that language, nothing is spoken (mode "none").
 */
export function speakText(
  text: string,
  langHint: string,
  onEnd?: () => void,
  onMode?: (mode: SpeakMode) => void
): void {
  primeSpeaker();
  const plain = plainForSpeech(text);
  const lang = langForSpeech(plain, langHint);
  const readInBrowser = () => {
    if (typeof window === "undefined" || !window.speechSynthesis) {
      onMode?.("none");
      onEnd?.();
      return;
    }
    const synth = window.speechSynthesis;
    synth.cancel();
    void loadVoices().then((voices) => {
      const spoken = plain;
      const voice = pickVoice(voices, lang);
      if (!voice && lang !== "en" && lang !== "hinglish") {
        onMode?.("none");
        onEnd?.();
        return;
      }
      onMode?.("native");
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
  };
  if (useServerTts(lang)) {
    onMode?.("native");
    void speakServer(plain, lang, onEnd).then((ok) => {
      if (ok) return;
      // The menu already said this language has a voice. The browser does not,
      // and falling through to it is what showed "No voice for this language".
      onMode?.("down");
      onEnd?.();
    });
    return;
  }
  readInBrowser();
}

export function stopSpeaking(): void {
  stopBuffer();
  if (htmlAudio) {
    try {
      htmlAudio.pause();
      htmlAudio.src = "";
    } catch {
      /* ignore */
    }
    htmlAudio = null;
  }
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
