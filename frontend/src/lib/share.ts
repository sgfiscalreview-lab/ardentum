/**
 * Shareable links. The workspace settings (and the calculation on the page being shared)
 * travel in the link's fragment, the part after "#", which browsers never send to a
 * server: nothing is stored anywhere, and opening the link recomputes the same result
 * from the same inputs. The JSON is deflate-compressed and base64url-encoded.
 */

export const SHARE_PREFIX = "#share=";
/** Largest decoded payload accepted; real settings are a few kilobytes. */
export const MAX_SHARE_BYTES = 200_000;

/** Pages whose last calculation travels with a link opened on them. */
export const PAGE_REQUESTS: Record<string, string[]> = {
  "/app/analytics": ["analytics"],
  "/app/optimise": ["optimise"],
  "/app/frontier": ["frontier", "frontier_cvar"],
  "/app/esg": ["esg"],
  "/app/simulate": ["simulate"],
  "/app/backtest": ["backtest"],
  "/app/compare": ["compare"],
  "/app/crises": ["stress"],
  "/app/factors": ["factors"],
  // Not "/app/trades": a trade list holds the amounts someone owns; a link should not.
};

function toBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(text: string): Uint8Array {
  const b64 = text.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(b64 + "=".repeat((4 - (b64.length % 4)) % 4));
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}

async function pipe(bytes: Uint8Array, stream: CompressionStream | DecompressionStream, limit: number): Promise<Uint8Array> {
  const source = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(bytes);
      controller.close();
    },
  });
  const reader = source.pipeThrough(stream as TransformStream<Uint8Array, Uint8Array>).getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.length;
    if (size > limit) {
      await reader.cancel();
      throw new Error("Shared settings are too large.");
    }
    chunks.push(value);
  }
  const out = new Uint8Array(size);
  let at = 0;
  for (const c of chunks) {
    out.set(c, at);
    at += c.length;
  }
  return out;
}

/** The fragment ("#share=...") for a payload. */
export async function encodeShare(payload: unknown): Promise<string> {
  const json = new TextEncoder().encode(JSON.stringify(payload));
  const packed = await pipe(json, new CompressionStream("deflate-raw"), MAX_SHARE_BYTES);
  return SHARE_PREFIX + toBase64Url(packed);
}

/** The payload in a fragment, or null when there is none; throws if it is damaged. */
export async function decodeShare(fragment: string): Promise<unknown> {
  if (!fragment.startsWith(SHARE_PREFIX)) return null;
  const packed = fromBase64Url(fragment.slice(SHARE_PREFIX.length));
  const json = await pipe(packed, new DecompressionStream("deflate-raw"), MAX_SHARE_BYTES);
  return JSON.parse(new TextDecoder().decode(json)) as unknown;
}
