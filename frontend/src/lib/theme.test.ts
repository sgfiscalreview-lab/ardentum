import { easeThemeChange } from "./theme";

describe("easeThemeChange", () => {
  afterEach(() => vi.useRealTimers());

  it("eases colours for a moment, then removes the transition", () => {
    vi.useFakeTimers();
    const root = document.createElement("html");
    easeThemeChange(root, 400);
    expect(root.classList.contains("theme-easing")).toBe(true);
    vi.advanceTimersByTime(399);
    expect(root.classList.contains("theme-easing")).toBe(true);
    vi.advanceTimersByTime(1);
    expect(root.classList.contains("theme-easing")).toBe(false);
  });

  it("restarts when the theme is switched again during the easing", () => {
    vi.useFakeTimers();
    const root = document.createElement("html");
    easeThemeChange(root, 400);
    vi.advanceTimersByTime(300);
    easeThemeChange(root, 400);
    vi.advanceTimersByTime(300);
    expect(root.classList.contains("theme-easing")).toBe(true); // still easing the second switch
    vi.advanceTimersByTime(100);
    expect(root.classList.contains("theme-easing")).toBe(false);
  });
});
