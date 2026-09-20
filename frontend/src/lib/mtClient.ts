/** Browser MyMemory (and gtx when CORS allows). No keys. */

const MYMEMORY = "https://api.mymemory.translated.net/get";

export async function translateClient(text: string, src: string, tgt: string): Promise<string | null> {
  const blob = (text || "").trim();
  if (!blob) return null;
  if (src === tgt) return blob;
  try {
    const q = new URLSearchParams({
      q: blob.slice(0, 450),
      langpair: `${src === "auto" ? "Autodetect" : src}|${tgt}`,
    });
    const r = await fetch(`${MYMEMORY}?${q}`);
    if (!r.ok) return null;
    const data = await r.json();
    const piece = data?.responseData?.translatedText;
    const status = data?.responseStatus;
    if ((status !== 200 && status !== "200") || !piece) return null;
    if (String(piece).toLowerCase().startsWith("query length limit")) return null;
    return String(piece).trim() || null;
  } catch {
    return null;
  }
}

export async function questionToEnglish(message: string, locale: string): Promise<string | undefined> {
  const loc = (locale || "en").slice(0, 2).toLowerCase();
  if (loc === "en" || !message.trim()) return undefined;
  return (await translateClient(message, loc === "auto" ? "auto" : loc, "en")) || undefined;
}
