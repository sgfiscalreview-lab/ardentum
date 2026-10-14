import type { Metadata } from "next";

import { UsageView } from "./usage-view";

export const metadata: Metadata = { title: "Usage" };

export default function UsagePage() {
  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <p className="text-footnote font-semibold text-accent-ink">Usage</p>
      <h1 className="type-title-1 mt-2 text-ink">How much Ardentum is used</h1>
      <p className="mt-2 max-w-2xl text-ink-2">
        Each time a calculation finishes successfully, the server adds one to a daily total for that kind of calculation. Nothing else is recorded: no account, address, device, cookie or content, so no count can be traced to anyone. Requests that fail, and the automated checks that monitor the site, are not counted.
      </p>
      <UsageView />
    </main>
  );
}
