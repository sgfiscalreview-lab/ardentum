import { describe, expect, it } from "vitest";

import { safeNext } from "./redirect";

describe("safeNext", () => {
  it("keeps paths on this site", () => {
    expect(safeNext("/app/optimise")).toBe("/app/optimise");
    expect(safeNext("/portfolios?sort=name#top")).toBe("/portfolios?sort=name#top");
  });

  it("sends everything else to the workspace", () => {
    for (const bad of [
      null,
      "",
      "app",
      "https://evil.example",
      "//evil.example",
      "/\\evil.example",
      "/\\/evil.example",
      "/\t/evil.example",
      "/\n/evil.example",
      "javascript:alert(1)",
    ]) {
      expect(safeNext(bad)).toBe("/app");
    }
  });
});
