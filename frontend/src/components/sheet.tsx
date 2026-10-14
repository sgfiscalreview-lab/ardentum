"use client";

import { animate, m, useMotionValue, useReducedMotion, useTransform, type AnimationPlaybackControlsWithThen } from "motion/react";
import { useEffect, useEffectEvent, useId, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { project, rubberband, type Sample, SPRING, SPRING_MOMENTUM, velocityFrom } from "@/lib/motion";

import { Button } from "./ui";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
/** Movement in pixels before a press on the grabber becomes a drag (hysteresis). */
const DRAG_THRESHOLD = 10;
/** How much smaller the page behind becomes when the sheet is fully open. */
const PUSH_BACK = 0.05;
/** Corner radius of the pushed-back page, in pixels. */
const PAGE_CORNER = 12;

interface Drag {
  pointerId: number;
  startPointer: number;
  startValue: number;
  samples: Sample[];
  moved: boolean;
}

/**
 * A bottom sheet, after Apple's fluid interfaces. It slides up from the bottom edge and
 * leaves the same way, pushing the page back while it is up. Its grabber follows the
 * finger 1:1 from where it was grabbed, at any moment, opening or closing, and resists past
 * the top (rubber-banding); on release it continues at the finger's speed, and a flick is
 * projected forward to decide where it comes to rest. While travelling it is slightly
 * see-through. With reduced motion it fades instead of sliding and the page stays put.
 * Escape, the scrim and "Done" close it; focus stays inside while it is open and returns
 * to the opener after.
 */
export function Sheet({
  open,
  onOpenChange,
  title,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: ReactNode;
}) {
  const titleId = useId();
  const reduced = useReducedMotion();
  const [present, setPresent] = useState(open);
  if (open && !present) setPresent(true); // mount on open; unmount only after closing

  const panel = useRef<HTMLDivElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const drag = useRef<Drag | null>(null);
  const releaseVelocity = useRef<number | null>(null);
  const motion = useRef<AnimationPlaybackControlsWithThen | null>(null);

  const y = useMotionValue(10_000); // offscreen until measured
  const height = useMotionValue(1);
  const fade = useMotionValue(1);
  /** How far up the sheet is: 0 off screen, 1 fully open. Everything else follows it. */
  const progress = useTransform(() => Math.min(1, Math.max(0, 1 - y.get() / Math.max(1, height.get()))));
  const scrim = useTransform(() => fade.get() * progress.get());
  const opacity = useTransform(() => fade.get() * (0.85 + 0.15 * progress.get()));

  // Come to rest open (0) or closed (off screen), continuing any gesture's speed. Springs
  // start from the value on screen, so this can take over from a drag or another motion.
  const settle = (to: "open" | "closed", velocity: number | null) => {
    motion.current?.stop();
    if (reduced) {
      y.jump(0);
      motion.current = animate(fade, to === "open" ? 1 : 0, { duration: 0.16, ease: "easeOut" });
    } else {
      fade.set(1);
      motion.current = animate(y, to === "open" ? 0 : height.get(), velocity === null ? SPRING : { ...SPRING_MOMENTUM, velocity });
    }
    if (to === "closed") void motion.current.then(() => setPresent(false));
  };

  const onOpenChanged = useEffectEvent((isOpen: boolean) => {
    const h = panel.current?.offsetHeight ?? window.innerHeight;
    height.set(h);
    // The first opening starts just below the edge. `jump` also clears the velocity a plain
    // set would imply (from the parked position to the edge in one frame), which the spring
    // would otherwise inherit and fling the sheet far past the top.
    if (isOpen && y.get() > h) y.jump(h);
    const velocity = releaseVelocity.current;
    releaseVelocity.current = null;
    settle(isOpen ? "open" : "closed", velocity);
  });

  useEffect(() => {
    if (!present) return;
    onOpenChanged(open);
    return () => motion.current?.stop();
  }, [open, present, reduced]);

  // While present: the page behind is inert and does not scroll, focus is inside; after,
  // focus returns to the opener.
  useEffect(() => {
    if (!present) return;
    opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const root = document.documentElement;
    const page = document.getElementById("page");
    const overflow = root.style.overflow;
    root.style.overflow = "hidden";
    if (page) page.inert = true;
    const first = panel.current?.querySelector<HTMLElement>('[aria-current="page"]') ?? panel.current;
    first?.focus({ preventScroll: true });
    return () => {
      root.style.overflow = overflow;
      if (page) page.inert = false;
      opener.current?.focus({ preventScroll: true });
    };
  }, [present]);

  // Depth: the page shrinks back as the sheet comes up and returns as it goes, following
  // the sheet even under the finger. Only a transform changes per frame; the rounded clip
  // and the backdrop are set once.
  useEffect(() => {
    const page = document.getElementById("page");
    if (!present || reduced || !page) return;
    const root = document.documentElement;
    const top = window.scrollY;
    const bottom = Math.max(0, page.offsetHeight - top - window.innerHeight);
    root.setAttribute("data-sheet", "");
    page.style.transformOrigin = `50% ${top + window.innerHeight / 2}px`;
    page.style.clipPath = `inset(${top}px 0 ${bottom}px 0 round ${PAGE_CORNER}px)`;
    page.style.willChange = "transform";
    const push = (p: number) => {
      page.style.transform = `scale(${1 - PUSH_BACK * p})`;
    };
    push(progress.get());
    const stop = progress.on("change", push);
    return () => {
      stop();
      root.removeAttribute("data-sheet");
      page.style.transform = "";
      page.style.transformOrigin = "";
      page.style.clipPath = "";
      page.style.willChange = "";
    };
  }, [present, reduced, progress]);

  if (!present) return null;

  const close = () => onOpenChange(false);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      close();
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
    if (e.button !== 0 || (e.target as HTMLElement).closest("button, a")) return;
    motion.current?.stop(); // grab it mid-flight, opening or closing: it stays where it is
    y.stop();
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { pointerId: e.pointerId, startPointer: e.clientY, startValue: y.get(), samples: [{ t: e.timeStamp, v: y.get() }], moved: false };
  };
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d || d.pointerId !== e.pointerId) return;
    const delta = e.clientY - d.startPointer;
    if (!d.moved && Math.abs(delta) < DRAG_THRESHOLD) return; // a press is not yet a drag
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
    if (!d.moved) {
      settle(open ? "open" : "closed", null); // a press that caught a motion lets it go on
      return;
    }
    d.samples.push({ t: e.timeStamp, v: y.get() }); // a pause before letting go means no flick
    const velocity = velocityFrom(d.samples);
    const to = y.get() + project(velocity) > height.get() / 2 ? "closed" : "open";
    if ((to === "open") === open) {
      settle(to, velocity);
    } else {
      releaseVelocity.current = velocity; // the next motion continues the gesture
      onOpenChange(to === "open");
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-50">
      <m.div aria-hidden className="absolute inset-0 bg-scrim" style={{ opacity: scrim }} onClick={close} />
      <m.div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        style={{ y, opacity }}
        className="material-thick absolute inset-x-0 bottom-0 flex max-h-[85dvh] flex-col rounded-t-[20px] border-t border-line outline-none will-change-transform elev-3"
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
            <Button size="sm" variant="ghost" onClick={close}>
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
