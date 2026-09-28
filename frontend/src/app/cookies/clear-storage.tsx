"use client";

import { useState } from "react";

import { Button } from "@/components/ui";

const KEYS = ["ardentum.theme", "ardentum.workspace"];

/** Removes the settings Ardentum keeps in this browser (not the sign-in session). */
export function ClearStorage() {
  const [done, setDone] = useState(false);
  const clear = () => {
    try {
      for (const k of KEYS) window.localStorage.removeItem(k);
      setDone(true);
    } catch {
      setDone(false);
    }
  };
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button onClick={clear}>Clear my settings from this browser</Button>
      {done && (
        <p role="status" className="text-sm text-ink-2">
          Cleared. Reload the page to use the default settings.
        </p>
      )}
    </div>
  );
}
