/** Load a theme's extra Google font families only when that theme is used.
 * The default (midnight) fonts are linked once in layout.tsx; the old global @import pulled
 * 8 families (~40 font files) render-blocking on every page. */

const EXTRA: Record<string, string[]> = {
  sand: ["Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;0,6..72,700;1,6..72,400", "Instrument+Sans:wght@400;500;600;700"],
  monsoon: ["Space+Grotesk:wght@400;500;600;700"],
  ocean: ["Fira+Code:wght@400;500;600", "Space+Grotesk:wght@400;500;600;700"],
  mist: ["Instrument+Sans:wght@400;500;600;700"],
  dusk_mist: ["Instrument+Sans:wght@400;500;600;700", "Space+Grotesk:wght@400;500;600;700"],
  contrast: ["Space+Grotesk:wght@400;500;600;700"],
};

const loaded = new Set<string>();

export function ensureThemeFonts(theme: string | undefined) {
  if (typeof document === "undefined" || !theme) return;
  for (const fam of EXTRA[theme] || []) {
    if (loaded.has(fam)) continue;
    loaded.add(fam);
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `https://fonts.googleapis.com/css2?family=${fam}&display=swap`;
    document.head.appendChild(link);
  }
}
