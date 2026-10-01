"use client";

import { useSyncExternalStore } from "react";

import { Button } from "@/components/ui";

const noop = () => () => {};

/** The address of this website, for students working from a printed sheet. */
export function SiteAddress() {
  const host = useSyncExternalStore(
    noop,
    () => window.location.host,
    () => "",
  );
  return <span className="font-medium text-ink">{host || "this website"}</span>;
}

export function PrintButton() {
  return (
    <Button variant="primary" className="print:hidden" onClick={() => window.print()}>
      Print the worksheet
    </Button>
  );
}
