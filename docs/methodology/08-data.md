# Data

Where Ardentum's data comes from, how it is checked, and how the synthetic demo universe is generated.

## Sources

| Source | Status | Notes |
|---|---|---|
| **Synthetic demo universe** | Built in | Fictional assets for demonstration; never presented as market data. |
| **User uploads (CSV)** | Available to signed-in users | The uploader is responsible for the right to use the data; Ardentum does not verify it. |
| **Tiingo end-of-day prices** | Available when the deployment configures an API key | Split- and dividend-adjusted closes (`adjClose`). Tiingo's free plan is licensed for personal use; commercial use requires an appropriate plan. |
| **Kenneth French Data Library** | Built in (`kf12`, `kf49`) | Daily value-weighted returns of 12 or 49 US industry portfolios (all NYSE, AMEX and NASDAQ stocks grouped by SIC code) and the US market since 1926, from Prof. Kenneth R. French (Dartmouth). Free, no key; cite the library. |
| **FRED (risk-free rate)** | When a free API key is configured | 3-month Treasury bill yield (DGS3MO), U.S. government data published by the Federal Reserve Bank of St. Louis. |
| **Fama-French RF (risk-free rate)** | Built in | 1-month Treasury bill return, from the Kenneth French factors file. |
| **Exchange rates** | Built in | European Central Bank euro reference rates (daily since 1999), served by Frankfurter. Free, no key. |
| **Central-bank policy rates (currency hedging)** | Built in | Daily policy rates of about 30 central banks from the Bank for International Settlements (BIS, dataset WS_CBPOL). Free, no key; reuse allowed with the BIS cited as the source. |

Every result shows its data source, adjustment basis, licence note, window and number of observations.

## Validation and alignment

Price panels are checked before use:

- duplicate dates or tickers, non-numeric, infinite or non-positive prices are **rejected**;
- the common window starts at the **latest first available date** across the selected assets; earlier history is never back-filled, and the loss of history is reported;
- gaps of up to 3 consecutive missing prices inside the window (typically holiday-calendar mismatches) are carried forward and **reported** (this yields zero returns on those dates); longer gaps are **rejected**, because filling them would understate volatility;
- daily moves above 50% and runs of 10+ identical prices are **flagged** as possible bad ticks, unadjusted splits or stale quotes.

## Risk-free rate

The risk-free rate is an input you set; the Universe page can fill it with a historical average over the estimation window (last five years if no window is set):

- **Fama-French RF**: realised daily 1-month T-bill returns $r_t$, compounded and annualised: $R_f = \left(\prod_t (1+r_t)\right)^{252/n} - 1$.
- **FRED DGS3MO**: each daily 3-month bill yield $y_t$ is quoted on an investment (bond-equivalent) basis, i.e. a simple rate on a 365-day year; rolling 91-day bills gives the effective annual rate $(1+y_t\cdot 91/365)^{365/91}-1$. The window average of these is used.

The source and window are echoed with every result.

## Currencies

Each asset has a quote currency. Results are expressed in one currency: if the selected assets are quoted in different currencies you must choose a **base currency**. A price $P_L$ in local currency is converted with the exchange rate $X$ (units of base per unit of local): $P_B = P_L X$, so

$$1 + r_B = (1 + r_L)(1 + r_X).$$

This is the **unhedged** return: a base-currency investor bears both the asset's and the currency's return. Rates are ECB reference rates (published on ECB business days since 4 January 1999); on dates without a published rate the previous rate is used for at most five days. Prices before 1999, or across a longer gap, are rejected rather than guessed.

### Currency-hedged returns

With hedging on, each period the investor sells forward the position's value at the start of the period (the hedge is re-set on every price date of the source data). Covered interest parity prices the forward as $F = X_{t-1}\,(1 + i_B\,\delta)/(1 + i_L\,\delta)$ for a period of $\delta$ years (calendar days / 365) and annual short rates $i_B$ (base) and $i_L$ (local) known at $t-1$. The base-currency return is then

$$r_H = r_L\,(1 + r_X) + \frac{1 + i_B\,\delta}{1 + i_L\,\delta} - 1 .$$

The local return is kept; the exchange rate affects only the period's gain (the $r_L r_X$ term), and the rate difference is the cost or income of hedging, the reason hedged foreign bonds earn roughly the base currency's rates. A constant price earns exactly the carry whatever the exchange rate does; with equal rates and a fixed exchange rate the hedged return equals the local return (automated tests, plus an independent day-by-day recomputation through the API).

Short rates are the issuing central banks' **policy rates** from the BIS, carried forward over up to ten days without a value. They stand in for the money-market rates that price forwards, which differ by small spreads; transaction costs and the forward bid-ask spread are ignored. Currencies whose central bank has no BIS policy-rate series (for example SGD, whose monetary policy works through the exchange rate) cannot be hedged and return a clear error.

## Uploading data

- **Wide format:** `date,AAA,BBB,...` with ISO dates (`YYYY-MM-DD`) and one column of adjusted closes per ticker.
- **Long format:** `date,ticker,adj_close` (also accepted: `close`, `price`).
- **Metadata (optional):** `ticker,name,sector,asset_class,currency,isin,market_cap,esg_score,esg_source,esg_as_of`. An ESG score must have a source. `currency` is the ISO 4217 quote currency (default USD); `isin` is validated with its check digit and is used to match open ESG data; `market_cap` (in the quote currency) is used for Black–Litterman equilibrium returns.
- Limits: 5 MB per file, 200 tickers, at least 31 prices per ticker. Ambiguous dates (e.g. `02/03/2024`) are rejected rather than guessed.

## The synthetic demo universe

The demo dataset contains 16 fictional equities across 11 sectors, a government-bond index, a corporate-bond index, gold and a market index, all with a `.SYN` ticker suffix, from 2011 to 2025. It is generated deterministically (fixed seed, versioned generator) by a factor model designed to reproduce the stylised facts that matter for testing portfolio tools (Cont, 2001):

- a **market factor** with GARCH(1,1) volatility clustering (Bollerslev, 1986; $\alpha=0.08$, $\beta=0.90$, unconditional volatility 16% p.a., drift 8% p.a.) and Student-t(6) shocks;
- **sector factors** (10% p.a. volatility), so correlations are higher within sectors;
- **idiosyncratic noise** with Student-t(5) fat tails;
- two generic **stress episodes** at arbitrary dates that do not replicate any historical crisis;
- **defensive assets**: a government-bond index with negative market beta.

Returns are $r_{i,t} = \alpha_i + \beta_i m_t + \lambda_i f_{s(i),t} + \varepsilon_{i,t}$. ESG scores for the demo assets are hand-chosen illustrative values (for instance, the fictional energy company scores low and the renewable utility high); gold and the index have no score, which exercises the missing-score rules.

Results computed on synthetic data demonstrate the methods; they say nothing about real securities.
