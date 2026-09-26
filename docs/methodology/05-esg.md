# ESG methodology

How ESG scores enter portfolio construction, how their effect is measured, and the limits of ESG data.

## ESG data: provenance and limitations

An ESG score is a rating agency's **opinion**, not an observed quantity. Ratings from different providers are only weakly correlated — Berg, Kölbel & Rigobon (2022) report correlations between major raters of roughly 0.38 to 0.71, driven by differences in scope, measurement and weighting. Conclusions about the "ESG quality" of a portfolio therefore depend on the rating source.

Ardentum's rules:

- Scores are on a **0–100 scale, higher is better**. Scores from providers using other scales (for example risk scores where lower is better) must be converted before upload.
- Every score must carry its **source** (and ideally an as-of date). Uploads without a source are rejected.
- **Missing scores are never imputed.** ESG constraints fail with a message naming the unscored assets; the user can explicitly exclude them.
- The built-in demo dataset uses **synthetic, illustrative** scores that do not come from any rating provider, and says so on every screen.
- No licensed ESG dataset is bundled. Production use requires either user-supplied scores or a licensed provider (a business decision recorded in the project's decision log).

## How ESG changes the optimisation

ESG settings are part of the optimisation problem, not a label added afterwards.

| Setting | Formulation | Effect |
|---|---|---|
| Minimum portfolio score | $s^\top w \ge s_{\min}$ | Value-weighted average score must reach the floor. Linear, exact. |
| Sector exclusion | $w_i = 0$ for $i$ in excluded sectors | Negative screening. |
| Asset exclusion / exclude unscored | $w_i = 0$ | Removes assets from the investable set. |
| ESG preference ("tilt") | objective uses $\mu_i + \tau z_i$ | Soft preference; see below. |

The portfolio score $s^\top w$ is a convex combination of asset scores only when weights are non-negative and sum to one, so ESG settings require long-only portfolios.

### ESG preference (tilt)

Following the ESG-adjusted-return formulation of Pedersen, Fitzgibbons & Pomorski (2021), an investor who values ESG can treat a better score like extra expected return. With cross-sectionally standardised scores $z_i = (s_i - \bar s)/\operatorname{sd}(s)$ and a user-chosen premium $\tau$ (annual return per one standard deviation of score), return-seeking objectives (maximum Sharpe, target volatility, maximum utility) optimise with $\mu_i + \tau z_i$.

- The tilt changes **which portfolio is chosen**; all **reported** expected returns remain unadjusted financial estimates. The ESG-adjusted return used by the optimiser is shown separately.
- Minimum-volatility and target-return objectives have no expected-return term to tilt, so the tilt has no effect on them and Ardentum says so; use the minimum-score constraint instead.

## Measuring the cost of ESG

The ESG impact analysis solves the **same** problem twice — same data, estimators, objective and non-ESG constraints — once without and once with the ESG settings, and reports:

- change in expected return, volatility and Sharpe ratio (for a maximum-Sharpe objective the Sharpe change is $\le 0$ by construction: a constraint cannot improve the objective);
- change in ESG score;
- **ex-ante tracking error** between the two portfolios, $\sqrt{(w_{ESG}-w_{base})^\top\Sigma(w_{ESG}-w_{base})}$;
- **realised (in-sample) tracking error** of the two constant-mix portfolios over the estimation window;
- composition and sector changes;
- the **ESG-efficient frontier**: the maximum Sharpe ratio attainable at each minimum ESG level, which makes the trade-off curve explicit (Pedersen, Fitzgibbons & Pomorski, 2021).

## Interpreting the results

The measured cost is an *estimate* under the model's inputs. Because expected returns are imprecise, a small estimated Sharpe cost is not evidence that ESG constraints are free, and a large one is not proof that they are costly. The tracking-error figures are the most robust output: they measure how different the ESG portfolio is from the baseline, using only the covariance matrix.
