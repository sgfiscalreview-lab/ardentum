import { afterEach, describe, expect, it } from "vitest";

import { MAY_SLEEP_AFTER_MS, requestFinished, requestStarted, resetServerStatus, wakingSince } from "./server-status";

afterEach(() => resetServerStatus());

describe("server status", () => {
  it("treats requests before the first answer as possibly waiting for a start", () => {
    const a = requestStarted(1000);
    requestStarted(2000);
    expect(wakingSince()).toBe(1000);
    requestFinished(a, true, 30_000);
    // Any answer means the API is up: nothing is waiting for it to start any more.
    expect(wakingSince()).toBeNull();
  });

  it("does not flag requests while the API is known to be up", () => {
    requestFinished(requestStarted(0), true, 100);
    requestStarted(5000); // e.g. a background job poll held open for 20 s
    expect(wakingSince()).toBeNull();
  });

  it("flags requests again after a long quiet period", () => {
    requestFinished(requestStarted(0), true, 100);
    const late = 100 + MAY_SLEEP_AFTER_MS + 1;
    requestStarted(late);
    expect(wakingSince()).toBe(late);
  });

  it("never flags the quiet wake-up call, but counts its answer", () => {
    const id = requestStarted(0, true);
    expect(wakingSince()).toBeNull();
    requestFinished(id, true, 40_000);
    requestStarted(41_000);
    expect(wakingSince()).toBeNull();
  });

  it("stops flagging a request that failed without an answer", () => {
    const id = requestStarted(0);
    requestFinished(id, false, 90_000);
    expect(wakingSince()).toBeNull();
  });
});
