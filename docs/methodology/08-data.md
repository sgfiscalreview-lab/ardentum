# Data

Where Ardentum's data comes from, how it is checked, and how the synthetic demo universe is generated.

## Sources

| Source | Status | Notes |
|---|---|---|
| **Synthetic demo universe** | Built in | Fictional assets for demonstration; never presented as market data. |
| **User uploads (CSV)** | Available to signed-in users | The uploader is responsible for the right to use the data; Ardentum does not verify it. |
| **Tiingo end-of-day prices** | Available when the deployment configures an API key | Split- and dividend-adjusted closes (`adjClose`). Tiingo's free plan is licensed for personal use; commercial use requires an appropriate plan. |
| **FRED (risk-free rate)** | Client implemented | 3-month Treasury constant-maturity yield (DGS3MO), U.S. government data published by the Federal Reserve Bank of St. Louis. |

Every result shows its data source, adjustment basis, licence note, window and number of observations.

## Validation and alignment

Price panels are checked before use:

- duplicate dates or tickers, non-numeric, infinite or non-positive prices → **rejected**;
- the common window starts at the **latest first available date** across the selected assets — earlier history is never back-filled; the loss of history is reported;
- gaps of up to 3 consecutive missing prices inside the window (typically holiday-calendar mismatches) are carried forward and **reported** (this yields zero returns on those dates); longer gaps are **rejected**, because filling them would understate volatility;
- daily moves above 50% and runs of 10+ identical prices are **flagged** as possible bad ticks, unadjusted splits or stale quotes.

## Uploading data

- **Wide format:** `date,AAA,BBB,...` with ISO dates (`YYYY-MM-DD`) and one column of adjusted closes per ticker.
- **Long format:** `date,ticker,adj_close` (also accepted: `close`, `price`).
- **Metadata (optional):** `ticker,name,sector,asset_class,esg_score,esg_source,esg_as_of`. An ESG score must have a source.
- Limits: 5 MB per file, 200 tickers, at least 31 prices per ticker. Ambiguous dates (e.g. `02/03/2024`) are rejected rather than guessed.

## The synthetic demo universe

The demo dataset contains 16 fictional equities across 11 sectors, a government-bond index, a corporate-bond index, gold and a market index — all with a `.SYN` ticker suffix — from 2011 to 2025. It is generated deterministically (fixed seed, versioned generator) by a factor model designed to reproduce the stylised facts that matter for testing portfolio tools (Cont, 2001):

- a **market factor** with GARCH(1,1) volatility clustering (Bollerslev, 1986; $\alpha=0.08$, $\beta=0.90$, unconditional volatility 16% p.a., drift 8% p.a.) and Student-t(6) shocks;
- **sector factors** (10% p.a. volatility), so correlations are higher within sectors;
- **idiosyncratic noise** with Student-t(5) fat tails;
- two generic **stress episodes** at arbitrary dates that do not replicate any historical crisis;
- **defensive assets**: a government-bond index with negative market beta.

Returns are $r_{i,t} = \alpha_i + \beta_i m_t + \lambda_i f_{s(i),t} + \varepsilon_{i,t}$. ESG scores for the demo assets are hand-chosen illustrative values (for instance, the fictional energy company scores low and the renewable utility high); gold and the index have no score, which exercises the missing-score rules.

Results computed on synthetic data demonstrate the methods; they say nothing about real securities.
