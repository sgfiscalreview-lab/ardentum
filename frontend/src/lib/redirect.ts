const FALLBACK = "/app";
const BASE = "https://ardentum.invalid";

/**
 * A path on this site to return to after sign-in; anything else becomes the workspace.
 * Browsers read "//host", "/\host" and paths with tabs or line breaks in them as another
 * site, so only a plain path that stays on this origin once parsed is kept.
 */
export function safeNext(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || next.includes("\\")) return FALLBACK;
  for (const ch of next) {
    const code = ch.charCodeAt(0);
    if (code < 0x20 || code === 0x7f) return FALLBACK;
  }
  try {
    const url = new URL(next, BASE);
    if (url.origin !== BASE) return FALLBACK;
    return url.pathname + url.search + url.hash;
  } catch {
    return FALLBACK;
  }
}
