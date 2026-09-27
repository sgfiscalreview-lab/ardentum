import Link from "next/link";
import type { ReactNode } from "react";

import { LEGAL, LEGAL_CONFIGURED } from "@/lib/legal";

export function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="font-display text-3xl font-semibold text-ink">{title}</h1>
      <p className="mt-2 text-xs text-muted">Last updated {LEGAL.lastUpdated}</p>
      {!LEGAL_CONFIGURED && (
        <p role="status" className="mt-4 rounded-sm border border-warn/40 bg-warn-wash px-3 py-2 text-sm text-ink">
          This deployment has not set its operator name, contact address and governing law
          (NEXT_PUBLIC_LEGAL_OPERATOR, NEXT_PUBLIC_LEGAL_CONTACT_EMAIL, NEXT_PUBLIC_LEGAL_GOVERNING_LAW).
        </p>
      )}
      <div className="legal mt-8 space-y-8 text-sm leading-relaxed text-ink">{children}</div>
      <p className="mt-12 text-xs text-muted">
        See also the <Link href="/terms" className="underline underline-offset-2">Terms of Service</Link> and the{" "}
        <Link href="/privacy" className="underline underline-offset-2">Privacy Policy</Link>.
      </p>
    </main>
  );
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      <div className="mt-2 space-y-2 text-ink-2">{children}</div>
    </section>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-line">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-3 px-4 py-6 text-xs text-muted sm:flex-row sm:items-start sm:justify-between">
        <p className="max-w-2xl leading-relaxed">
          Ardentum is an analytical tool for education and research. It does not give investment advice. Model outputs are estimates based on historical data and stated assumptions; past performance does not predict future results.
        </p>
        <nav aria-label="Legal" className="flex shrink-0 gap-4">
          <Link href="/terms" className="underline-offset-2 hover:underline">
            Terms of Service
          </Link>
          <Link href="/privacy" className="underline-offset-2 hover:underline">
            Privacy Policy
          </Link>
          <Link href="/research" className="underline-offset-2 hover:underline">
            Methodology
          </Link>
        </nav>
      </div>
    </footer>
  );
}
