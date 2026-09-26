import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "./schema";

/** Error returned by the Ardentum API, carrying the server's user-facing message. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly type: string,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let tokenProvider: () => Promise<string | null> = async () => null;

/** Registered by the auth provider so every request carries the current token. */
export function setTokenProvider(fn: () => Promise<string | null>): void {
  tokenProvider = fn;
}

const authMiddleware: Middleware = {
  async onRequest({ request }) {
    const token = await tokenProvider();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
};

// NEXT_PUBLIC_API_BASE (static hosting): the browser calls the API origin directly.
// Empty (Node server / dev): relative URLs, proxied to the backend by next.config.ts.
const baseUrl =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ??
  (typeof window === "undefined" ? (process.env.API_URL ?? "http://localhost:8000") : "");

export const api = createClient<paths>({ baseUrl });
api.use(authMiddleware);

interface ErrorEnvelope {
  error?: { type?: string; message?: string; details?: unknown };
}

/** Unwrap an openapi-fetch result, converting error envelopes into ApiError. */
export async function unwrap<T>(
  promise: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result: { data?: T; error?: unknown; response: Response };
  try {
    result = await promise;
  } catch {
    throw new ApiError(
      "Cannot reach the Ardentum API. Check your connection and that the server is running.",
      0,
      "network_error",
    );
  }
  const { data, error, response } = result;
  if (response.ok && data !== undefined) return data;
  if (response.ok && response.status === 204) return undefined as T;
  const env = (error ?? {}) as ErrorEnvelope;
  throw new ApiError(
    env.error?.message ?? `Request failed (HTTP ${response.status}).`,
    response.status,
    env.error?.type ?? "http_error",
    env.error?.details,
  );
}
