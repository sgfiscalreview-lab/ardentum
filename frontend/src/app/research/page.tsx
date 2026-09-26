import type { Metadata } from "next";
import Link from "next/link";

import { listDocs } from "@/lib/docs";

export const metadata: Metadata = { title: "Research & methodology" };

export default function ResearchIndex() {
  const docs = listDocs();
  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">Research</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink">Methodology</h1>
      <p className="mt-2 max-w-2xl text-ink-2">
        The definitions, models, assumptions and limitations behind every number in Ardentum, with references to the primary literature.
      </p>
      <ol className="mt-8 divide-y divide-[var(--border)] rounded-lg border border-line bg-surface">
        {docs.map((d, i) => (
          <li key={d.slug}>
            <Link href={`/research/${d.slug}`} className="flex gap-4 px-5 py-4 hover:bg-surface-2">
              <span className="w-6 shrink-0 pt-0.5 text-sm text-muted tabular">{i + 1}</span>
              <span>
                <span className="block font-medium text-ink">{d.title}</span>
                <span className="mt-0.5 block text-sm text-ink-2">{d.summary}</span>
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </main>
  );
}
