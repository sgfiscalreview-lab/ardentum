/** Class-name helpers shared by server and client components (no React here). */

export function cx(...parts: unknown[]): string {
  return parts.filter((p): p is string => typeof p === "string" && p.length > 0).join(" ");
}

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON: Record<ButtonVariant, string> = {
  primary: "bg-accent text-on-accent elev-2 hover:bg-accent-hover disabled:opacity-50",
  secondary: "bg-surface text-ink border border-line-strong elev-1 hover:bg-surface-2 disabled:opacity-50",
  ghost: "text-ink-2 hover:bg-surface-2 hover:text-ink active:bg-surface-3 disabled:opacity-50",
  danger: "bg-surface text-critical border border-line-strong elev-1 hover:bg-critical-wash disabled:opacity-50",
};

/** Classes for a button, also for links that look like one. Feedback starts on the press. */
export function buttonClass(variant: ButtonVariant = "secondary", size: "sm" | "md" | "lg" = "md"): string {
  return cx(
    "pressable inline-flex select-none items-center justify-center gap-2 rounded-md font-medium whitespace-nowrap",
    size === "sm" ? "h-8 px-3.5 text-[13px]" : size === "lg" ? "h-11 rounded-full px-6 text-[15px]" : "h-9 px-4 text-sm",
    BUTTON[variant],
  );
}
