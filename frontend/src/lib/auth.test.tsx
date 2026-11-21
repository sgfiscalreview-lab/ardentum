import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

// The API never answers, as when the free host is still starting it.
vi.mock("./api/client", () => ({
  api: { GET: () => new Promise(() => {}) },
  unwrap: <T,>(p: Promise<T>) => p,
  setTokenProvider: () => {},
}));
vi.mock("@supabase/supabase-js", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: null } }),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } }),
    },
  }),
}));

// React reports act() warnings only where this flag is set.
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

async function shownStatus() {
  const { AuthProvider, useAuth } = await import("./auth");
  function Status() {
    const { status, mode } = useAuth();
    return <p>{`${status} ${mode ?? "none"}`}</p>;
  }
  const box = document.createElement("div");
  const root = createRoot(box);
  await act(async () => {
    root.render(
      <AuthProvider>
        <Status />
      </AuthProvider>,
    );
  });
  const shown = box.textContent;
  act(() => root.unmount());
  return shown;
}

describe("sign-in state", () => {
  it("is known at once on a Supabase build, without waiting for the API", async () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test");
    expect(await shownStatus()).toBe("signed_out supabase");
  });

  it("waits for the API's settings on a build without Supabase", async () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "");
    expect(await shownStatus()).toBe("loading none");
  });
});
