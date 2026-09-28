import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

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

// Longest a single request may take. The free API host can need about a minute to start
// after being idle; beyond this the request is abandoned with a clear message.
export const REQUEST_TIMEOUT_MS = 90_000;

function withTimeout(request: Request): Promise<Response> {
  // Older browsers without these helpers still work, just without the time limit.
  if (typeof AbortSignal.timeout !== "function" || typeof AbortSignal.any !== "function") return fetch(request);
  return fetch(request, { signal: AbortSignal.any([request.signal, AbortSignal.timeout(REQUEST_TIMEOUT_MS)]) });
}

export const api = createClient<paths>({ baseUrl, fetch: withTimeout });
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
  } catch (e) {
    const name = e instanceof Error ? e.name : "";
    // Cancelled by the caller (e.g. leaving the page): not an error to show.
    if (name === "AbortError") throw e;
    if (name === "TimeoutError") {
      throw new ApiError(
        `The Ardentum API did not answer within ${REQUEST_TIMEOUT_MS / 1000} seconds. It may be starting up after a quiet period; try again in a minute.`,
        0,
        "timeout",
      );
    }
    throw new ApiError(
      "Cannot reach the Ardentum API. If it has been idle it can take up to a minute to start; check your connection and try again shortly.",
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

export type JobKind = components["schemas"]["JobCreate"]["kind"];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Run a calculation as a background job and wait for its result.
 * The server holds each poll open for up to 20 s, which also keeps serverless CPU
 * allocated while the job runs. Brief network failures are retried.
 */
export async function runJob<T>(kind: JobKind, request: unknown, signal?: AbortSignal): Promise<T> {
  let job = await unwrap(api.POST("/api/v1/jobs", { body: { kind, request: request as Record<string, never> }, signal }));
  let failures = 0;
  while (job.status === "queued" || job.status === "running") {
    try {
      job = await unwrap(api.GET("/api/v1/jobs/{job_id}", { params: { path: { job_id: job.id }, query: { wait: 20 } }, signal }));
      failures = 0;
    } catch (e) {
      if (signal?.aborted || !(e instanceof ApiError) || e.status !== 0 || ++failures > 3) throw e;
      await sleep(1000 * failures);
    }
  }
  if (job.status === "failed") {
    throw new ApiError(job.error?.message ?? "The calculation failed.", job.error?.status ?? 500, job.error?.type ?? "job_failed");
  }
  return job.result as T;
}
