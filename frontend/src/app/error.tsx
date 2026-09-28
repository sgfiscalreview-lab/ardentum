"use client";

import Link from "next/link";
import { useEffect } from "react";

import { Button, Callout } from "@/components/ui";

/** Shown in place of a page that crashed while rendering; the header and footer stay. */
export default function PageError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="mx-auto max-w-xl space-y-4 px-4 py-16">
      <h1 className="font-display text-3xl font-semibold text-ink">This page could not be shown</h1>
      <Callout tone="error" title="The page stopped because of an unexpected error.">
        Your workspace settings are kept in this browser. Try again, or go back to the workspace.
        {error.digest && <span className="mt-1 block text-xs">Reference: {error.digest}</span>}
      </Callout>
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" onClick={() => retry()}>
          Try again
        </Button>
        <Link href="/app" className="inline-flex h-9 items-center rounded-sm border border-line-strong bg-surface px-4 text-sm text-ink hover:bg-surface-2">
          Back to the workspace
        </Link>
      </div>
    </main>
  );
}
