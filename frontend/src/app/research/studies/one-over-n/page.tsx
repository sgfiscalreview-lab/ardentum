import "katex/dist/katex.min.css";

import type { Metadata } from "next";

import { Cite, Eq, M, Paper, PaperTable, Section, Sub } from "@/components/paper";
import { GrowthChart, PairedBarChart } from "@/components/study-charts";
import { num, pct, signedNum } from "@/lib/typeset";
import type { RefKey } from "@/lib/study-references";
import { getStudy, monthYear, oneOverN, oneOverNGrowth, runMetadata } from "@/lib/studies";

const META = getStudy("one-over-n");

export const metadata: Metadata = { title: META.short, description: META.summary };

/** Every work cited below; a unit test checks each citation is listed here. */
const REFS: RefKey[] = [
  "markowitz1952",
  "demiguel2009",
  "michaud1989",
  "bestGrauer1991",
  "chopraZiemba1993",
  "jagannathanMa2003",
  "kirbyOstdiek2012",
  "tuZhou2011",
  "ledoitWolf2004",
  "jorion1986",
  "charnesCooper1962",
  "rockafellarUryasev2000",
  "sharpe1966",
  "jobsonKorkie1981",
  "memmel2003",
  "ledoitWolf2008",
  "neweyWest1994",
  "frenchData",
];

const ONE_N = "1/N (equal weight)";
const STRATEGIES = [
  ONE_N,
  "Minimum variance (sample)",
  "Minimum variance (shrinkage)",
  "Maximum Sharpe (sample)",
  "Maximum Sharpe (shrinkage)",
  "Minimum CVaR 90% (tail risk)",
];
const SETTINGS = ["window 60m, costs 0bp", "window 60m, costs 50bp", "window 120m, costs 0bp", "window 120m, costs 50bp"];
const MAIN = "window 120m, costs 50bp";

function settingName(s: string): string {
  const [, w, c] = /window (\d+)m, costs (\d+)bp/.exec(s) ?? [];
  return `${w}-month window, ${c === "0" ? "no costs" : `${c} bp costs`}`;
}

const p = (x: number) => num(x, 2);
const monthCount = (k: number) => (k === 0 ? "no months" : k === 1 ? "one month" : `${k} months`);

export default function OneOverNPage() {
  const r = oneOverN();
  const growth = oneOverNGrowth();
  const meta = runMetadata();
  const main = r[MAIN]!;
  const base = main[ONE_N]!;
  const months = base.full.months;
  const end = monthYear(growth.dates[growth.dates.length - 1] ?? meta.industries_sample[1]);
  const optimised = STRATEGIES.slice(1);
  const minP = Math.min(...SETTINGS.flatMap((s) => optimised.flatMap((n) => [r[s]![n]!.full.p_value_vs_1n, r[s]![n]!.full.p_value_vs_1n_robust])));
  const mv = main["Minimum variance (shrinkage)"]!;
  const ms = main["Maximum Sharpe (sample)"]!;
  const mss = main["Maximum Sharpe (shrinkage)"]!;
  const free = r["window 120m, costs 0bp"]!;
  const maxGap = Math.max(...SETTINGS.flatMap((s) => optimised.map((n) => Math.abs(r[s]![n]!.full.sharpe_minus_1n))));

  return (
    <Paper
      meta={META}
      dataThrough={end}
      refs={REFS}
      abstract={
        <p>
          We revisit the finding of <Cite k="demiguel2009" /> that no optimised portfolio reliably outperforms the equally weighted (1/N) portfolio out of sample. Using
          monthly returns on 12 value-weighted US industry portfolios, we evaluate five optimised strategies against 1/N in walk-forward backtests over {months} months, from
          January 1970 to {end}, with estimation windows of 60 and 120 months and proportional trading costs of 0 and 50 basis points. No optimised strategy has a Sharpe
          ratio significantly different from that of 1/N at the 5% level in any of the four specifications, under either the Jobson-Korkie test with Memmel&apos;s correction
          or a heteroskedasticity- and autocorrelation-robust test; the smallest p-value is {p(minP)}. Minimum-variance portfolios earn modestly higher Sharpe ratios than
          1/N and suffer markedly smaller drawdowns, while maximum-Sharpe portfolios trail 1/N before 2005 and, in the main specification, roughly match it afterwards. The
          original result has survived two further decades of data.
        </p>
      }
    >
      <Section n="1" title="Introduction">
        <p>
          Mean-variance analysis <Cite k="markowitz1952" p /> gives the portfolio with the best trade-off between expected return and risk, provided the expected returns
          and covariances are known. In practice they must be estimated, and the optimal weights are highly sensitive to errors in the estimated means{" "}
          <Cite k="bestGrauer1991" p />. <Cite k="chopraZiemba1993" /> show that errors in means matter roughly an order of magnitude more than errors in variances, and{" "}
          <Cite k="michaud1989" /> calls mean-variance optimisers &quot;estimation-error maximizers&quot;, because they concentrate in the assets whose estimated returns
          are most overstated.
        </p>
        <p>
          <Cite k="demiguel2009" /> put the problem in its starkest form. Across seven empirical datasets, none of fourteen optimising models delivered a Sharpe ratio, a
          certainty-equivalent return or a turnover consistently better than simply holding every asset in equal proportion. Their analysis implies that, with realistic
          numbers of assets, the estimation window needed for mean-variance optimisation to beat 1/N runs to centuries of monthly data. The finding prompted a large
          literature: <Cite k="kirbyOstdiek2012" /> show that strategies which time volatility, rather than estimate means, can beat 1/N after costs, and{" "}
          <Cite k="tuZhou2011" /> show that combining a sophisticated rule with 1/N can improve on both.
        </p>
        <p>
          The original samples end in the early 2000s. This note asks whether the result still holds after them. It makes four contributions: it extends the evaluation to{" "}
          {end}; it splits the sample in January 2005 to compare the original period with the two decades since; it reports a test of Sharpe-ratio differences that
          remains valid under fat tails and autocorrelation <Cite k="ledoitWolf2008" p />, alongside the test the original study used; and it publishes code that reruns
          every number on the latest data.
        </p>
      </Section>

      <Section n="2" title="Data">
        <p>
          We use monthly value-weighted returns on the 12 US industry portfolios of the Kenneth R. French Data Library <Cite k="frenchData" p />, available from July 1926,
          and the one-month Treasury bill rate from the same library&apos;s Fama-French factor file, used as the risk-free rate. Industry portfolios are a standard test
          universe in this literature: they are well diversified, cover the whole US market and have no survivorship bias. All returns are total returns in US dollars.
          The evaluation period starts in January 1970 so that the longest estimation window is fully populated, and runs to {end}, giving {months} monthly out-of-sample
          returns for every strategy.
        </p>
      </Section>

      <Section n="3" title="Methodology">
        <Sub n="3.1" title="Strategies">
          <p>
            All portfolios are long only and fully invested: each weight lies between 0 and 1 and the weights sum to one. We compare six strategies.
          </p>
          <ol>
            <li>
              <strong>1/N</strong> holds every industry in equal proportion and needs no estimation.
            </li>
            <li>
              <strong>Minimum variance (sample)</strong> minimises portfolio variance using the sample covariance matrix.
            </li>
            <li>
              <strong>Minimum variance (shrinkage)</strong> does the same with the Ledoit-Wolf estimator, which shrinks the sample covariance matrix towards a scaled identity{" "}
              <Cite k="ledoitWolf2004" p />.
            </li>
            <li>
              <strong>Maximum Sharpe (sample)</strong> maximises the ratio of expected excess return to volatility using sample means and covariances, with the risk-free
              rate set to the average Treasury bill rate over the estimation window. The ratio is maximised exactly through the transformation of{" "}
              <Cite k="charnesCooper1962" />.
            </li>
            <li>
              <strong>Maximum Sharpe (shrinkage)</strong> uses Bayes-Stein means <Cite k="jorion1986" p /> and the Ledoit-Wolf covariance matrix.
            </li>
            <li>
              <strong>Minimum CVaR</strong> minimises the conditional value at risk at the 90% level over the historical scenarios in the window, using the linear
              programme of <Cite k="rockafellarUryasev2000" />.
            </li>
          </ol>
          <p>
            When no long-only portfolio has an expected return above the risk-free rate, the maximum-Sharpe problem has no solution; the strategy then holds the
            minimum-variance portfolio for that month. In the main specification this fallback was used in {monthCount(ms.tangency_fallbacks)} for the sample version and{" "}
            {monthCount(mss.tangency_fallbacks)} for the shrinkage version.
          </p>
        </Sub>

        <Sub n="3.2" title="Walk-forward design">
          <p>
            At the end of every month <M tex="t" /> each strategy estimates its inputs from the <M tex="M" /> months ending at <M tex="t" />, with <M tex="M" /> equal to 60
            or 120, and holds the resulting weights over month <M tex="t+1" />. Portfolios are rebalanced monthly. Proportional trading costs of <M tex="c" /> are charged
            on turnover, so the return over month <M tex="t+1" /> net of costs is
          </p>
          <Eq tex="r^{\text{net}}_{t+1} = (1 - c\,\tau_t)\,(1 + w_t^\top R_{t+1}) - 1, \qquad \tau_t = \textstyle\sum_i \lvert w_{i,t} - w_{i,t}^{-} \rvert," label="1" />
          <p>
            where <M tex="w_t^{-}" /> are the weights drifted by the previous month&apos;s returns and <M tex="c" /> is 0 or 50 basis points. No information after month{" "}
            <M tex="t" /> enters the weights chosen at <M tex="t" />. A unit test of the backtesting engine checks this by altering the returns after a cut-off date and
            confirming that no weight chosen up to that date changes.
          </p>
        </Sub>

        <Sub n="3.3" title="Performance measures">
          <p>
            Let <M tex="e_t" /> be a strategy&apos;s monthly return in excess of the Treasury bill, with sample mean <M tex="\hat\mu" /> and standard deviation{" "}
            <M tex="\hat\sigma" />. We report the annualised Sharpe ratio <Cite k="sharpe1966" p /> and, as in <Cite k="demiguel2009" />, the certainty-equivalent excess
            return of an investor with mean-variance utility and risk aversion <M tex="\gamma = 1" />:
          </p>
          <Eq tex="\widehat{SR} = \sqrt{12}\,\frac{\hat\mu}{\hat\sigma}, \qquad \widehat{CE} = 12\left(\hat\mu - \frac{\gamma}{2}\,\hat\sigma^{2}\right)." label="2" />
          <p>We also report the maximum drawdown, the largest fall from a previous peak in value, and the average annual turnover.</p>
        </Sub>

        <Sub n="3.4" title="Statistical inference">
          <p>
            To test whether a strategy&apos;s Sharpe ratio differs from that of 1/N, we use the test of <Cite k="jobsonKorkie1981" /> with the correction of{" "}
            <Cite k="memmel2003" />, the test reported by <Cite k="demiguel2009" />. For strategies <M tex="a" /> and <M tex="b" /> over <M tex="T" /> months,
          </p>
          <Eq
            tex="z = \frac{\hat\sigma_b\hat\mu_a - \hat\sigma_a\hat\mu_b}{\sqrt{\hat\theta}}, \quad \hat\theta = \frac{1}{T}\left(2\hat\sigma_a^2\hat\sigma_b^2 - 2\hat\sigma_a\hat\sigma_b\hat\sigma_{ab} + \tfrac12\hat\mu_a^2\hat\sigma_b^2 + \tfrac12\hat\mu_b^2\hat\sigma_a^2 - \frac{\hat\mu_a\hat\mu_b}{\hat\sigma_a\hat\sigma_b}\hat\sigma_{ab}^2\right),"
            label="3"
          />
          <p>
            which is asymptotically standard normal under the null of equal Sharpe ratios. Because this test assumes independent, normally distributed returns, we also
            report the robust test of <Cite k="ledoitWolf2008" />, section 3.1: the difference in Sharpe ratios is written as a function of the first and second moments of
            the two return series, and its standard error is obtained by the delta method from a heteroskedasticity- and autocorrelation-consistent estimate of their
            long-run covariance, with a Bartlett kernel and the lag length of <Cite k="neweyWest1994" />. Both tests are two-sided.
          </p>
        </Sub>
      </Section>

      <Section n="4" title="Results">
        <Sub n="4.1" title="Main specification">
          <p>
            Table 1 reports the full-sample results for the main specification, a 120-month estimation window with 50 basis points of trading costs. The equally weighted
            portfolio earns a Sharpe ratio of {p(base.full.sharpe)}. The minimum-variance portfolios do somewhat better, at {p(main["Minimum variance (sample)"]!.full.sharpe)}{" "}
            and {p(mv.full.sharpe)}, but the difference from 1/N is not statistically significant (robust p-values of{" "}
            {p(main["Minimum variance (sample)"]!.full.p_value_vs_1n_robust)} and {p(mv.full.p_value_vs_1n_robust)}). The maximum-Sharpe portfolios do worse, at{" "}
            {p(ms.full.sharpe)} and {p(mss.full.sharpe)}, again without statistical significance. Much of their shortfall is the cost of trading. Their annual turnover is{" "}
            {num(ms.annual_turnover, 2)} and {num(mss.annual_turnover, 2)} times portfolio value, against {num(base.annual_turnover, 2)} for 1/N, and without trading costs
            their gap to 1/N narrows from {signedNum(ms.full.sharpe_minus_1n, 2)} to {signedNum(free["Maximum Sharpe (sample)"]!.full.sharpe_minus_1n, 2)} (sample) and from{" "}
            {signedNum(mss.full.sharpe_minus_1n, 2)} to {signedNum(free["Maximum Sharpe (shrinkage)"]!.full.sharpe_minus_1n, 2)} (shrinkage).
          </p>
          <PaperTable
            n={1}
            caption={`Out-of-sample performance, January 1970 to ${end}: 120-month window, 50 basis points of trading costs.`}
            head={["Strategy", "Excess return", "Volatility", "Sharpe ratio", "Versus 1/N", "p (JKM)", "p (robust)", "CE", "Max drawdown", "Turnover"]}
            rows={STRATEGIES.map((n) => {
              const s = main[n]!;
              const f = s.full;
              const isBase = n === ONE_N;
              return [
                n,
                pct(f.mean_excess_annual, 1),
                pct(f.volatility_annual, 1),
                p(f.sharpe),
                isBase ? "" : signedNum(f.sharpe_minus_1n, 2),
                isBase ? "" : p(f.p_value_vs_1n),
                isBase ? "" : p(f.p_value_vs_1n_robust),
                pct(f.certainty_equivalent, 1),
                pct(f.max_drawdown, 1),
                num(s.annual_turnover, 2),
              ];
            })}
            note={
              <>
                Excess return and volatility are annualised; versus 1/N is the difference in Sharpe ratio; CE is the certainty-equivalent excess return with risk aversion of 1 (equation 2); turnover is the sum of
                absolute changes in portfolio weights at rebalancing (purchases plus sales) per year, as a multiple of portfolio value. p (JKM) is the two-sided p-value of the Jobson-Korkie test with Memmel&apos;s correction; p (robust)
                is that of the HAC test after Ledoit and Wolf (2008). Returns are net of costs.
              </>
            }
          />
          <GrowthChart
            title={`Figure 1. Growth of $1 invested in January 1970, ${settingName(MAIN)}`}
            note="Logarithmic scale; returns net of trading costs."
            dates={growth.dates}
            series={STRATEGIES.map((n) => ({ name: n, values: growth.wealth[n] ?? [] }))}
          />
          <p>
            The clearest difference between the strategies is in risk rather than reward. The minimum-variance portfolios&apos; deepest losses were{" "}
            {pct(-main["Minimum variance (sample)"]!.full.max_drawdown, 1)} and {pct(-mv.full.max_drawdown, 1)}, against {pct(-base.full.max_drawdown, 1)} for 1/N. By construction they
            hold more of the least volatile industries, and that protection shows most when markets fall.
          </p>
        </Sub>

        <Sub n="4.2" title="The original period and the two decades since">
          <p>
            Figure 2 and Table 2 split the evaluation at January 2005. Before 2005 the maximum-Sharpe portfolios trail 1/N by{" "}
            {p(Math.abs(ms["1970-2004"].sharpe_minus_1n))} and {p(Math.abs(mss["1970-2004"].sharpe_minus_1n))} in Sharpe ratio, as the original study found. Since 2005 the
            gap has all but closed, at {signedNum(ms["2005-latest"].sharpe_minus_1n, 2)} and {signedNum(mss["2005-latest"].sharpe_minus_1n, 2)}, while the minimum-variance portfolios keep a
            small, insignificant lead. No difference in either period is significant at the 5% level.
          </p>
          <PairedBarChart
            title="Figure 2. Sharpe ratio minus that of 1/N, before and after 2005"
            note={`${settingName(MAIN)}. Above zero, the strategy beat equal weights.`}
            rows={optimised.map((n) => ({ label: n, a: main[n]!["1970-2004"].sharpe_minus_1n, b: main[n]!["2005-latest"].sharpe_minus_1n }))}
            names={["1970 to 2004", `2005 to ${end}`]}
            kind="signedRatio"
            axisLabel="Difference in annualised Sharpe ratio"
          />
          <PaperTable
            n={2}
            caption={`Sharpe ratios by subperiod: 120-month window, 50 basis points of trading costs.`}
            head={["Strategy", "1970 to 2004", "p (robust)", `2005 to ${end}`, "p (robust)"]}
            rows={STRATEGIES.map((n) => {
              const s = main[n]!;
              const isBase = n === ONE_N;
              return [n, p(s["1970-2004"].sharpe), isBase ? "" : p(s["1970-2004"].p_value_vs_1n_robust), p(s["2005-latest"].sharpe), isBase ? "" : p(s["2005-latest"].p_value_vs_1n_robust)];
            })}
            note="p (robust) tests the difference from 1/N over the same subperiod."
          />
        </Sub>

        <Sub n="4.3" title="Robustness">
          <p>
            Table 3 repeats the comparison for all four combinations of estimation window and trading cost. The pattern is the same throughout: minimum variance is ahead of
            1/N in every specification, maximum Sharpe is behind it in every specification once costs are charged, and none of the {optimised.length * SETTINGS.length}{" "}
            comparisons is significant at the 5% level. Trading costs matter most for the high-turnover maximum-Sharpe strategies, and a longer window reduces turnover for
            all of them.
          </p>
          <PaperTable
            n={3}
            caption={`Difference in Sharpe ratio from 1/N, January 1970 to ${end}, with robust p-values in parentheses.`}
            head={["Strategy", ...SETTINGS.map(settingName)]}
            rows={optimised.map((n) => [n, ...SETTINGS.map((s) => `${signedNum(r[s]![n]!.full.sharpe_minus_1n, 2)} (${p(r[s]![n]!.full.p_value_vs_1n_robust)})`)])}
          />
        </Sub>

        <Sub n="4.4" title="Behaviour in crises">
          <p>
            Table 4 reports cumulative returns over three recent episodes of market stress. The minimum-variance portfolios lost substantially less than 1/N in the 2008
            financial crisis, while all strategies fell sharply in the 2020 Covid crash, when losses were broad and brief.
          </p>
          <PaperTable
            n={4}
            caption={`Cumulative return during crises: ${settingName(MAIN)}.`}
            head={["Strategy", ...Object.keys(base.crisis_returns)]}
            rows={STRATEGIES.map((n) => [n, ...Object.keys(base.crisis_returns).map((c) => pct(main[n]!.crisis_returns[c], 1))])}
            note="The 2008 financial crisis runs from November 2007 to March 2009, the Covid crash from February to March 2020, and the 2022 rate shock from January to September 2022."
          />
        </Sub>
      </Section>

      <Section n="5" title="Discussion">
        <p>
          The results confirm the central message of <Cite k="demiguel2009" />. The strategies that rely on estimated expected returns do not beat equal weights, and those
          that ignore expected returns and minimise risk do only slightly better. This ordering is what estimation error predicts: sample means are so noisy that a rule
          which uses them adds more error than information, while covariances can be estimated far more precisely. The long-only constraint itself acts as a form of
          shrinkage of the covariance matrix <Cite k="jagannathanMa2003" p />, which helps explain why the minimum-variance portfolios are well behaved even with sample
          estimates.
        </p>
        <p>
          The absence of statistical significance is itself informative. Over more than half a century of monthly data, differences in annualised Sharpe ratio of the size measured here, none larger than{" "}
          {p(maxGap)} in absolute value, cannot be told apart from chance; an investor who cannot distinguish two strategies statistically should prefer the one with fewer assumptions, lower turnover and lower
          cost, which is 1/N. The narrowing of the gap after 2005 is suggestive but should not be over-read, since the subperiod estimates are noisier still.
        </p>
      </Section>

      <Section n="6" title="Limitations">
        <p>
          The universe is 12 broad industry portfolios. With more assets, estimation error grows and the case for 1/N strengthens further, while with individual securities
          the results could differ in either direction. We consider only long-only portfolios, a flat proportional trading cost and monthly rebalancing; less frequent
          rebalancing would reduce costs for all strategies. The risk-free rate is the one-month Treasury bill. Finally, the results describe one market over one historical
          period and do not predict future performance.
        </p>
      </Section>

      <Section n="7" title="Conclusion">
        <p>
          More than two decades after the end of the original samples, the 1/N puzzle stands. On US industry portfolios from 1970 to {end}, no optimised strategy beats equal weights with statistical
          significance, after costs or before. Minimising risk is the only optimisation that is ahead of 1/N in every specification, and its clearest advantage
          is smaller losses in falling markets; estimating expected returns does not pay. For most investors, equal weighting remains a demanding benchmark for any optimised portfolio.
        </p>
      </Section>
    </Paper>
  );
}
