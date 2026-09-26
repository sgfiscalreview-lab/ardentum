"use client";

import { createContext, useCallback, useContext, useEffect, useSyncExternalStore, type ReactNode } from "react";

type ThemeChoice = "system" | "light" | "dark";

interface ThemeContextValue {
  choice: ThemeChoice;
  isDark: boolean;
  setChoice: (c: ThemeChoice) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);
const KEY = "ardentum.theme";
const listeners = new Set<() => void>();

function readChoice(): ThemeChoice {
  try {
    const v = window.localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

function subscribeChoice(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

function subscribeSystem(cb: () => void) {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const choice = useSyncExternalStore(subscribeChoice, readChoice, () => "system" as const);
  const systemDark = useSyncExternalStore(
    subscribeSystem,
    () => window.matchMedia("(prefers-color-scheme: dark)").matches,
    () => false,
  );

  useEffect(() => {
    const root = document.documentElement;
    if (choice === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", choice);
  }, [choice]);

  const setChoice = useCallback((c: ThemeChoice) => {
    try {
      if (c === "system") window.localStorage.removeItem(KEY);
      else window.localStorage.setItem(KEY, c);
    } catch {
      /* storage unavailable: theme still applies for this page view */
    }
    listeners.forEach((l) => l());
  }, []);

  const isDark = choice === "dark" || (choice === "system" && systemDark);
  return <ThemeContext.Provider value={{ choice, isDark, setChoice }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}
