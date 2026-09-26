import "katex/dist/katex.min.css";

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { getDoc, listDocs } from "@/lib/docs";

export const dynamicParams = false;

export function generateStaticParams() {
  return listDocs().map((d) => ({ slug: d.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const doc = getDoc((await params).slug);
  return { title: doc?.title ?? "Research", description: doc?.summary };
}

export default async function ResearchDoc({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = getDoc(slug);
  if (!doc) notFound();
  const docs = listDocs();
  const i = docs.findIndex((d) => d.slug === slug);
  const prev = docs[i - 1];
  const next = docs[i + 1];
  return (
    <main className="mx-auto grid max-w-6xl gap-10 px-4 py-10 lg:grid-cols-[14rem_minmax(0,1fr)]">
      <nav aria-label="Methodology" className="hidden lg:block">
        <ol className="sticky top-20 space-y-1 text-sm">
          {docs.map((d) => (
            <li key={d.slug}>
              <Link
                href={`/research/${d.slug}`}
                aria-current={d.slug === slug ? "page" : undefined}
                className={d.slug === slug ? "font-medium text-ink" : "text-ink-2 hover:text-ink"}
              >
                {d.title}
              </Link>
            </li>
          ))}
        </ol>
      </nav>
      <article className="prose-doc min-w-0 max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">
          <Link href="/research">Methodology</Link>
        </p>
        <h1 className="mt-2">{doc.title}</h1>
        <p className="text-lg text-ink-2">{doc.summary}</p>
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[rehypeKatex]}
          components={{
            h1: () => null,
            a: ({ href, children }) =>
              href?.startsWith("/") ? (
                <Link href={href}>{children}</Link>
              ) : (
                <a href={href} target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              ),
          }}
        >
          {doc.body}
        </ReactMarkdown>
        <div className="mt-12 flex justify-between border-t border-line pt-4 text-sm">
          {prev ? <Link href={`/research/${prev.slug}`}>Previous: {prev.title}</Link> : <span />}
          {next ? <Link href={`/research/${next.slug}`}>Next: {next.title}</Link> : <span />}
        </div>
      </article>
    </main>
  );
}
