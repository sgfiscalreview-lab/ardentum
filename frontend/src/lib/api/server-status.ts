/**
 * Whether the API may be asleep. The free host stops the API after a quiet period and
 * takes up to a minute to start it again, holding requests meanwhile. A request sent
 * before the API has answered anything in this page session, or long after its last
 * answer, may be waiting for that start; the site says so instead of looking frozen.
 */

/** Longest gap between answers after which the host may have stopped the API again. */
export const MAY_SLEEP_AFTER_MS = 10 * 60 * 1000;

type Listener = () => void;

const listeners = new Set<Listener>();
// Start times of pending requests sent while the API may have been asleep.
const pending = new Map<number, number>();
let lastAnswerAt: number | null = null;
let nextId = 0;

function emit(): void {
  for (const l of listeners) l();
}

/**
 * Record a request; returns its id for {@link requestFinished}. A `quiet` request (the
 * wake-up call sent on page load) counts when it is answered but never shows the notice.
 */
export function requestStarted(now: number = Date.now(), quiet = false): number {
  const id = nextId++;
  if (!quiet && (lastAnswerAt === null || now - lastAnswerAt > MAY_SLEEP_AFTER_MS)) {
    pending.set(id, now);
    emit();
  }
  return id;
}

/** Record the end of a request; `answered` is true for any HTTP response, error or not. */
export function requestFinished(id: number, answered: boolean, now: number = Date.now()): void {
  const tracked = pending.delete(id);
  if (answered) {
    lastAnswerAt = now;
    // One answer means the API is up: earlier requests are no longer waiting for a start.
    if (pending.size) pending.clear();
    emit();
  } else if (tracked) {
    emit();
  }
}

/** When the oldest request waiting for a possible start was sent, or null. */
export function wakingSince(): number | null {
  let oldest: number | null = null;
  for (const t of pending.values()) if (oldest === null || t < oldest) oldest = t;
  return oldest;
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Test helper: forget everything. */
export function resetServerStatus(): void {
  pending.clear();
  lastAnswerAt = null;
  emit();
}
