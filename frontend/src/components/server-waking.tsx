"use client";

import { AnimatePresence, m, useReducedMotion } from "motion/react";
import { useEffect, useState, useSyncExternalStore } from "react";

import { wakeApi } from "@/lib/api/client";
import { subscribe, wakingSince } from "@/lib/api/server-status";
import { REDUCED_UNFOLD, SPRING } from "@/lib/motion";

/** Seconds a request may wait before the notice appears (a warm API answers in well under one). */
const SHOW_AFTER_S = 3;

/**
 * Wakes the API when any page loads, and says so while a request waits for it to start:
 * otherwise a visitor arriving after a quiet period sees a page that seems to hang.
 */
export function ServerWaking() {
  const since = useSyncExternalStore(subscribe, wakingSince, () => null);
  const [now, setNow] = useState(() => Date.now());
  const reduced = useReducedMotion();

  useEffect(() => wakeApi(), []);

  useEffect(() => {
    if (since === null) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [since]);

  const waited = since === null ? 0 : Math.max(0, Math.floor((now - since) / 1000));
  const shown = since !== null && waited >= SHOW_AFTER_S;
  return (
    // Unfolds below the header and folds back into it once the server answers.
    <AnimatePresence initial={false}>
      {shown && (
        <m.div
          key="waking"
          role="status"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={reduced ? REDUCED_UNFOLD : SPRING}
          className="overflow-hidden border-b border-accent/25 bg-accent-wash text-sm text-ink print:hidden"
        >
          <p className="mx-auto max-w-6xl px-4 py-2.5">
            <span className="font-medium">Starting the calculation server ({waited} s).</span>{" "}
            <span className="text-ink-2">
              The free server sleeps when nobody has used it for a while and takes up to a minute to start. Your request
              continues on its own.
            </span>
          </p>
        </m.div>
      )}
    </AnimatePresence>
  );
}
