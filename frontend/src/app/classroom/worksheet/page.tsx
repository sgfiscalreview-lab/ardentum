import type { Metadata } from "next";

import { EXERCISES, EXIT_QUESTION, EXTENSION } from "@/lib/classroom";

import { PrintButton, SiteAddress } from "../print-tools";

export const metadata: Metadata = { title: "Classroom worksheet" };

function AnswerBox() {
  return <div aria-hidden className="mt-1.5 h-16 rounded-sm border border-line print:h-14 print:border-line-strong" />;
}

function Questions({ items }: { items: string[] }) {
  return (
    <ol className="mt-3 space-y-3 pl-5 [list-style:lower-alpha] print:space-y-2">
      {items.map((q) => (
        <li key={q} className="break-inside-avoid text-sm text-ink">
          {q}
          <AnswerBox />
        </li>
      ))}
    </ol>
  );
}

export default function WorksheetPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-10 print:py-0">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">Classroom worksheet</p>
          <h1 className="mt-2 font-display text-3xl font-semibold text-ink">Risk, diversification and the optimiser&apos;s promise</h1>
        </div>
        <PrintButton />
      </div>
      <p className="mt-4 text-sm text-ink-2">
        Open <SiteAddress /> in a browser. You do not need to sign in. All the assets are invented (their names end in .SYN), so nothing here is investment advice.
      </p>
      <dl className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
        {["Name", "Class", "Date"].map((f) => (
          <div key={f} className="border-b border-line-strong pb-1">
            <dt className="text-ink-2">{f}</dt>
            <dd aria-hidden className="h-5" />
          </div>
        ))}
      </dl>

      {EXERCISES.map((ex, i) => (
        <section key={ex.title} className="mt-8 print:mt-5">
          <h2 className="break-after-avoid text-lg font-semibold text-ink">
            Exercise {i + 1}. {ex.title}
          </h2>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-ink-2">
            {ex.steps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
          <Questions items={ex.questions} />
        </section>
      ))}

      <section className="mt-8 print:mt-5">
        <h2 className="text-lg font-semibold text-ink">{EXTENSION.title}</h2>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-ink-2">
          {EXTENSION.steps.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ol>
        <Questions items={EXTENSION.questions} />
      </section>

      <section className="mt-8 break-inside-avoid print:mt-5">
        <h2 className="text-lg font-semibold text-ink">Before you leave</h2>
        <p className="mt-2 text-sm text-ink">{EXIT_QUESTION}</p>
        <AnswerBox />
      </section>
    </main>
  );
}
