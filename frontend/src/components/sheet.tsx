"use client";

import { animate, m, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import { useEffect, useId, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { project, rubberband, type Sample, SPRING, SPRING_MOMENTUM, velocityFrom } from "@/lib/motion";

import { Button } from "./ui";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface Drag {
  pointerId: number;
  startPointer: number;
  startValue: number;
  samples: Sample[];
  moved: boolean;
}

/**
 * A bottom sheet, after Apple's fluid interfaces: it slides up from the bottom edge and
 * leaves the same way; its grabber follows the finger 1:1 from where it was grabbed and
 * rubber-bands past the top; on release it continues at the finger's speed, and a flick
 * is projected forward to decide whether it closes. While open it can be grabbed
 * mid-flight. With reduced motion it fades instead of sliding. Escape, the scrim and
 * "Done" close it; focus stays inside while open and returns to the opener after.
 */
export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const titleId = useId();
  const reduced = useReducedMotion();
  const [present, setPresent] = useState(open);
  if (open && !present) setPresent(true); // mount on open; unmount only after closing

  const panel = useRef<HTMLDivElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const drag = useRef<Drag | null>(null);
  const releaseVelocity = useRef<number | null>(null);

  const y = useMotionValue(10_000); // offscreen until measured
  const height = useMotionValue(1);
  const fade = useMotionValue(1);
  const scrim = useTransform(() => fade.get() * Math.min(1, Math.max(0, 1 - y.get() / Math.max(1, height.get()))));

  // Open and close: springs from the value on screen, with any velocity left by a gesture.
  useEffect(() => {
    if (!present) return;
    const h = panel.current?.offsetHeight ?? window.innerHeight;
    height.set(h);
    if (reduced) {
      y.set(0);
      if (open) fade.set(0);
      const controls = animate(fade, open ? 1 : 0, { duration: 0.16, ease: "easeOut" });
      if (!open) void controls.then(() => setPresent(false));
      return () => controls.stop();
    }
    fade.set(1);
    if (open && y.get() > h) y.set(h);
    const velocity = releaseVelocity.current;
    releaseVelocity.current = null;
    const controls = animate(y, open ? 0 : h, velocity === null ? SPRING : { ...SPRING_MOMENTUM, velocity });
    if (!open) void controls.then(() => setPresent(false));
    return () => controls.stop();
  }, [open, present, reduced, y, height, fade]);

  // While open: no page scroll behind, focus inside; afterwards focus returns to the opener.
  useEffect(() => {
    if (!present) return;
    opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const root = document.documentElement;
    const previous = root.style.overflow;
    root.style.overflow = "hidden";
    const first = panel.current?.querySelector<HTMLElement>('[aria-current="page"]') ?? panel.current;
    first?.focus({ preventScroll: true });
    return () => {
      root.style.overflow = previous;
      opener.current?.focus({ preventScroll: true });
    };
  }, [present]);

  if (!present) return null;

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      onClose();
      return;
    }
    if (e.key !== "Tab" || !panel.current) return;
    const items = Array.from(panel.current.querySelectorAll<HTMLElement>(FOCUSABLE));
    const first = items[0];
    const last = items[items.length - 1];
    if (!first || !last) return;
    if (e.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    // Once closing, the sheet belongs to the page again: only an open sheet can be grabbed.
    if (!open || e.button !== 0 || (e.target as HTMLElement).closest("button, a")) return;
    y.stop(); // grab it mid-flight: continue from where it is on screen
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { pointerId: e.pointerId, startPointer: e.clientY, startValue: y.get(), samples: [{ t: e.timeStamp, v: y.get() }], moved: false };
  };
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d || d.pointerId !== e.pointerId) return;
    const delta = e.clientY - d.startPointer;
    if (!d.moved && Math.abs(delta) < 4) return; // a tap is not a drag
    d.moved = true;
    const raw = d.startValue + delta;
    const v = raw < 0 ? rubberband(raw, height.get()) : raw; // resist past the top
    y.set(v);
    d.samples.push({ t: e.timeStamp, v });
    if (d.samples.length > 24) d.samples.shift();
  };
  const onPointerEnd = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d || d.pointerId !== e.pointerId) return;
    drag.current = null;
    if (!d.moved) return;
    d.samples.push({ t: e.timeStamp, v: y.get() }); // a pause before letting go means no flick
    const velocity = velocityFrom(d.samples);
    const resting = y.get() + project(velocity);
    if (resting > height.get() / 2) {
      releaseVelocity.current = velocity; // the close animation continues the gesture
      onClose();
    } else {
      void animate(y, 0, { ...SPRING_MOMENTUM, velocity });
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-50">
      <m.div aria-hidden className="absolute inset-0 bg-scrim" style={{ opacity: scrim }} onClick={onClose} />
      <m.div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        style={{ y, opacity: fade }}
        className="material-thick absolute inset-x-0 bottom-0 flex max-h-[85dvh] flex-col rounded-t-[22px] border-t border-line outline-none elev-3"
      >
        <div
          className="cursor-grab touch-none select-none px-4 pb-2 pt-2 active:cursor-grabbing"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerEnd}
          onPointerCancel={onPointerEnd}
        >
          <div aria-hidden className="mx-auto h-1.5 w-10 rounded-full bg-[var(--border-strong)]" />
          <div className="mt-2 flex items-center justify-between gap-3">
            <h2 id={titleId} className="type-headline text-ink">
              {title}
            </h2>
            <Button size="sm" variant="ghost" onClick={onClose}>
              Done
            </Button>
          </div>
        </div>
        <div className="overflow-y-auto overscroll-contain px-3 pb-[max(1rem,env(safe-area-inset-bottom))]">{children}</div>
      </m.div>
    </div>,
    document.body,
  );
}
