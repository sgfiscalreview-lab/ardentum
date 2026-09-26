"use client";

import {
  forwardRef,
  useId,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";

export function cx(...parts: unknown[]): string {
  return parts.filter((p): p is string => typeof p === "string" && p.length > 0).join(" ");
}

// --------------------------------------------------------------------------- Button

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON: Record<ButtonVariant, string> = {
  primary: "bg-accent text-white hover:bg-accent-hover disabled:opacity-50",
  secondary: "bg-surface text-ink border border-line-strong hover:bg-surface-2 disabled:opacity-50",
  ghost: "text-ink-2 hover:bg-surface-2 hover:text-ink disabled:opacity-50",
  danger: "bg-surface text-critical border border-line-strong hover:bg-critical-wash disabled:opacity-50",
};

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: "sm" | "md"; busy?: boolean }
>(function Button({ variant = "secondary", size = "md", busy, className, children, disabled, ...rest }, ref) {
  return (
    <button
      ref={ref}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors whitespace-nowrap",
        size === "sm" ? "h-8 px-3 text-[13px]" : "h-9 px-4 text-sm",
        BUTTON[variant],
        className,
      )}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      {...rest}
    >
      {busy && <Spinner className="size-3.5" />}
      {children}
    </button>
  );
});

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={cx("animate-spin", className ?? "size-4")} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

// --------------------------------------------------------------------------- Card

export function Card({
  title,
  subtitle,
  actions,
  children,
  className,
  bodyClassName,
  id,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  id?: string;
}) {
  return (
    <section id={id} className={cx("rounded-lg border border-line bg-surface", className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-ink-2">{subtitle}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cx("p-4", bodyClassName)}>{children}</div>
    </section>
  );
}

// --------------------------------------------------------------------------- Form fields

export function Field({
  label,
  hint,
  children,
  htmlFor,
  className,
}: {
  label: ReactNode;
  hint?: ReactNode;
  children: ReactNode;
  htmlFor?: string;
  className?: string;
}) {
  return (
    <div className={cx("flex flex-col gap-1", className)}>
      <label htmlFor={htmlFor} className="text-xs font-medium text-ink-2">
        {label}
      </label>
      {children}
      {hint && <p className="text-[11px] leading-snug text-muted">{hint}</p>}
    </div>
  );
}

const CONTROL =
  "h-9 w-full rounded-md border border-line-strong bg-surface px-2.5 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none disabled:opacity-60";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...rest },
  ref,
) {
  return <input ref={ref} className={cx(CONTROL, className)} {...rest} />;
});

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cx(CONTROL, "pr-8", className)} {...rest}>
      {children}
    </select>
  );
}

/**
 * Numeric input shown in display units (e.g. percent) and stored in model units
 * (e.g. decimals). Keeps the raw text while typing so partial input is not clobbered.
 */
export function NumberInput({
  value,
  onChange,
  scale = 1,
  suffix,
  min,
  max,
  step,
  allowEmpty = false,
  id,
  ariaLabel,
  placeholder,
  disabled,
}: {
  value: number | null | undefined;
  onChange: (v: number | null) => void;
  scale?: number;
  suffix?: string;
  min?: number;
  max?: number;
  step?: number;
  allowEmpty?: boolean;
  id?: string;
  ariaLabel?: string;
  placeholder?: string;
  disabled?: boolean;
}) {
  const format = (v: number | null | undefined) =>
    v === null || v === undefined ? "" : String(Number((v * scale).toFixed(6)));
  const [text, setText] = useState(format(value));
  const [focused, setFocused] = useState(false);
  // While editing, show the raw text; otherwise always reflect the model value.
  const shown = focused ? text : format(value);
  const invalid = (() => {
    if (shown.trim() === "") return !allowEmpty;
    const n = Number(shown);
    if (!Number.isFinite(n)) return true;
    if (min !== undefined && n < min) return true;
    if (max !== undefined && n > max) return true;
    return false;
  })();
  return (
    <div className="relative">
      <input
        id={id}
        aria-label={ariaLabel}
        aria-invalid={invalid || undefined}
        inputMode="decimal"
        className={cx(CONTROL, suffix && "pr-8", invalid && "border-critical focus:border-critical", "tabular")}
        value={shown}
        placeholder={placeholder}
        disabled={disabled}
        onFocus={() => {
          setText(format(value));
          setFocused(true);
        }}
        onBlur={() => setFocused(false)}
        onChange={(e) => {
          const t = e.target.value;
          setText(t);
          if (t.trim() === "") {
            if (allowEmpty) onChange(null);
            return;
          }
          const n = Number(t);
          if (!Number.isFinite(n)) return;
          if (min !== undefined && n < min) return;
          if (max !== undefined && n > max) return;
          onChange(n / scale);
        }}
        step={step}
      />
      {suffix && (
        <span className="pointer-events-none absolute inset-y-0 right-2.5 flex items-center text-xs text-muted">
          {suffix}
        </span>
      )}
    </div>
  );
}

export function Checkbox({
  checked,
  onChange,
  label,
  hint,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: ReactNode;
  hint?: ReactNode;
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <div className="flex items-start gap-2">
      <input
        id={id}
        type="checkbox"
        className="mt-0.5 size-4 accent-[var(--accent)]"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <label htmlFor={id} className="text-sm leading-tight text-ink">
        {label}
        {hint && <span className="mt-0.5 block text-[11px] text-muted">{hint}</span>}
      </label>
    </div>
  );
}

// --------------------------------------------------------------------------- Feedback

type Tone = "info" | "warning" | "error" | "success" | "synthetic";

const TONE: Record<Tone, { box: string; icon: string; glyph: string }> = {
  info: { box: "bg-accent-wash border-accent/30", icon: "text-accent-ink", glyph: "i" },
  warning: { box: "bg-warn-wash border-warn/30", icon: "text-warn", glyph: "!" },
  error: { box: "bg-critical-wash border-critical/30", icon: "text-critical", glyph: "×" },
  success: { box: "bg-good-wash border-good/30", icon: "text-good", glyph: "✓" },
  synthetic: { box: "bg-synthetic-wash border-synthetic/30", icon: "text-synthetic", glyph: "S" },
};

export function Callout({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: Tone;
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  const t = TONE[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cx("flex gap-3 rounded-md border px-3 py-2.5 text-sm", t.box, className)}
    >
      <span
        aria-hidden
        className={cx(
          "mt-0.5 inline-flex size-4 shrink-0 items-center justify-center rounded-full border border-current text-[10px] font-bold",
          t.icon,
        )}
      >
        {t.glyph}
      </span>
      <div className="min-w-0 text-ink">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={cx("text-ink-2", title && "mt-0.5")}>{children}</div>}
      </div>
    </div>
  );
}

export function Badge({
  children,
  tone = "neutral",
  title,
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "good" | "warn" | "critical" | "synthetic";
  title?: string;
}) {
  const cls = {
    neutral: "bg-surface-2 text-ink-2 border-line",
    accent: "bg-accent-wash text-accent-ink border-accent/30",
    good: "bg-good-wash text-good border-good/30",
    warn: "bg-warn-wash text-warn border-warn/30",
    critical: "bg-critical-wash text-critical border-critical/30",
    synthetic: "bg-synthetic-wash text-synthetic border-synthetic/40",
  }[tone];
  return (
    <span
      title={title}
      className={cx("inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium", cls)}
    >
      {children}
    </span>
  );
}

export function EmptyState({ title, children, action }: { title: ReactNode; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-line-strong bg-surface px-6 py-12 text-center">
      <p className="text-sm font-medium text-ink">{title}</p>
      {children && <div className="mt-1 max-w-md text-sm text-ink-2">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// --------------------------------------------------------------------------- Metrics

export function Stat({
  label,
  value,
  sub,
  tone,
  help,
}: {
  label: ReactNode;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "good" | "critical";
  help?: string;
}) {
  return (
    <div className="min-w-0 rounded-md border border-line bg-surface px-3 py-2.5" title={help}>
      <p className="truncate text-[11px] font-medium text-ink-2">{label}</p>
      <p className="mt-0.5 text-xl font-semibold text-ink">{value}</p>
      {sub && (
        <p className={cx("mt-0.5 text-[11px]", tone === "good" ? "text-good" : tone === "critical" ? "text-critical" : "text-muted")}>
          {sub}
        </p>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- Tabs

export function Tabs<T extends string>({
  value,
  onChange,
  items,
  label,
}: {
  value: T;
  onChange: (v: T) => void;
  items: { value: T; label: ReactNode }[];
  label: string;
}) {
  return (
    <div role="tablist" aria-label={label} className="inline-flex rounded-md border border-line bg-surface-2 p-0.5">
      {items.map((it) => (
        <button
          key={it.value}
          role="tab"
          type="button"
          aria-selected={value === it.value}
          onClick={() => onChange(it.value)}
          className={cx(
            "rounded px-2.5 py-1 text-xs font-medium transition-colors",
            value === it.value ? "bg-surface text-ink shadow-sm" : "text-ink-2 hover:text-ink",
          )}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}

// --------------------------------------------------------------------------- Table

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cx("overflow-x-auto", className)}>
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  );
}

export function Th({ children, align = "left", className }: { children?: ReactNode; align?: "left" | "right"; className?: string }) {
  return (
    <th
      scope="col"
      className={cx(
        "sticky top-0 border-b border-line bg-surface px-2 py-2 text-[11px] font-medium uppercase tracking-wide text-ink-2 whitespace-nowrap",
        align === "right" ? "text-right" : "text-left",
        className,
      )}
    >
      {children}
    </th>
  );
}

export function Td({ children, align = "left", className, title }: { children?: ReactNode; align?: "left" | "right"; className?: string; title?: string }) {
  return (
    <td
      title={title}
      className={cx("border-b border-line px-2 py-1.5 align-top", align === "right" && "text-right tabular whitespace-nowrap", className)}
    >
      {children}
    </td>
  );
}

// --------------------------------------------------------------------------- Disclosure

export function Disclosure({ summary, children, defaultOpen }: { summary: ReactNode; children: ReactNode; defaultOpen?: boolean }) {
  return (
    <details className="group rounded-md border border-line bg-surface" open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center justify-between px-3 py-2 text-sm font-medium text-ink">
        {summary}
        <span aria-hidden className="text-muted transition-transform group-open:rotate-90">
          ›
        </span>
      </summary>
      <div className="border-t border-line px-3 py-3">{children}</div>
    </details>
  );
}
