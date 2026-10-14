"use client";

import { AnimatePresence } from "motion/react";
import { useEffect, useState, useSyncExternalStore } from "react";

import { wakeApi } from "@/lib/api/client";
import { subscribe, wakingSince } from "@/lib/api/server-status";
import { MATERIAL_IN, MATERIAL_OUT } from "@/lib/motion";

import { Departing } from "./ui";

/** Seconds a request may wait before the notice appears (a warm API answers in well under one). */
const SHOW_AFTER_S = 3;

/**
 * Wakes the API when any page loads, and says so while a request waits for it to start:
 * otherwise a visitor arriving after a quiet period sees a page that seems to hang.
 */
export function ServerWaking() {
  const since = useSyncExternalStore(subscribe, wakingSince, () => null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => wakeApi(), []);

  useEffect(() => {
    if (since === null) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [since]);

  const waited = since === null ? 0 : Math.max(0, Math.floor((now - since) / 1000));
  const shown = since !== null && waited >= SHOW_AFTER_S;
  return (
    // A notice that floats above the page rather than pushing it down: it rises from the
    // bottom edge and returns there once the server answers. Nothing on the page moves.
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-40 flex justify-center px-4 print:hidden">
      <AnimatePresence>
        {shown && (
          <Departing
            key="waking"
            role="status"
            initial={{ opacity: 0, y: 24, ...MATERIAL_OUT }}
            animate={{ opacity: 1, y: 0, ...MATERIAL_IN }}
            exit={{ opacity: 0, y: 24, ...MATERIAL_OUT }}
            className="material-thick pointer-events-auto w-full max-w-xl rounded-xl border border-line px-4 py-3 text-sm text-ink elev-3"
          >
            <p>
              <span className="font-medium">Starting the calculation server ({waited} s).</span>{" "}
              <span className="text-ink-2">
                The free server sleeps when nobody has used it for a while and takes up to a minute to start. Your request
                continues on its own.
              </span>
            </p>
          </Departing>
        )}
      </AnimatePresence>
    </div>
  );
}
