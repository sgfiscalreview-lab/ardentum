"use client";

import { useState } from "react";

import type { AssetOut, ConstraintsIn, ObjectiveIn } from "@/lib/api/types";
import { OBJECTIVE_LABELS } from "@/lib/format";

import { Button, Checkbox, cx, DisclosureHint, Field, NumberInput, Select } from "./ui";

const OBJECTIVE_HELP: Record<ObjectiveIn["objective"], string> = {
  min_volatility: "Lowest expected volatility. Ignores expected returns, which are the noisiest input.",
  max_sharpe: "Highest expected excess return per unit of volatility (the tangency portfolio).",
  target_return: "Lowest volatility that still reaches a chosen expected return.",
  target_volatility: "Highest expected return without exceeding a chosen volatility.",
  max_utility: "Maximises return − (γ/2)·variance; higher γ means more risk-averse.",
  min_cvar: "Smallest average loss in the worst periods of the history (historical CVaR). Uses the actual return distribution, including fat tails.",
  risk_parity:
    "Every holding contributes the same share of risk. Uses no expected returns. The weights come from the risks alone, so your weight limits must leave room for them: low-risk assets can need large weights.",
};

export function ObjectivePanel({ value, onChange }: { value: ObjectiveIn; onChange: (v: ObjectiveIn) => void }) {
  const o = value.objective;
  return (
    <div className="space-y-3">
      <Field label="Objective" htmlFor="objective" hint={OBJECTIVE_HELP[o]}>
        <Select
          id="objective"
          value={o}
          onChange={(e) => {
            const next = e.target.value as ObjectiveIn["objective"];
            onChange({
              objective: next,
              target_return: next === "target_return" ? (value.target_return ?? 0.08) : null,
              target_volatility: next === "target_volatility" ? (value.target_volatility ?? 0.12) : null,
              risk_aversion: next === "max_utility" ? (value.risk_aversion ?? 4) : null,
              cvar_confidence: value.cvar_confidence ?? 0.95,
            });
          }}
        >
          {Object.entries(OBJECTIVE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </Select>
      </Field>
      {o === "target_return" && (
        <Field label="Target expected return (annual)" htmlFor="target-return">
          <NumberInput id="target-return" value={value.target_return} onChange={(v) => onChange({ ...value, target_return: v ?? 0 })} scale={100} suffix="%" min={-50} max={200} />
        </Field>
      )}
      {o === "target_volatility" && (
        <Field label="Target volatility (annual)" htmlFor="target-vol">
          <NumberInput id="target-vol" value={value.target_volatility} onChange={(v) => onChange({ ...value, target_volatility: v ?? 0.1 })} scale={100} suffix="%" min={0.1} max={200} />
        </Field>
      )}
      {o === "min_cvar" && (
        <>
          <Field label="CVaR confidence" htmlFor="cvar-conf" hint="95% means the average loss in the worst 5% of periods.">
            <Select id="cvar-conf" value={String(value.cvar_confidence ?? 0.95)} onChange={(e) => onChange({ ...value, cvar_confidence: Number(e.target.value) })}>
              <option value="0.9">90%</option>
              <option value="0.95">95%</option>
              <option value="0.975">97.5%</option>
              <option value="0.99">99%</option>
            </Select>
          </Field>
          <Field label="Minimum expected return (optional)" htmlFor="cvar-target">
            <NumberInput id="cvar-target" value={value.target_return ?? null} onChange={(v) => onChange({ ...value, target_return: v })} scale={100} suffix="%" min={-50} max={200} allowEmpty placeholder="None" />
          </Field>
        </>
      )}
      {o === "max_utility" && (
        <Field label="Risk aversion γ" htmlFor="gamma" hint="Typical values 2–10.">
          <NumberInput id="gamma" value={value.risk_aversion} onChange={(v) => onChange({ ...value, risk_aversion: v ?? 4 })} min={0.01} max={100} />
        </Field>
      )}
    </div>
  );
}

function Chips({
  options,
  selected,
  onChange,
  label,
  render,
}: {
  options: string[];
  selected: string[];
  onChange: (v: string[]) => void;
  label: string;
  render?: (o: string) => string;
}) {
  const [adding, setAdding] = useState("");
  const remaining = options.filter((o) => !selected.includes(o));
  return (
    <div>
      <div className="mb-1.5 flex flex-wrap gap-1">
        {selected.length === 0 && <span className="text-xs text-muted">None</span>}
        {selected.map((s) => (
          <span key={s} className="inline-flex items-center gap-1 rounded border border-line bg-surface-2 px-1.5 py-0.5 text-xs text-ink">
            {render ? render(s) : s}
            <button type="button" className="text-muted hover:text-ink" aria-label={`Remove ${s}`} onClick={() => onChange(selected.filter((x) => x !== s))}>
              ×
            </button>
          </span>
        ))}
      </div>
      {remaining.length > 0 && (
        <Select
          aria-label={label}
          value={adding}
          onChange={(e) => {
            const v = e.target.value;
            if (v) onChange([...selected, v]);
            setAdding("");
          }}
        >
          <option value="">Add…</option>
          {remaining.map((o) => (
            <option key={o} value={o}>
              {render ? render(o) : o}
            </option>
          ))}
        </Select>
      )}
    </div>
  );
}

function Section({ title, children, defaultOpen = true }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  return (
    <details open={defaultOpen} className="group border-t border-line pt-3">
      <summary className="mb-2 flex cursor-pointer list-none items-center justify-between text-xs font-semibold uppercase tracking-wide text-ink-2">
        {title}
        <DisclosureHint />
      </summary>
      <div className="space-y-3">{children}</div>
    </details>
  );
}

export function ConstraintsPanel({
  value,
  onChange,
  assets,
  tickers,
  showEsg = true,
}: {
  value: ConstraintsIn;
  onChange: (v: Partial<ConstraintsIn>) => void;
  assets: AssetOut[];
  tickers: string[];
  showEsg?: boolean;
}) {
  const inUniverse = assets.filter((a) => tickers.includes(a.ticker));
  const sectors = Array.from(new Set(inUniverse.map((a) => a.sector).filter((s): s is string => !!s))).sort();
  const scored = inUniverse.filter((a) => a.esg_score != null);
  const unscored = inUniverse.filter((a) => a.esg_score == null).map((a) => a.ticker);
  const maxEsg = scored.length ? Math.max(...scored.map((a) => a.esg_score ?? 0)) : null;
  const allowShort = value.min_weight < 0;
  const sectorLimits = value.sector_limits ?? [];
  return (
    <div className="space-y-3">
      <Section title="Position limits">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Min weight" htmlFor="min-w">
            <NumberInput id="min-w" value={value.min_weight} onChange={(v) => onChange({ min_weight: v ?? 0 })} scale={100} suffix="%" min={-100} max={100} />
          </Field>
          <Field label="Max weight" htmlFor="max-w">
            <NumberInput id="max-w" value={value.max_weight} onChange={(v) => onChange({ max_weight: v ?? 1 })} scale={100} suffix="%" min={0} max={100} />
          </Field>
        </div>
        <Checkbox
          checked={allowShort}
          onChange={(v) => onChange(v ? { min_weight: -0.2, max_gross_exposure: value.max_gross_exposure ?? 1.5 } : { min_weight: 0, max_gross_exposure: null })}
          label="Allow short positions"
          hint="Negative minimum weight; gross exposure capped. ESG settings require long-only."
        />
        {allowShort && (
          <Field label="Max gross exposure (Σ|w|)" htmlFor="gross">
            <NumberInput id="gross" value={value.max_gross_exposure} onChange={(v) => onChange({ max_gross_exposure: v })} scale={100} suffix="%" min={100} max={300} allowEmpty />
          </Field>
        )}
        <Field label="Excluded assets">
          <Chips label="Exclude an asset" options={tickers} selected={value.excluded_assets ?? []} onChange={(v) => onChange({ excluded_assets: v })} />
        </Field>
      </Section>

      <Section title="Sector limits" defaultOpen={sectorLimits.length > 0}>
        {sectors.length === 0 ? (
          <p className="text-xs text-muted">No sector data for these assets.</p>
        ) : (
          <>
            {sectorLimits.map((lim, i) => (
              <div key={i} className="grid grid-cols-[1fr_4.5rem_4.5rem_auto] items-end gap-1.5">
                <Field label={i === 0 ? "Sector" : ""}>
                  <Select
                    aria-label="Sector"
                    value={lim.sector}
                    onChange={(e) => onChange({ sector_limits: sectorLimits.map((x, j) => (j === i ? { ...x, sector: e.target.value } : x)) })}
                  >
                    {sectors.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </Select>
                </Field>
                <Field label={i === 0 ? "Min" : ""}>
                  <NumberInput ariaLabel="Sector minimum" value={lim.min_weight} allowEmpty onChange={(v) => onChange({ sector_limits: sectorLimits.map((x, j) => (j === i ? { ...x, min_weight: v } : x)) })} scale={100} suffix="%" min={0} max={100} />
                </Field>
                <Field label={i === 0 ? "Max" : ""}>
                  <NumberInput ariaLabel="Sector maximum" value={lim.max_weight} allowEmpty onChange={(v) => onChange({ sector_limits: sectorLimits.map((x, j) => (j === i ? { ...x, max_weight: v } : x)) })} scale={100} suffix="%" min={0} max={100} />
                </Field>
                <Button size="sm" variant="ghost" aria-label="Remove sector limit" onClick={() => onChange({ sector_limits: sectorLimits.filter((_, j) => j !== i) })}>
                  ×
                </Button>
              </div>
            ))}
            <Button size="sm" onClick={() => onChange({ sector_limits: [...sectorLimits, { sector: sectors[0] ?? "", min_weight: null, max_weight: 0.3 }] })}>
              Add sector limit
            </Button>
          </>
        )}
      </Section>

      {showEsg && (
        <Section title="ESG" defaultOpen={value.min_esg_score != null || (value.esg_tilt ?? 0) > 0 || (value.excluded_sectors ?? []).length > 0}>
          {scored.length === 0 ? (
            <p className="text-xs text-muted">No ESG scores for these assets. Upload metadata with scores and their source to use ESG constraints.</p>
          ) : (
            <>
              <Field
                label="Minimum portfolio ESG score"
                htmlFor="min-esg"
                hint={maxEsg != null ? `Value-weighted average, 0–100. Best available asset: ${maxEsg.toFixed(0)}.` : undefined}
              >
                <NumberInput id="min-esg" value={value.min_esg_score} onChange={(v) => onChange({ min_esg_score: v })} min={0} max={100} allowEmpty placeholder="No minimum" />
              </Field>
              <Field label="ESG preference (tilt)" htmlFor="tilt" hint="Extra expected return credited per 1 standard deviation of ESG score, in return-seeking objectives only. Reported returns stay unadjusted.">
                <NumberInput id="tilt" value={value.esg_tilt} onChange={(v) => onChange({ esg_tilt: v ?? 0 })} scale={100} suffix="%" min={0} max={20} />
              </Field>
              <Field label="Excluded sectors">
                <Chips label="Exclude a sector" options={sectors} selected={value.excluded_sectors ?? []} onChange={(v) => onChange({ excluded_sectors: v })} />
              </Field>
              {unscored.length > 0 && (
                <Checkbox
                  checked={!!value.exclude_unscored_assets}
                  onChange={(v) => onChange({ exclude_unscored_assets: v })}
                  label={`Exclude assets without an ESG score (${unscored.join(", ")})`}
                  hint="Scores are never imputed. Without this, ESG constraints fail when an unscored asset is investable."
                />
              )}
            </>
          )}
        </Section>
      )}

      <Section title="Tracking error" defaultOpen={value.tracking_error != null}>
        <Checkbox
          checked={value.tracking_error != null}
          onChange={(v) => onChange({ tracking_error: v ? { benchmark: "equal_weight", max_tracking_error: 0.04 } : null })}
          label="Limit ex-ante tracking error vs. equal weight"
        />
        {value.tracking_error && (
          <Field label="Maximum tracking error (annual)" htmlFor="te">
            <NumberInput
              id="te"
              value={value.tracking_error.max_tracking_error}
              onChange={(v) => value.tracking_error && onChange({ tracking_error: { ...value.tracking_error, max_tracking_error: v ?? 0.04 } })}
              scale={100}
              suffix="%"
              min={0.1}
              max={50}
            />
          </Field>
        )}
      </Section>
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    held: { label: "Held", cls: "bg-accent-wash text-accent-ink" },
    at_upper_bound: { label: "At max", cls: "bg-warn-wash text-warn" },
    at_lower_bound: { label: "At min", cls: "bg-warn-wash text-warn" },
    zero_by_optimiser: { label: "Not held", cls: "bg-surface-2 text-ink-2" },
    excluded: { label: "Excluded", cls: "bg-surface-2 text-ink-2" },
  };
  const m = map[status] ?? { label: status, cls: "bg-surface-2 text-ink-2" };
  return <span className={cx("inline-block rounded px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap", m.cls)}>{m.label}</span>;
}
