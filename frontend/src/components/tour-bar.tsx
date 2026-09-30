"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { TOUR, tourHref, tourStepFor } from "@/lib/tour";

/** Shown at the top of a workspace page opened from the guided tour (?tour=<step>). */
export function TourBar() {
  const pathname = usePathname();
  const params = useSearchParams();
  const n = tourStepFor(pathname, params.get("tour"));
  const step = n === null ? undefined : TOUR[n - 1];
  if (n === null || !step) return null;
  const next = TOUR[n];
  const link = "underline underline-offset-2";
  return (
    <aside aria-label="Guided tour" className="mb-4 rounded-sm border border-accent/30 bg-accent-wash px-3 py-2.5 text-sm">
      <p className="font-medium text-ink">
        Guided tour, step {n} of {TOUR.length}: {step.title}
      </p>
      <p className="mt-1 text-ink-2">
        <span className="font-medium text-ink">Try: </span>
        {step.tryThis}
      </p>
      <p className="mt-1 text-ink-2">
        <span className="font-medium text-ink">Look for: </span>
        {step.lookFor}
      </p>
      <nav aria-label="Tour steps" className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-ink">
        {n > 1 && (
          <Link href={tourHref(n - 1)} className={link}>
            Previous step
          </Link>
        )}
        {next ? (
          <Link href={tourHref(n + 1)} className={`${link} font-medium`}>
            Next step: {next.title}
          </Link>
        ) : (
          <Link href="/research" className={`${link} font-medium`}>
            Finish: read the methodology
          </Link>
        )}
        <Link href="/tour" className={link}>
          All steps
        </Link>
        <Link href={pathname} className={link}>
          Close the tour
        </Link>
      </nav>
    </aside>
  );
}
