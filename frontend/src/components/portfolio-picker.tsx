"use client";

import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { PortfolioOut } from "@/lib/api/types";
import { useAuth } from "@/lib/auth";
import { pct } from "@/lib/format";
import { equalWeights, useWorkspace } from "@/lib/workspace";

import { Field, Select } from "./ui";

export interface PickedPortfolio {
  key: string;
  name: string;
  weights: Record<string, number>;
}

export function useSavedPortfolios() {
  const { status } = useAuth();
  return useQuery({
    queryKey: ["portfolios"],
    queryFn: () => unwrap(api.GET("/api/v1/portfolios")),
    enabled: status === "signed_in",
  });
}

/** Portfolios available for the current dataset: working, equal weight, saved. */
export function useAvailablePortfolios(): PickedPortfolio[] {
  const { state } = useWorkspace();
  const saved = useSavedPortfolios();
  const out: PickedPortfolio[] = [];
  if (state.working && state.working.datasetId === state.universe.dataset_id) {
    out.push({ key: "working", name: `Working: ${state.working.name}`, weights: state.working.weights });
  }
  if (state.universe.tickers.length > 0) {
    out.push({ key: "equal", name: `Equal weight (${state.universe.tickers.length} assets)`, weights: equalWeights(state.universe.tickers) });
  }
  for (const p of (saved.data ?? []) as PortfolioOut[]) {
    if (p.dataset_id === state.universe.dataset_id) out.push({ key: `saved:${p.id}`, name: `Saved: ${p.name}`, weights: p.weights });
  }
  return out;
}

export function PortfolioPicker({
  value,
  onChange,
  label = "Portfolio",
  id = "portfolio",
}: {
  value: string;
  onChange: (key: string) => void;
  label?: string;
  id?: string;
}) {
  const options = useAvailablePortfolios();
  const current = options.find((o) => o.key === value) ?? options[0];
  return (
    <div className="space-y-2">
      <Field label={label} htmlFor={id}>
        <Select id={id} value={current?.key ?? ""} onChange={(e) => onChange(e.target.value)}>
          {options.map((o) => (
            <option key={o.key} value={o.key}>
              {o.name}
            </option>
          ))}
        </Select>
      </Field>
      {current && (
        <ul className="max-h-40 overflow-y-auto rounded-md border border-line bg-surface-2/50 px-2 py-1.5 text-xs">
          {Object.entries(current.weights)
            .sort((a, b) => b[1] - a[1])
            .map(([t, w]) => (
              <li key={t} className="flex justify-between tabular text-ink-2">
                <span>{t}</span>
                <span className="text-ink">{pct(w, 1)}</span>
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}

export function resolvePortfolio(options: PickedPortfolio[], key: string): PickedPortfolio | undefined {
  return options.find((o) => o.key === key) ?? options[0];
}
