"""Run all three studies on the real data and write results to research/results/.

Usage (from the repository root):
    uv run --project backend --with matplotlib python -m research.run_all
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from research import data
from research.studies import currency_hedging, one_over_n, promised_vs_realised

OUT = Path(__file__).parent / "results"


def main() -> None:
    started = time.time()
    industries = data.monthly_industries()
    factors = data.monthly_factors()
    fx = {"EUR": data.fx_month_end("EUR", "USD"), "GBP": data.fx_month_end("GBP", "USD")}
    rates = {c: data.policy_rate_month_end(c) for c in ("EUR", "GBP", "USD")}
    print(f"industries {industries.index[0].date()} to {industries.index[-1].date()}")
    if OUT.exists():
        shutil.rmtree(OUT)  # no stale tables or figures from an earlier version of a study
    one_over_n.run(industries, factors, OUT / "1_one_over_n")
    currency_hedging.run(industries, factors, fx, rates, OUT / "2_currency_hedging")
    promised_vs_realised.run(industries, factors, OUT / "3_promised_vs_realised")
    meta = {
        "industries_sample": [str(industries.index[0].date()), str(industries.index[-1].date())],
        "fx_sample": {k: [str(v.index[0].date()), str(v.index[-1].date())] for k, v in fx.items()},
        "runtime_seconds": round(time.time() - started, 1),
        "sources": [
            "Kenneth R. French Data Library: 12 Industry Portfolios, Fama/French 3 Factors (monthly)",
            "European Central Bank reference rates via Frankfurter",
            "BIS central bank policy rates (WS_CBPOL)",
        ],
    }
    (OUT / "run_metadata.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
