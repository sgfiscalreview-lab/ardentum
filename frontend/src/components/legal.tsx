import Link from "next/link";
import type { ReactNode } from "react";

import { LEGAL, LEGAL_CONFIGURED, operatorDetails } from "@/lib/legal";

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
        See also the <Link href="/terms" className="underline underline-offset-2">Terms of Service</Link>, the{" "}
        <Link href="/privacy" className="underline underline-offset-2">Privacy Policy</Link>, the{" "}
        <Link href="/cookies" className="underline underline-offset-2">Cookie Policy</Link> and the{" "}
        <Link href="/licences" className="underline underline-offset-2">licences</Link>.
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
  const links = [
    { href: "/terms", label: "Terms of Service" },
    { href: "/privacy", label: "Privacy Policy" },
    { href: "/cookies", label: "Cookie Policy" },
    { href: "/licences", label: "Licences" },
    { href: "/research", label: "Methodology" },
  ];
  return (
    <footer className="mt-16 border-t border-line">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-3 px-4 py-6 text-xs text-muted sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-2xl space-y-2 leading-relaxed">
          <p>
            Ardentum is an analytical tool for education and research. It does not give investment advice. Model outputs are estimates based on historical data and stated assumptions; past performance does not predict future results.
          </p>
          {LEGAL.operator && (
            <p>
              Operated by {operatorDetails()}.
              {LEGAL.contactEmail && (
                <>
                  {" "}Contact:{" "}
                  <a href={`mailto:${LEGAL.contactEmail}`} className="underline underline-offset-2">
                    {LEGAL.contactEmail}
                  </a>
                  .
                </>
              )}
            </p>
          )}
        </div>
        <nav aria-label="Legal" className="flex shrink-0 flex-wrap gap-x-4 gap-y-2">
          {links.map((l) => (
            <Link key={l.href} href={l.href} className="underline-offset-2 hover:underline">
              {l.label}
            </Link>
          ))}
        </nav>
      </div>
    </footer>
  );
}
