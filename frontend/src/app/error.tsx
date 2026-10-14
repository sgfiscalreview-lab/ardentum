"use client";

import Link from "next/link";
import { useEffect } from "react";

import { Button, Callout } from "@/components/ui";
import { buttonClass } from "@/lib/classes";

/** Shown in place of a page that crashed while rendering; the header and footer stay. */
export default function PageError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="mx-auto max-w-xl space-y-4 px-4 py-16">
      <h1 className="type-title-1 text-ink">This page could not be shown</h1>
      <Callout tone="error" title="The page stopped because of an unexpected error.">
        Your workspace settings are kept in this browser. Try again, or go back to the workspace.
        {error.digest && <span className="mt-1 block text-xs">Reference: {error.digest}</span>}
      </Callout>
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" onClick={() => retry()}>
          Try again
        </Button>
        <Link href="/app" className={buttonClass("secondary")}>
          Back to the workspace
        </Link>
      </div>
    </main>
  );
}
