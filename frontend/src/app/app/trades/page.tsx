"use client";

import { useState } from "react";

import { PortfolioPicker, resolvePortfolio, useAvailablePortfolios } from "@/components/portfolio-picker";
import { Callout, Card, EmptyState, Field, NumberInput, Select, Stat, Table, Td, Th } from "@/components/ui";
import { ErrorCallout, ExportMenu, PageHeader, ResultsSkeleton, RunBar, Running, toCsv, useComputation, useDataset } from "@/components/workspace";
import { api, unwrap } from "@/lib/api/client";
import type { TradeOut, TradesRequest, TradesResponse } from "@/lib/api/types";
import { num, pct } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace";

const amount = (x: number | null | undefined) => num(x, 2);

const ORDER: Record<TradeOut["action"], number> = { sell: 0, buy: 1, hold: 2 };

export default function TradesPage() {
  const { state } = useWorkspace();
  const ds = useDataset(state.universe.dataset_id);
  const options = useAvailablePortfolios();
  const { data, error, running, run, request } = useComputation<TradesRequest, TradesResponse>("trades", (req) =>
    unwrap(api.POST("/api/v1/trades", { body: req })),
  );
  const [pick, setPick] = useState("working");
  const [holdings, setHoldings] = useState<Record<string, number>>(request?.holdings ?? {});
  const [flow, setFlow] = useState<"none" | "add" | "withdraw">(
    request?.new_money ? (request.new_money > 0 ? "add" : "withdraw") : "none",
  );
  const [flowAmount, setFlowAmount] = useState(Math.abs(request?.new_money ?? 0) || 1000);
  const [bps, setBps] = useState(request?.transaction_cost_bps ?? 10);
  const target = resolvePortfolio(options, pick);
  const tickers = Array.from(new Set([...Object.keys(target?.weights ?? {}), ...state.universe.tickers, ...Object.keys(holdings)]));
  const held = Object.values(holdings).reduce((a, b) => a + b, 0);
  const newMoney = flow === "none" ? 0 : flow === "add" ? flowAmount : -flowAmount;

  const submit = () => {
    if (!target) return;
    run({
      holdings: Object.fromEntries(Object.entries(holdings).filter(([, v]) => v > 0)),
      target: { name: target.name, weights: target.weights },
      new_money: newMoney,
      transaction_cost_bps: bps,
    });
  };

  // Synthetic assets and industry portfolios (a provider with a fixed list) cannot be bought as such.
  const notTradable = Boolean(ds.data && (ds.data.is_synthetic || ds.data.kind === "provider") && ds.data.assets.length > 0);

  return (
    <>
      <PageHeader
        title="Trade list"
        description="The trades that turn what you hold now into a target portfolio, after trading costs. Amounts are in your own currency. Nothing is sent to a broker, and the list is not advice."
      />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[22rem_minmax(0,1fr)]">
        <aside className="space-y-4">
          <Card title="Target">
            <PortfolioPicker value={pick} onChange={setPick} label="Target weights" />
          </Card>
          <Card title="What you hold now" subtitle="The current value of each holding. Leave empty for none.">
            <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
              {tickers.map((t) => (
                <div key={t} className="grid grid-cols-[minmax(0,1fr)_9rem] items-center gap-2">
                  <label htmlFor={`h-${t}`} className="truncate text-sm text-ink">
                    {t}
                    {target?.weights[t] ? <span className="ml-1.5 text-[11px] text-muted">target {pct(target.weights[t], 1)}</span> : null}
                  </label>
                  <NumberInput
                    id={`h-${t}`}
                    value={holdings[t] ?? null}
                    onChange={(v) => setHoldings((h) => ({ ...h, [t]: v ?? 0 }))}
                    min={0}
                    max={1e12}
                    allowEmpty
                    placeholder="0"
                  />
                </div>
              ))}
            </div>
            <p className="mt-2 text-xs text-ink-2">Total now: {amount(held)}</p>
          </Card>
          <Card title="Money and costs">
            <div className="space-y-3">
              <Field label="New money" htmlFor="flow">
                <Select id="flow" value={flow} onChange={(e) => setFlow(e.target.value as typeof flow)}>
                  <option value="none">None</option>
                  <option value="add">Add money</option>
                  <option value="withdraw">Withdraw money</option>
                </Select>
              </Field>
              {flow !== "none" && (
                <Field label={flow === "add" ? "Amount to add" : "Amount to withdraw"} htmlFor="flow-amount">
                  <NumberInput id="flow-amount" value={flowAmount} onChange={(v) => setFlowAmount(Math.abs(v ?? 0))} min={0} max={1e12} />
                </Field>
              )}
              <Field label="Trading cost" htmlFor="bps" hint="Basis points (hundredths of a percent) of each amount bought or sold, paid out of the portfolio.">
                <NumberInput id="bps" value={bps} onChange={(v) => setBps(v ?? 0)} min={0} max={500} suffix="bp" />
              </Field>
              <RunBar
                running={running}
                label="Make trade list"
                onRun={submit}
                disabled={!target || held + newMoney <= 0}
                note={held + newMoney <= 0 ? "Enter what you hold or some new money." : undefined}
              />
            </div>
          </Card>
        </aside>
        <div className="min-w-0">
          <ErrorCallout error={error} />
          {!data && running ? (
            <ResultsSkeleton />
          ) : !data ? (
            <EmptyState title="No trade list yet">Choose a target portfolio, enter what you hold now and make the list. The target can be the optimiser&apos;s portfolio, equal weights or a saved portfolio.</EmptyState>
          ) : (
            <Running running={running}>
              <Results data={data} notTradable={notTradable} />
            </Running>
          )}
        </div>
      </div>
    </>
  );
}

function Results({ data, notTradable }: { data: TradesResponse; notTradable: boolean }) {
  const rows = [...data.trades].sort((a, b) => ORDER[a.action] - ORDER[b.action] || Math.abs(b.trade) - Math.abs(a.trade));
  const csv = () =>
    toCsv([
      ["action", "asset", "current_value", "target_weight", "value_after", "trade", "cost"],
      ...rows.map((t) => [t.action, t.ticker, t.current_value, t.target_weight, t.target_value, t.trade, t.cost]),
    ]);
  const trades = rows.filter((t) => t.action !== "hold").length;
  return (
    <div className="space-y-4">
      <Card title={`${trades} trade${trades === 1 ? "" : "s"}`} subtitle="Sales first, then purchases, largest first." bodyClassName="p-0" actions={<ExportMenu name="ardentum-trade-list" json={data} csv={csv} />}>
        <div className="grid grid-cols-2 gap-2 p-4 md:grid-cols-4">
          <Stat label="Value now" value={amount(data.value_before)} />
          <Stat label="New money" value={amount(data.new_money)} />
          <Stat label="Trading costs" value={amount(data.total_costs)} />
          <Stat label="Value after" value={amount(data.value_after)} sub="invested at the target weights" />
        </div>
        <Table>
          <thead>
            <tr>
              <Th>Action</Th>
              <Th>Asset</Th>
              <Th align="right">Now</Th>
              <Th align="right">Target</Th>
              <Th align="right">After</Th>
              <Th align="right">Trade</Th>
              <Th align="right">Cost</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.ticker}>
                <Td className={t.action === "sell" ? "font-medium text-critical" : t.action === "buy" ? "font-medium text-good" : "text-muted"}>
                  {t.action === "sell" ? "Sell" : t.action === "buy" ? "Buy" : "Hold"}
                </Td>
                <Td className="font-medium">{t.ticker}</Td>
                <Td align="right">
                  {amount(t.current_value)}
                  <span className="block text-[11px] text-muted">{t.current_weight == null ? "n/a" : pct(t.current_weight, 1)}</span>
                </Td>
                <Td align="right">{pct(t.target_weight, 1)}</Td>
                <Td align="right">{amount(t.target_value)}</Td>
                <Td align="right">{amount(Math.abs(t.trade))}</Td>
                <Td align="right">{amount(t.cost)}</Td>
              </tr>
            ))}
            <tr>
              <Td className="font-medium">Total</Td>
              <Td />
              <Td align="right">{amount(data.value_before)}</Td>
              <Td align="right">100.0%</Td>
              <Td align="right">{amount(data.value_after)}</Td>
              <Td align="right">
                bought {amount(data.bought)}
                <span className="block text-[11px] text-muted">sold {amount(data.sold)}</span>
              </Td>
              <Td align="right">{amount(data.total_costs)}</Td>
            </tr>
          </tbody>
        </Table>
      </Card>
      {notTradable && (
        <Callout tone="warning" title="These assets are not directly tradable">
          Industry portfolios and synthetic assets cannot be bought as such. Use funds that follow the same industries, or upload prices for the funds you hold.
        </Callout>
      )}
      <Callout tone="info" title="How the list is made">
        {data.method}
      </Callout>
    </div>
  );
}
