import type { Metadata } from "next";
import Link from "next/link";

import { listDocs } from "@/lib/docs";
import { GLOSSARY } from "@/lib/glossary";

export const metadata: Metadata = {
  title: "Glossary",
  description: "Plain definitions of the terms Ardentum uses, each linked to its formulas.",
};

const link = "text-accent-ink underline underline-offset-2";

export default function GlossaryPage() {
  const titles = new Map(listDocs().map((d) => [d.slug, d.title]));
  const entries = [...GLOSSARY].sort((a, b) => a.term.localeCompare(b.term));
  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">Glossary</p>
      <h1 className="mt-2 font-display text-3xl font-semibold text-ink">What the terms mean</h1>
      <p className="mt-2 text-ink-2">
        Short definitions of the terms on Ardentum&apos;s pages. Labels with a dotted underline in the workspace link
        here; the <Link href="/research" className={link}>methodology</Link> has the formulas.
      </p>
      <dl className="mt-8 divide-y divide-line border-y border-line">
        {entries.map((e) => (
          <div key={e.id} id={e.id} className="scroll-mt-16 py-4">
            <dt className="font-medium text-ink">{e.term}</dt>
            <dd className="mt-1 text-sm leading-relaxed text-ink-2">
              {e.definition}
              {e.method && titles.has(e.method) && (
                <>
                  {" "}
                  <Link href={`/research/${e.method}`} className={link}>
                    Formulas: {titles.get(e.method)}
                  </Link>
                </>
              )}
            </dd>
          </div>
        ))}
      </dl>
    </main>
  );
}
