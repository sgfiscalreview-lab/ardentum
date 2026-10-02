import { describe, expect, it } from "vitest";

import { decodeShare, encodeShare, MAX_SHARE_BYTES, SHARE_PREFIX } from "./share";
import { DEFAULT_STATE } from "./workspace";

describe("share links", () => {
  it("round-trip the settings in a short, URL-safe fragment", async () => {
    const payload = { v: 1, universe: DEFAULT_STATE.universe, objective: DEFAULT_STATE.objective, name: "Ünïcode ok" };
    const fragment = await encodeShare(payload);
    expect(fragment.startsWith(SHARE_PREFIX)).toBe(true);
    expect(fragment.slice(SHARE_PREFIX.length)).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(fragment.length).toBeLessThan(600);
    expect(await decodeShare(fragment)).toEqual(payload);
  });

  it("ignores other fragments and rejects damaged or oversized ones", async () => {
    expect(await decodeShare("#main")).toBeNull();
    await expect(decodeShare(SHARE_PREFIX + "not-deflate-data")).rejects.toThrow();
    const bomb = await encodeShare({ x: "a".repeat(MAX_SHARE_BYTES + 10) });
    expect(bomb.length).toBeLessThan(2000); // compresses well, so the limit is on the decoded size
    await expect(decodeShare(bomb)).rejects.toThrow(/too large/);
  });
});
