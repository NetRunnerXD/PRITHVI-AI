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

/**
 * Optional device-side translation. Not on the send path: the server translates the
 * question itself. The source is detected from the text, never taken from the UI locale.
 */
export async function questionToEnglish(message: string, inputLang?: string): Promise<string | undefined> {
  if (!message.trim() || !/[^\u0000-\u024F]/.test(message)) return undefined;
  const src = inputLang && /^[a-z]{2}$/.test(inputLang) ? inputLang : "auto";
  return (await translateClient(message, src, "en")) || undefined;
}
