import fs from "node:fs";
import path from "node:path";

/** Methodology documents live in /docs/methodology at the repository root. */
// Read at build time only (pages are statically generated), so exclude from file tracing.
const DOCS_DIR = process.env.DOCS_DIR ?? path.join(/*turbopackIgnore: true*/ process.cwd(), "..", "docs", "methodology");

export interface DocMeta {
  slug: string;
  title: string;
  summary: string;
  order: number;
}

function parse(file: string): DocMeta & { body: string } {
  const raw = fs.readFileSync(path.join(DOCS_DIR, file), "utf8");
  const m = /^(\d+)-(.+)\.md$/.exec(file);
  const lines = raw.split("\n");
  const title = (lines.find((l) => l.startsWith("# ")) ?? "# Untitled").slice(2).trim();
  const afterTitle = lines.slice(lines.findIndex((l) => l.startsWith("# ")) + 1);
  const summary = afterTitle.find((l) => l.trim() !== "")?.trim() ?? "";
  // The summary line is shown as a lead paragraph, so drop it from the body.
  const body = afterTitle.join("\n").replace(summary, "").trim();
  return { slug: m?.[2] ?? file, order: Number(m?.[1] ?? 99), title, summary, body };
}

export function listDocs(): DocMeta[] {
  return fs
    .readdirSync(DOCS_DIR)
    .filter((f) => /^\d+-.+\.md$/.test(f))
    .map((f) => {
      const { slug, title, summary, order } = parse(f);
      return { slug, title, summary, order };
    })
    .sort((a, b) => a.order - b.order);
}

export function getDoc(slug: string): (DocMeta & { body: string }) | null {
  const file = fs.readdirSync(DOCS_DIR).find((f) => f.replace(/^\d+-/, "").replace(/\.md$/, "") === slug);
  return file ? parse(file) : null;
}
