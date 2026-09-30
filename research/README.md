# Research studies built on Ardentum

Three empirical studies that use Ardentum's engine (`backend/src/ardentum`) on free public
data. Each is reproducible: `research/run_all.py` downloads the data, runs every
calculation and writes tables, figures and JSON to `research/results/`.

| Study | Question | Code |
|---|---|---|
| 1. The 1/N puzzle, twenty years later | Does optimising a portfolio beat equal weights out of sample, and did the 2009 answer survive the years since? | `studies/one_over_n.py` |
| 2. Should a European investor hedge the dollar? | For euro and sterling investors in US shares (1999 onwards), does hedging reduce risk, and in crises? | `studies/currency_hedging.py` |
| 3. The optimiser's promise versus reality | How far do optimised portfolios fall short of the Sharpe ratio they promise, and how much does shrinkage help? | `studies/promised_vs_realised.py` |

## Reproduce

```bash
uv run --project backend --with matplotlib python -m research.run_all
```
(or Actions tab > Research studies > Run workflow). Needs internet access for the first run;
raw downloads are cached in `research/data/raw/`.

## Data
* Kenneth R. French Data Library (Tuck School of Business, Dartmouth): 12 Industry
  Portfolios and Fama/French research factors, monthly.
* European Central Bank euro reference rates, via Frankfurter.
* Bank for International Settlements, central-bank policy rates (WS_CBPOL).

## Method notes
* No look-ahead: every portfolio uses only data available at its formation date.
* Statistical test of Sharpe differences: Jobson and Korkie (1981) with Memmel's (2003)
  correction, as in DeMiguel, Garlappi and Uppal (2009).
* Currency hedge: one-month forward re-set monthly, priced by covered interest parity from
  policy rates (a proxy for the interbank rates that price real forwards).
