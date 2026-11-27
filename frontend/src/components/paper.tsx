import katex from "katex";
import Link from "next/link";
import type { ReactNode } from "react";

import { LEGAL, SOURCE_URL } from "@/lib/legal";
import { REFERENCES, type RefKey } from "@/lib/study-references";
import type { StudyMeta } from "@/lib/studies";

/**
 * The layout of a research note: a title block, abstract, numbered sections, captioned
 * tables and figures, display equations, author-year citations and a reference list.
 */

export const PUBLISHED = "November 2026";

/** The author shown on the notes: the site's operator when configured. */
export const AUTHOR = LEGAL.operator || "Ardentum Research";

export function Paper({
  meta,
  dataThrough,
  abstract,
  refs,
  children,
}: {
  meta: StudyMeta;
  dataThrough: string;
  abstract: ReactNode;
  refs: RefKey[];
  children: ReactNode;
}) {
  const url = `https://ardentum-frontend.pages.dev/research/studies/${meta.slug}`;
  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <nav aria-label="Breadcrumb" className="text-footnote font-semibold text-accent-ink">
        <Link href="/research">Research</Link>
        <span className="px-1.5 text-muted" aria-hidden>
          /
        </span>
        <Link href="/research/studies">Studies</Link>
      </nav>
      <article className="prose-doc mt-3">
        <header>
          <p className="text-footnote text-muted">Ardentum Research Note No. {meta.number}</p>
          <h1 className="mt-2">{meta.title}</h1>
          <p className="text-ink-2">
            {AUTHOR}. {PUBLISHED}. Data through {dataThrough}.
          </p>
        </header>

        <section aria-labelledby="abstract" className="mt-6 rounded-lg border border-line bg-surface px-5 py-4 elev-1">
          <h2 id="abstract" className="!mt-0 !text-base">
            Abstract
          </h2>
          <div className="text-subheadline">{abstract}</div>
          <p className="!mb-0 text-footnote text-ink-2">
            <span className="font-semibold text-ink">Keywords:</span> {meta.keywords.join(", ")}.{" "}
            <span className="font-semibold text-ink">JEL classification:</span> {meta.jel.join(", ")}.
          </p>
        </section>

        {children}

        <Section n="" title="Data and code availability">
          <p>
            Every table and figure in this note is drawn from the recorded output of the study code, which runs Ardentum&apos;s portfolio engine on the public data cited below.
            No number was entered by hand. The code, the data loaders and the results are published in the{" "}
            <a href={`${SOURCE_URL}/tree/main/research`}>research folder of the Ardentum repository</a> under the MIT licence, and an automated workflow reruns the study
            whenever its code changes. Rerunning it on the same data reproduces every number shown here.
          </p>
        </Section>

        <Section n="" title="References">
          <ol className="!list-none !pl-0 space-y-2 text-subheadline">
            {[...refs]
              .sort((a, b) => REFERENCES[a].full.localeCompare(REFERENCES[b].full))
              .map((k) => (
                <li key={k} id={`ref-${k}`} className="pl-6 -indent-6">
                  {REFERENCES[k].full}
                </li>
              ))}
          </ol>
        </Section>

        <section aria-labelledby="cite-as" className="mt-10 rounded-lg border border-line bg-surface-2 px-5 py-4">
          <h2 id="cite-as" className="!mt-0 !text-base">
            Suggested citation
          </h2>
          <p className="!mb-0 text-subheadline">
            {AUTHOR} ({PUBLISHED.split(" ")[1]}). {meta.title}. Ardentum Research Note No. {meta.number}. {url}
          </p>
        </section>

        <p className="text-footnote text-muted">
          Ardentum is a tool for education and research. This note describes past data and a stated model; it is not investment advice.
        </p>
      </article>
    </main>
  );
}

export function Section({ n, title, children }: { n: string; title: string; children: ReactNode }) {
  const id = title.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return (
    <section aria-labelledby={id}>
      <h2 id={id}>
        {n && <span className="mr-2 text-muted">{n}</span>}
        {title}
      </h2>
      {children}
    </section>
  );
}

export function Sub({ n, title, children }: { n: string; title: string; children: ReactNode }) {
  return (
    <>
      <h3>
        <span className="mr-2 text-muted">{n}</span>
        {title}
      </h3>
      {children}
    </>
  );
}

/** A display equation, typeset at build time (MathML is included for screen readers). */
export function Eq({ tex, label }: { tex: string; label?: string }) {
  const html = katex.renderToString(tex, { displayMode: true, throwOnError: true, output: "htmlAndMathml" });
  return (
    <div className="flex items-center gap-3">
      {/* The wrapper scrolls a wide formula and is focusable, so keyboard users can reach it. */}
      <div className="min-w-0 flex-1 overflow-x-auto [&_.katex-display]:!overflow-visible" tabIndex={0} dangerouslySetInnerHTML={{ __html: html }} />
      {label && <span className="shrink-0 text-footnote text-muted">({label})</span>}
    </div>
  );
}

/** Inline mathematics. */
export function M({ tex }: { tex: string }) {
  return <span dangerouslySetInnerHTML={{ __html: katex.renderToString(tex, { throwOnError: true, output: "htmlAndMathml" }) }} />;
}

/** An author-year citation linked to the reference list: "Lo (2002)" or, with `p`, "(Lo, 2002)". */
export function Cite({ k, p = false }: { k: RefKey; p?: boolean }) {
  const r = REFERENCES[k];
  return <a href={`#ref-${k}`}>{p ? `(${r.cite}, ${r.year})` : `${r.cite} (${r.year})`}</a>;
}

/** A numbered table with its caption above and an optional note below. */
export function PaperTable({
  n,
  caption,
  head,
  rows,
  note,
}: {
  n: number;
  caption: string;
  head: ReactNode[];
  rows: ReactNode[][];
  note?: ReactNode;
}) {
  const id = `table-${n}`;
  return (
    // Tables may use more width than the text on large screens; they scroll on small ones.
    <figure className="my-6 xl:-mx-20">
      <figcaption id={id} className="text-subheadline">
        <span className="font-semibold">Table {n}.</span> {caption}
      </figcaption>
      {/* Focusable so keyboard users can scroll a wide table (WCAG 2.1.1). */}
      <table tabIndex={0} aria-labelledby={id} className="tabular-nums text-footnote">
        <thead>
          <tr>
            {head.map((h, i) => (
              <th key={i} scope="col" className={i > 0 ? "!px-2.5 !text-right align-bottom" : "!px-2.5 align-bottom"}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((c, j) =>
                j === 0 ? (
                  <th key={j} scope="row" className="min-w-[10.5rem] !bg-transparent !px-2.5 !font-normal">
                    {c}
                  </th>
                ) : (
                  <td key={j} className="!px-2.5 !text-right whitespace-nowrap">
                    {c}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {note && <p className="!mt-2 text-footnote text-ink-2">{note}</p>}
    </figure>
  );
}
