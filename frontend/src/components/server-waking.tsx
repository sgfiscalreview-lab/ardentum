"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

import { wakeApi } from "@/lib/api/client";
import { subscribe, wakingSince } from "@/lib/api/server-status";

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
  if (since === null || waited < SHOW_AFTER_S) return null;
  return (
    <div role="status" className="border-b border-accent/30 bg-accent-wash px-4 py-2 text-sm text-ink print:hidden">
      <p className="mx-auto max-w-6xl">
        <span className="font-medium">Starting the calculation server ({waited} s).</span>{" "}
        <span className="text-ink-2">
          The free server sleeps when nobody has used it for a while and takes up to a minute to start. Your request
          continues on its own.
        </span>
      </p>
    </div>
  );
}
