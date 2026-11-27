import type { Metadata } from "next";
import Link from "next/link";

import { AUTHOR, PUBLISHED } from "@/components/paper";
import { monthYear, runMetadata, STUDIES } from "@/lib/studies";

export const metadata: Metadata = {
  title: "Research studies",
  description: "Empirical studies of portfolio construction run with Ardentum's engine on public data, each fully reproducible.",
};

export default function StudiesIndex() {
  const meta = runMetadata();
  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <nav aria-label="Breadcrumb" className="text-footnote font-semibold text-accent-ink">
        <Link href="/research">Research</Link>
      </nav>
      <h1 className="type-title-1 mt-2 text-ink">Research studies</h1>
      <p className="mt-2 max-w-2xl text-ink-2">
        Empirical studies of portfolio construction, run with Ardentum&apos;s engine on public data from the Kenneth R. French Data Library, the European Central Bank and
        the Bank for International Settlements. Every number is reproduced from published code, and the studies are rerun on the latest data whenever the code changes. Data
        through {monthYear(meta.industries_sample[1])}.
      </p>
      <ol className="mt-8 space-y-4">
        {STUDIES.map((s) => (
          <li key={s.slug}>
            <Link href={`/research/studies/${s.slug}`} className="block rounded-lg border border-line bg-surface px-5 py-4 elev-1 hover:bg-surface-2">
              <span className="block text-footnote text-muted">
                Research Note No. {s.number}. {AUTHOR}, {PUBLISHED}.
              </span>
              <span className="mt-1 block font-semibold text-ink">{s.title}</span>
              <span className="mt-1 block text-subheadline leading-relaxed text-ink-2">{s.summary}</span>
            </Link>
          </li>
        ))}
      </ol>
    </main>
  );
}
