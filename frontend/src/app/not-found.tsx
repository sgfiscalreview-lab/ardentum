import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Page not found" };

export default function NotFound() {
  return (
    <main className="mx-auto max-w-xl space-y-4 px-4 py-16">
      <h1 className="font-display text-3xl font-semibold text-ink">Page not found</h1>
      <p className="text-sm leading-relaxed text-ink-2">There is no page at this address. It may have moved, or the link may be mistyped.</p>
      <div className="flex flex-wrap gap-2">
        <Link href="/app" className="inline-flex h-9 items-center rounded-sm bg-accent px-4 text-sm font-medium text-on-accent hover:bg-accent-hover">
          Open the workspace
        </Link>
        <Link href="/" className="inline-flex h-9 items-center rounded-sm border border-line-strong bg-surface px-4 text-sm text-ink hover:bg-surface-2">
          Home page
        </Link>
      </div>
    </main>
  );
}
