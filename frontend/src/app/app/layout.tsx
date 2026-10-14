import { Suspense, type ReactNode } from "react";

import { TourBar } from "@/components/tour-bar";
import { MobileStepNav, SharedLinkNotice, StepNav, UniverseSummary } from "@/components/workspace";

export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex max-w-[100rem]" data-print="results">
      {/* A structural region, so a heavier, opaque tint (not a translucent material: the
          page does not scroll under it), inset with rounded corners. */}
      <aside className="sticky top-[3.75rem] m-3 mr-0 hidden h-[calc(100vh-4.5rem)] w-64 shrink-0 flex-col gap-5 overflow-y-auto rounded-2xl bg-sidebar px-3 py-4 lg:flex print:hidden">
        <StepNav />
        <UniverseSummary />
      </aside>
      <main className="min-w-0 flex-1 px-4 pb-10 pt-4 lg:px-8 lg:pt-7">
        <MobileStepNav />
        <Suspense fallback={null}>
          <TourBar />
        </Suspense>
        <SharedLinkNotice />
        {children}
      </main>
    </div>
  );
}
