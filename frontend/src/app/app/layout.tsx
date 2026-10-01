import { Suspense, type ReactNode } from "react";

import { TourBar } from "@/components/tour-bar";
import { MobileStepNav, SharedLinkNotice, StepNav, UniverseSummary } from "@/components/workspace";

export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex max-w-[1600px]" data-print="results">
      <aside className="sticky top-12 hidden h-[calc(100vh-3rem)] w-60 shrink-0 flex-col gap-4 overflow-y-auto border-r border-line px-3 py-4 lg:flex">
        <StepNav />
        <UniverseSummary />
      </aside>
      <main className="min-w-0 flex-1 px-4 py-5 lg:px-6">
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
