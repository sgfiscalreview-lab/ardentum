# Crisis replay, factor exposure and trade lists

How a fixed portfolio is replayed through past crises, how its exposure to the Fama-French factors is estimated, and how a trade list reaches target weights after costs.

## Crisis replay

Each crisis runs from the US stock market's closing high before the crash to its closing low, so every portfolio is measured over the same dates. Dates are the S&P 500's closing high and low (S&P Dow Jones Indices); for 1929 to 1932 the Dow Jones Industrial Average's.

| Crisis | High | Low |
|---|---|---|
| 1929 crash and Great Depression | 3 Sep 1929 | 8 Jul 1932 |
| 1973 to 1974 oil crisis | 11 Jan 1973 | 3 Oct 1974 |
| 1987 crash (Black Monday) | 25 Aug 1987 | 4 Dec 1987 |
| Dot-com crash | 24 Mar 2000 | 9 Oct 2002 |
| Global financial crisis | 9 Oct 2007 | 9 Mar 2009 |
| COVID-19 crash | 19 Feb 2020 | 23 Mar 2020 |
| 2022 inflation and rate rises | 3 Jan 2022 | 12 Oct 2022 |

**Buy and hold.** The portfolio is bought at the close on the first day (or the last close before it, at most a week earlier) and then held without trading, so weights drift with prices. With starting weights $w_i$ and each asset's growth since the purchase $G_{i,t} = \prod_{s \le t} (1 + r_{i,s})$, the portfolio's value is

$$V_t = \sum_i w_i G_{i,t}, \qquad V_0 = 1.$$

Only returns dated after the purchase are used.

* **Return** over the period: $V_T - 1$. It splits exactly into contributions $w_i (G_{i,T} - 1)$.
* **Largest fall**: $\min_t \left( V_t / \max_{s \le t} V_s - 1 \right)$ inside the period, which can be larger than the period's return when the portfolio's low came on another day than the market's.
* **Worst day**: the smallest daily return $V_t / V_{t-1} - 1$.
* **Back to its previous high**: from the portfolio's low in the period, the first later date (using all later data, still without trading) on which $V_t$ is back at the highest value it had before that low, and the calendar days it took.
* **Market**: the same calculation for the dataset's market index (the Fama-French market return for US industries).

Daily prices are required: several crises last only weeks. The named crises need real data; on the synthetic demo data only periods the user chooses can be replayed, because synthetic dates contain no real events. A period that starts before the data or ends after it is reported as not available, with the reason.

**Verification.** Tests compare the value path with closed forms (constant returns), with a brute-force share-count calculation and with the general buy-and-hold function; contributions must add up to the return; changing every return up to the purchase must leave the result unchanged.

## Factor exposure

The Fama-French (1993) three-factor model explains a portfolio's return above the risk-free rate by three long-short factors:

$$r_t - r_{f,t} = \alpha + \beta_M (R_{M,t} - r_{f,t}) + \beta_S \,\text{SMB}_t + \beta_H \,\text{HML}_t + \varepsilon_t$$

* $R_M - r_f$: the US market's return above the risk-free rate (one-month Treasury bill).
* SMB (small minus big): small companies' shares minus large companies'.
* HML (high minus low): shares with high book-to-market ratios (cheap) minus low (expensive).

Factor and risk-free returns are Professor French's daily series from the Kenneth R. French Data Library. The portfolio is rebalanced to its weights every period (constant mix), over the window and frequency chosen on the Universe page.

**Estimation.** Ordinary least squares. Standard errors are Newey and West (1987): heteroskedasticity- and autocorrelation-consistent with Bartlett weights $1 - \ell/(L+1)$, $L = \lfloor 4 (T/100)^{2/9} \rfloor$ lags (Newey and West 1994) and the small-sample factor $T/(T-k)$, with $k = 4$ coefficients. p-values are two-sided from Student's t with $T - k$ degrees of freedom. A loading is called clear when its p-value is below 5%.

**Weekly and monthly returns.** Each period's factor returns are compounded from the days inside it: the risk-free rate and the market ($R_M = (R_M - r_f) + r_f$) as returns, the market's excess as their difference, and SMB and HML as the return of holding each long-short position through the period. Periods the factor data does not fully cover (before its start, after its latest update, or without a US trading day) are left out and reported.

**Decomposition.** Because least-squares residuals average zero when an intercept is included, the average excess return splits exactly:

$$\overline{r - r_f} = \alpha + \beta_M \overline{R_M - r_f} + \beta_S \overline{\text{SMB}} + \beta_H \overline{\text{HML}}.$$

Annualised arithmetically (times periods per year), these are the bars "where the average return came from". The portfolio's loadings equal the weighted loadings of its holdings, which are shown too.

**Limits.** Factor exposure needs real returns; synthetic demo data has no link to the real factors and is refused. The factors are US dollar returns: for returns in another currency, exchange-rate moves end up in alpha and the residual.

**Verification.** Coefficients, Newey-West standard errors, t-statistics, p-values and R-squared match statsmodels; the decomposition and the weighted-loadings identity hold to rounding; compounded weekly factors are checked by hand.

## Trade lists

Given current holdings $h_i$ (money values), new money $c$ (negative to withdraw), target weights $w_i$ and a trading cost $k$ per unit traded paid out of the portfolio, the value left invested after trading solves

$$V = \sum_i h_i + c - k \sum_i |w_i V - h_i|,$$

and the trades are $t_i = w_i V - h_i$. The right-hand side minus $V$ falls strictly as $V$ rises when $k \sum_i |w_i| < 1$ (always true for costs up to 500 basis points and the leverage the optimiser allows), so the solution is unique. It is found by bracketing root search (Brent's method) and then checked: what is sold plus new money must equal what is bought plus all costs. Holdings not in the target are sold. A withdrawal so large that nothing is left after costs is refused with the largest possible withdrawal.

Amounts are in the user's own currency; no prices or units are involved. Industry portfolios and synthetic assets cannot be bought as such, which the page says.

**Verification.** Closed forms (all purchases: $V = c/(1+k)$; a full switch: $V = H(1-k)/(1+k)$), the cash identity and the resulting weights for random inputs.
