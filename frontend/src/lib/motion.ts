/**
 * Motion rules for the interface, after Apple's "Designing Fluid Interfaces" (WWDC 2018);
 * see .claude/skills/apple-design. Everything that moves uses a spring, so motion starts
 * from the value on screen, keeps its velocity when redirected and can be interrupted.
 */

export interface Spring {
  type: "spring";
  stiffness: number;
  damping: number;
  mass: number;
}

/**
 * Apple's two designer-facing spring parameters as mass-spring constants (mass 1):
 * stiffness (2 pi / response)^2 and damping 4 pi dampingRatio / response. A damping ratio
 * of 1 settles without overshoot; below 1 it overshoots. Response is the period of the
 * undamped spring in seconds, not a duration.
 */
export function appleSpring(dampingRatio: number, response: number): Spring {
  if (!(dampingRatio > 0) || !(response > 0)) throw new Error("Damping ratio and response must be positive.");
  const omega = (2 * Math.PI) / response;
  return { type: "spring", stiffness: omega * omega, damping: 2 * dampingRatio * omega, mass: 1 };
}

/** Default for anything that moves on its own: critically damped, no overshoot. */
export const SPRING = appleSpring(1, 0.35);
/** Small selections (segmented controls): a little quicker. */
export const SPRING_SNAPPY = appleSpring(1, 0.28);
/** After a flick or a drag release only: the gesture carried momentum, so a slight overshoot reads as physical. */
export const SPRING_MOMENTUM = appleSpring(0.8, 0.3);
/** With reduced motion, for content that unfolds: its size changes at once and it fades in or out. */
export const REDUCED_UNFOLD = { height: { duration: 0 }, default: { duration: 0.15, ease: "easeOut" } } as const;

/**
 * Distance a flick travels before coming to rest, in pixels, for a release velocity in
 * pixels per second: Apple's projection for scroll-like deceleration (rate per millisecond).
 */
export function project(velocity: number, decelerationRate = 0.998): number {
  return ((velocity / 1000) * decelerationRate) / (1 - decelerationRate);
}

/**
 * Rubber-banding past a boundary: the further past the edge, the less the element follows.
 * Keeps the sign of the overshoot and approaches, but never reaches, `dimension` in size.
 */
export function rubberband(overshoot: number, dimension: number, constant = 0.55): number {
  if (dimension <= 0) return 0;
  return (overshoot * dimension * constant) / (dimension + constant * Math.abs(overshoot));
}

export interface Sample {
  t: number; // milliseconds
  v: number; // position in pixels
}

/**
 * Release velocity in pixels per second from the pointer's recent positions: the change
 * over the samples in the last `windowMs` before the final one. Zero when there are not
 * two samples in that window (the pointer stopped before letting go).
 */
export function velocityFrom(samples: readonly Sample[], windowMs = 100): number {
  if (samples.length < 2) return 0;
  const last = samples[samples.length - 1]!;
  let first = last;
  for (let i = samples.length - 2; i >= 0; i--) {
    const s = samples[i]!;
    if (last.t - s.t > windowMs) break;
    first = s;
  }
  const dt = last.t - first.t;
  return dt > 0 ? ((last.v - first.v) / dt) * 1000 : 0;
}
