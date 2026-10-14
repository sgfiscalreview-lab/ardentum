"use client";

import { AnimatePresence, m, useIsPresent } from "motion/react";
import Link from "next/link";
import {
  forwardRef,
  useEffect,
  useEffectEvent,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ComponentProps,
  type InputHTMLAttributes,
  type ReactNode,
  type RefObject,
  type SelectHTMLAttributes,
} from "react";

import { buttonClass, cx, type ButtonVariant } from "@/lib/classes";
import { glossaryIdFor } from "@/lib/glossary";
import { MATERIAL_IN, MATERIAL_OUT, SPRING, SPRING_SNAPPY } from "@/lib/motion";

export { buttonClass, cx } from "@/lib/classes";

// --------------------------------------------------------------------------- Button

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: "sm" | "md"; busy?: boolean }
>(function Button({ variant = "secondary", size = "md", busy, className, children, disabled, ...rest }, ref) {
  return (
    <button
      ref={ref}
      className={cx(buttonClass(variant, size), className)}
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
    <section id={id} className={cx("rounded-lg border border-line bg-surface elev-1", className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3">
          <div className="min-w-0">
            {title && <h2 className="type-headline text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-footnote leading-snug text-ink-2">{subtitle}</p>}
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
      <label htmlFor={htmlFor} className="text-footnote font-medium text-ink-2">
        {label}
      </label>
      {children}
      {hint && <p className="type-caption text-muted">{hint}</p>}
    </div>
  );
}

const CONTROL =
  "field h-9 w-full rounded-md border border-line-strong bg-surface px-3 text-sm text-ink placeholder:text-muted disabled:opacity-60";

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
        className="mt-0.5 size-4 shrink-0 rounded accent-[var(--accent)]"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <label htmlFor={id} className="text-sm leading-tight text-ink">
        {label}
        {hint && <span className="type-caption mt-0.5 block text-muted">{hint}</span>}
      </label>
    </div>
  );
}

// --------------------------------------------------------------------------- Feedback

type Tone = "info" | "warning" | "error" | "success" | "synthetic";

const TONE: Record<Tone, string> = {
  info: "bg-accent-wash border-accent/30",
  warning: "bg-warn-wash border-warn/40",
  error: "bg-critical-wash border-critical/40",
  success: "bg-good-wash border-good/40",
  synthetic: "bg-synthetic-wash border-synthetic/40",
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
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cx("rounded-lg border px-4 py-3 text-sm", TONE[tone], className)}>
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
      className={cx("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-caption2 font-medium", cls)}
    >
      {children}
    </span>
  );
}

export function EmptyState({ title, children, action }: { title: ReactNode; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-line bg-surface px-6 py-14 text-center elev-1">
      <p className="type-headline text-ink">{title}</p>
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
    <div className="min-w-0 rounded-lg border border-line bg-surface px-3.5 py-3" title={help}>
      <p className="truncate text-xs font-medium text-ink-2">
        <GlossaryLabel label={label} />
      </p>
      <p className="mt-1 text-[1.375rem] font-semibold leading-tight tracking-[-0.02em] text-ink tabular">{value}</p>
      {sub && (
        <p className={cx("type-caption mt-1", tone === "good" ? "text-good" : tone === "critical" ? "text-critical" : "text-muted")}>
          {sub}
        </p>
      )}
    </div>
  );
}

/** A result label, linked to its glossary definition when it has one. */
export function GlossaryLabel({ label }: { label: ReactNode }) {
  const id = typeof label === "string" ? glossaryIdFor(label) : undefined;
  if (!id) return <>{label}</>;
  return (
    <Link href={`/glossary#${id}`} className="underline decoration-dotted underline-offset-2 print:no-underline" title={`What "${String(label)}" means`}>
      {label}
    </Link>
  );
}

// --------------------------------------------------------------------------- Segmented controls

interface SegmentItem<T extends string> {
  value: T;
  label: ReactNode;
}

/**
 * A row of mutually exclusive choices with one sliding highlight. The highlight moves on
 * a spring from wherever it is on screen, so a quick second choice redirects it smoothly.
 * Arrow keys move the choice; only the chosen item is in the tab order.
 */
function SegmentedButtons<T extends string>({
  value,
  onChange,
  items,
  label,
  kind,
  size = "sm",
}: {
  value: T;
  onChange: (v: T) => void;
  items: SegmentItem<T>[];
  label: string;
  kind: "tabs" | "radio";
  size?: "xs" | "sm";
}) {
  const highlight = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const chosen = items.findIndex((it) => it.value === value);
  const choose = (i: number) => {
    const j = (i + items.length) % items.length;
    const it = items[j];
    if (!it) return;
    onChange(it.value);
    refs.current[j]?.focus();
  };
  return (
    <div
      role={kind === "tabs" ? "tablist" : "radiogroup"}
      aria-label={label}
      className="inline-flex shrink-0 rounded-[9px] bg-surface-2 p-0.5"
    >
      {items.map((it, i) => {
        const selected = i === chosen;
        return (
          <button
            key={it.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role={kind === "tabs" ? "tab" : "radio"}
            aria-selected={kind === "tabs" ? selected : undefined}
            aria-checked={kind === "radio" ? selected : undefined}
            tabIndex={selected || (chosen < 0 && i === 0) ? 0 : -1}
            onClick={() => onChange(it.value)}
            onKeyDown={(e) => {
              const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
              if (step) {
                e.preventDefault();
                choose(i + step);
              } else if (e.key === "Home" || e.key === "End") {
                e.preventDefault();
                choose(e.key === "Home" ? 0 : items.length - 1);
              }
            }}
            className={cx(
              "hit relative rounded-[7px] font-medium whitespace-nowrap",
              size === "xs" ? "px-2 py-0.5 text-caption1 sm:px-2.5" : "px-3 py-1 text-xs",
              selected ? "text-ink" : "text-ink-2 hover:text-ink",
            )}
          >
            {selected && (
              <m.span
                layoutId={highlight}
                transition={SPRING_SNAPPY}
                aria-hidden
                className="absolute inset-0 rounded-[7px] border border-line bg-surface elev-2"
              />
            )}
            <span className="relative">{it.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/** Switches between views of the same content (role "tab"). */
export function Tabs<T extends string>(props: { value: T; onChange: (v: T) => void; items: SegmentItem<T>[]; label: string }) {
  return <SegmentedButtons {...props} kind="tabs" />;
}

/** Chooses one setting among a few (role "radio"). */
export function Segmented<T extends string>(props: {
  value: T;
  onChange: (v: T) => void;
  items: SegmentItem<T>[];
  label: string;
  size?: "xs" | "sm";
}) {
  return <SegmentedButtons {...props} kind="radio" />;
}

// --------------------------------------------------------------------------- Table

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    // Focusable so keyboard users can scroll wide tables (WCAG 2.1.1).
    <div className={cx("overflow-x-auto", className)} tabIndex={0}>
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  );
}

export function Th({ children, align = "left", className }: { children?: ReactNode; align?: "left" | "right"; className?: string }) {
  return (
    <th
      scope="col"
      className={cx(
        "sticky top-0 z-[1] border-b border-line bg-surface px-3 py-2 text-xs font-medium text-ink-2 whitespace-nowrap",
        align === "right" ? "text-right" : "text-left",
        className,
      )}
    >
      {children}
    </th>
  );
}

export function Td({
  children,
  align = "left",
  className,
  title,
  colSpan,
  continued = false,
}: {
  children?: ReactNode;
  align?: "left" | "right";
  className?: string;
  title?: string;
  colSpan?: number;
  /** The row continues in the next one (no rule or bottom padding before it). */
  continued?: boolean;
}) {
  return (
    <td
      title={title}
      colSpan={colSpan}
      className={cx(
        "px-3 align-top",
        continued ? "pt-2" : "border-b border-line py-2",
        align === "right" && "text-right tabular whitespace-nowrap",
        className,
      )}
    >
      {children}
    </td>
  );
}

// --------------------------------------------------------------------------- Disclosure

/** "Show" / "Hide" label for a <details> summary (parent needs the `group` class). */
export function DisclosureHint() {
  return (
    <span aria-hidden className="shrink-0 text-xs font-normal text-muted">
      <span className="group-open:hidden">Show</span>
      <span className="hidden group-open:inline">Hide</span>
    </span>
  );
}

export function Disclosure({ summary, children, defaultOpen }: { summary: ReactNode; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(Boolean(defaultOpen));
  const region = useId();
  return (
    <section className="rounded-lg border border-line bg-surface elev-1">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={region}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 rounded-lg px-4 py-3 text-left text-sm font-medium text-ink"
      >
        {summary}
        <span aria-hidden className="shrink-0 text-xs font-normal text-muted">
          {open ? "Hide" : "Show"}
        </span>
      </button>
      {/* The body comes out of the header and goes back into it on the same path. Only
          opacity and position animate (no layout per frame); the card takes its new
          size at once. */}
      <AnimatePresence initial={false}>
        {open && (
          <m.div
            key="body"
            id={region}
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0, transition: SPRING }}
            exit={{ opacity: 0, y: -6, transition: SPRING_SNAPPY }}
          >
            <div className="border-t border-line px-4 py-3">{children}</div>
          </m.div>
        )}
      </AnimatePresence>
    </section>
  );
}

// --------------------------------------------------------------------------- Popover

/**
 * Puts a popover away on a press outside `ref` or on Escape. `ref` should hold the trigger
 * as well, so pressing the trigger again is left to the trigger.
 */
export function useDismiss(ref: RefObject<HTMLElement | null>, open: boolean, onClose: () => void) {
  const close = useEffectEvent(onClose);
  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, ref]);
}

/**
 * A panel anchored under the control that opened it: it grows out of that control and
 * returns into it, its material forming as it arrives. Place it in a relatively
 * positioned wrapper with the trigger.
 */
export function PopoverPanel({
  open,
  align = "end",
  className,
  children,
}: {
  open: boolean;
  /** Which edge of the trigger the panel lines up with; on phones the start edge is safer. */
  align?: "start" | "end" | "responsive";
  className?: string;
  children: ReactNode;
}) {
  return (
    <AnimatePresence>
      {open && (
        <Departing
          key="popover"
          initial={{ opacity: 0, scale: 0.96, y: -6, ...MATERIAL_OUT }}
          animate={{ opacity: 1, scale: 1, y: 0, ...MATERIAL_IN }}
          exit={{ opacity: 0, scale: 0.96, y: -6, ...MATERIAL_OUT }}
          className={cx(
            "material-thick absolute top-full z-20 mt-2 w-72 rounded-xl border border-line p-3 elev-3",
            align === "start"
              ? "left-0 origin-top-left"
              : align === "end"
                ? "right-0 origin-top-right"
                : "left-0 origin-top-left sm:left-auto sm:right-0 sm:origin-top-right",
            className,
          )}
        >
          {children}
        </Departing>
      )}
    </AnimatePresence>
  );
}

/**
 * A surface inside AnimatePresence that stops taking clicks the moment it starts to
 * leave: input is never held up by an exit animation, even a nearly invisible one.
 */
export function Departing({ style, ...props }: ComponentProps<typeof m.div>) {
  const present = useIsPresent();
  return <m.div {...props} style={{ ...style, pointerEvents: present ? undefined : "none" }} />;
}

// --------------------------------------------------------------------------- Skeleton

/** Static placeholder blocks shaped like the content that is loading. */
export function Skeleton({ className }: { className?: string }) {
  return <span aria-hidden className={cx("skeleton block", className ?? "h-4 w-full")} />;
}

export function SkeletonRows({ rows = 6, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} className="space-y-2">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="h-4 w-4" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 flex-1" />
          <Skeleton className="h-4 w-16" />
        </div>
      ))}
    </div>
  );
}
