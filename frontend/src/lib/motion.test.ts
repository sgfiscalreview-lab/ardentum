import { appleSpring, project, rubberband, SPRING, SPRING_MOMENTUM, velocityFrom } from "./motion";

describe("appleSpring", () => {
  it("maps damping ratio and response to mass-spring constants", () => {
    const s = appleSpring(1, 0.4);
    const omega = (2 * Math.PI) / 0.4;
    expect(s.stiffness).toBeCloseTo(omega * omega, 10);
    expect(s.damping).toBeCloseTo((4 * Math.PI) / 0.4, 10);
    expect(s.mass).toBe(1);
  });

  it("is critically damped at ratio 1 and underdamped below it", () => {
    // Critical damping: c^2 = 4 k m.
    expect(SPRING.damping ** 2).toBeCloseTo(4 * SPRING.stiffness * SPRING.mass, 6);
    expect(SPRING_MOMENTUM.damping ** 2).toBeLessThan(4 * SPRING_MOMENTUM.stiffness);
    // The damping ratio is recovered from the constants.
    expect(SPRING_MOMENTUM.damping / (2 * Math.sqrt(SPRING_MOMENTUM.stiffness))).toBeCloseTo(0.8, 10);
  });

  it("refuses non-positive parameters", () => {
    expect(() => appleSpring(0, 0.3)).toThrow();
    expect(() => appleSpring(1, 0)).toThrow();
  });
});

describe("project", () => {
  it("matches the closed form of exponential deceleration", () => {
    // Sum of v * d^n per millisecond: v/1000 * d / (1 - d).
    const v = 1500;
    const d = 0.998;
    let distance = 0;
    let speed = v / 1000;
    for (let i = 0; i < 20_000; i++) {
      speed *= d;
      distance += speed;
    }
    expect(project(v, d)).toBeCloseTo(distance, 3);
    expect(project(-v)).toBeCloseTo(-project(v), 10);
    expect(project(0)).toBe(0);
  });
});

describe("rubberband", () => {
  it("follows the finger less the further it goes, and keeps the direction", () => {
    const dim = 400;
    const a = rubberband(50, dim);
    const b = rubberband(200, dim);
    expect(a).toBeGreaterThan(0);
    expect(b).toBeGreaterThan(a);
    expect(b - a).toBeLessThan(150); // less than the extra 150 px of overshoot
    expect(rubberband(-50, dim)).toBeCloseTo(-a, 10);
    expect(rubberband(1e9, dim)).toBeLessThan(dim);
    expect(rubberband(1e9, dim)).toBeGreaterThan(dim * 0.99);
    expect(rubberband(0, dim)).toBe(0);
  });
});

describe("velocityFrom", () => {
  it("uses only the last window of samples", () => {
    const samples = [
      { t: 0, v: 0 },
      { t: 500, v: 0 }, // a pause long before release
      { t: 550, v: 25 },
      { t: 600, v: 50 },
    ];
    expect(velocityFrom(samples)).toBeCloseTo(500, 10); // 50 px in 100 ms
    expect(velocityFrom([{ t: 0, v: 0 }])).toBe(0);
    expect(velocityFrom([{ t: 0, v: 0 }, { t: 300, v: 30 }])).toBe(0); // stopped before release
  });
});
