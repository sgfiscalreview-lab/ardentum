import "katex/dist/katex.min.css";

import type { Metadata } from "next";

import { Cite, Eq, M, Paper, PaperTable, Section, Sub } from "@/components/paper";
import { FrontierPairChart, PromiseChart, PromiseScatterChart } from "@/components/study-charts";
import { num } from "@/lib/format";
import type { RefKey } from "@/lib/study-references";
import { getStudy, monthYear, PROMISE_SETTINGS, promisedVersusRealised, promiseRecords, runMetadata, settingLabel } from "@/lib/studies";

const META = getStudy("promised-versus-realised");

export const metadata: Metadata = { title: META.short, description: META.summary };

/** Every work cited below; a unit test checks each citation is listed here. */
const REFS: RefKey[] = [
  "markowitz1952",
  "michaud1989",
  "jobsonKorkie1980",
  "bestGrauer1991",
  "chopraZiemba1993",
  "kanZhou2007",
  "jorion1986",
  "ledoitWolf2004",
  "demiguel2009",
  "charnesCooper1962",
  "lo2002",
  "jobsonKorkie1981",
  "memmel2003",
  "ledoitWolf2008",
  "frenchData",
];

const p = (x: number) => num(x, 2);

export default function PromisedVersusRealisedPage() {
  const r = promisedVersusRealised();
  const records = promiseRecords();
  const meta = runMetadata();
  const end = monthYear(meta.industries_sample[1]);
  const s60 = r[PROMISE_SETTINGS[0]]!;
  const k60 = r[PROMISE_SETTINGS[1]]!;
  const s120 = r[PROMISE_SETTINGS[2]]!;
  const k120 = r[PROMISE_SETTINGS[3]]!;
  const il = r.illustration;
  const years = records.filter((x) => x.lookback === 120);
  const first = Math.min(...years.map((x) => x.year_end));
  const last = Math.max(...years.map((x) => x.year_end));

  return (
    <Paper
      meta={META}
      dataThrough={end}
      refs={REFS}
      abstract={
        <p>
          A mean-variance optimiser reports the Sharpe ratio its portfolio is expected to earn, computed from the same estimates it optimised. We measure how much of that
          promise is kept. At every year end from {first} to {last}, using only the preceding 60 or 120 months of returns on 12 US industry portfolios, we form the
          maximum-Sharpe portfolio, record the Sharpe ratio it promises and measure what the same weights earn over the following 12 months. With sample estimates and a
          120-month window, the average promise is {p(s120.mean_promised_sharpe)} and the Sharpe ratio delivered out of sample is {p(s120.delivered_sharpe)}, less than
          half; with a 60-month window the gap is wider still. Shrinkage estimators of the means and covariances reduce the gap in both windows but do not close it, and in no
          setting does the optimised portfolio outperform simple equal weighting over the same months. The size of a year&apos;s promise is essentially unrelated to the
          following year&apos;s outcome.
        </p>
      }
    >
      <Section n="1" title="Introduction">
        <p>
          An investor who optimises a portfolio with mean-variance analysis <Cite k="markowitz1952" p /> receives two things: a set of weights, and a forecast of the
          portfolio&apos;s expected return, risk and Sharpe ratio. The forecast is computed from the same estimated inputs that chose the weights, and it is biased upwards.
          The optimiser favours the assets whose expected returns are most overestimated and whose risks are most underestimated, so the portfolio it reports as best is,
          on average, the one whose estimates are most flattering. <Cite k="michaud1989" /> called this the Markowitz optimisation enigma; <Cite k="jobsonKorkie1980" />{" "}
          documented the sampling error of estimated efficient portfolios; and <Cite k="kanZhou2007" /> quantify the loss from using estimated parameters as if they were
          true.
        </p>
        <p>
          Much of this literature is theoretical or uses simulated returns. This note measures the gap directly on real data over more than half a century, in the form an
          investor sees it: the Sharpe ratio the optimiser promises against the Sharpe ratio its portfolio then delivers. We also ask how much of the gap shrinkage estimators
          close, and how the delivered performance compares with equal weighting, the benchmark of <Cite k="demiguel2009" />.
        </p>
      </Section>

      <Section n="2" title="Data">
        <p>
          We use monthly value-weighted returns on the 12 US industry portfolios of the Kenneth R. French Data Library and the one-month Treasury bill rate from the same
          library <Cite k="frenchData" p />, from July 1926 to {end}. Portfolios are formed at each December from {first} to {last}; the last formation date is the latest
          December followed by a complete year of returns.
        </p>
      </Section>

      <Section n="3" title="Methodology">
        <Sub n="3.1" title="The promise">
          <p>
            At each formation date we estimate the annualised mean vector <M tex="\hat\mu" /> and covariance matrix <M tex="\hat\Sigma" /> from the previous <M tex="M" />{" "}
            months, with <M tex="M" /> equal to 60 or 120, and solve
          </p>
          <Eq tex="\hat w = \arg\max_{w}\ \frac{w^\top\hat\mu - r_f}{\sqrt{w^\top\hat\Sigma\,w}} \quad\text{subject to}\quad \textstyle\sum_i w_i = 1,\ \ 0 \le w_i \le 1," label="1" />
          <p>
            exactly, through the transformation of <Cite k="charnesCooper1962" />, where <M tex="r_f" /> is the average Treasury bill rate over the window. The value of the
            objective at <M tex="\hat w" /> is the promised Sharpe ratio. We use two sets of estimates: the sample mean and covariance, and shrinkage estimates that combine
            Bayes-Stein means <Cite k="jorion1986" p /> with the Ledoit-Wolf covariance matrix <Cite k="ledoitWolf2004" p />. When no long-only portfolio has an expected
            return above <M tex="r_f" />, no maximum-Sharpe portfolio exists and the year is skipped; this happened {k60.skipped_no_portfolio_beats_tbill} times with
            shrinkage and a 60-month window, {k120.skipped_no_portfolio_beats_tbill} with shrinkage and a 120-month window, and never with sample estimates.
          </p>
        </Sub>

        <Sub n="3.2" title="What is delivered">
          <p>
            The weights <M tex="\hat w" /> are then held, rebalanced monthly to their targets and without trading costs, over the next 12 months. Pooling the excess returns of
            all these out-of-sample months gives the delivered Sharpe ratio. Its standard error, for independent returns, is <Cite k="lo2002" p />
          </p>
          <Eq tex="\operatorname{SE}(\widehat{SR}) = \sqrt{12}\,\sqrt{\frac{1 + \tfrac12\,\widehat{sr}^{\,2}}{T}}," label="2" />
          <p>
            where <M tex="\widehat{sr}" /> is the monthly Sharpe ratio and <M tex="T" /> the number of months. We pool rather than average the 12-month Sharpe ratios,
            because averaging noisy short-period ratios overstates performance and gives calm years undue weight. We compare the delivered performance with an equally
            weighted portfolio over exactly the same months, using the test of <Cite k="jobsonKorkie1981" /> with the correction of <Cite k="memmel2003" />{" "}
            and the robust test of <Cite k="ledoitWolf2008" />.
          </p>
        </Sub>
      </Section>

      <Section n="4" title="Results">
        <Sub n="4.1" title="Promised against delivered">
          <p>
            Table 1 and Figure 1 report the results. In every setting the promise exceeds what is delivered, by a wide margin. With sample estimates the optimiser promises an
            average Sharpe ratio of {p(s60.mean_promised_sharpe)} with a 60-month window and {p(s120.mean_promised_sharpe)} with a 120-month window, and delivers{" "}
            {p(s60.delivered_sharpe)} and {p(s120.delivered_sharpe)}. The gap amounts to {num(s60.gap_in_standard_errors, 1)} and {num(s120.gap_in_standard_errors, 1)}{" "}
            standard errors of the delivered ratio; this treats the average promise as fixed, so it is a rough scale rather than a formal test. A longer window narrows the
            gap, because estimates from more data contain less noise for the optimiser to exploit.
          </p>
          <PaperTable
            n={1}
            caption={`Maximum-Sharpe portfolios formed each December, ${first} to ${last}: promised and delivered Sharpe ratios.`}
            head={["Setting", "Portfolios", "Average promise", "Delivered", "Standard error", "Gap", "Gap in standard errors", "1/N, same months", "p (JKM)", "p (robust)"]}
            rows={PROMISE_SETTINGS.map((k) => {
              const v = r[k]!;
              return [
                settingLabel(k),
                String(v.portfolios),
                p(v.mean_promised_sharpe),
                p(v.delivered_sharpe),
                p(v.delivered_sharpe_standard_error),
                p(v.promise_minus_delivered),
                num(v.gap_in_standard_errors, 1),
                p(v.equal_weight_sharpe_same_months),
                p(v.p_value_delivered_vs_equal_weight),
                p(v.p_value_delivered_vs_equal_weight_robust),
              ];
            })}
            note="Sharpe ratios are annualised. The delivered ratio pools every out-of-sample month; its standard error follows equation 2. The p-values test the delivered ratio against equal weights over the same months."
          />
          <PromiseChart
            title="Figure 1. The optimiser's average promise, what was delivered, and equal weights"
            note={`Portfolios formed each December, ${first} to ${last}. Whiskers show the 95% interval of the delivered Sharpe ratio.`}
            rows={PROMISE_SETTINGS.map((k) => {
              const v = r[k]!;
              const [low, high] = v.delivered_sharpe_interval_95;
              return { label: settingLabel(k), promised: v.mean_promised_sharpe, delivered: v.delivered_sharpe, low, high, equal: v.equal_weight_sharpe_same_months };
            })}
          />
        </Sub>

        <Sub n="4.2" title="Shrinkage helps, but does not close the gap">
          <p>
            Shrinkage estimators temper the promise most: with a 120-month window the average promise falls from {p(s120.mean_promised_sharpe)} to{" "}
            {p(k120.mean_promised_sharpe)} and the gap from {p(s120.promise_minus_delivered)} to {p(k120.promise_minus_delivered)}; with a 60-month window the gap falls from{" "}
            {p(s60.promise_minus_delivered)} to {p(k60.promise_minus_delivered)}. The promises become more honest, but the delivered Sharpe ratio changes little, from{" "}
            {p(s120.delivered_sharpe)} to {p(k120.delivered_sharpe)} with the longer window. In every setting the delivered ratio is below that of equal weights over the same
            months, though never significantly so at the 5% level.
          </p>
        </Sub>

        <Sub n="4.3" title="A year's promise says little about the next year">
          <p>
            Figure 2 plots each year&apos;s promise against the Sharpe ratio earned over the following 12 months. If promises were informative, the points would lie along an
            upward slope; instead they form a cloud. The correlation between the promise and the next year&apos;s outcome is {p(s120.corr_promised_vs_next_12_months)} with
            sample estimates and {p(k120.corr_promised_vs_next_12_months)} with shrinkage for the 120-month window, and {p(s60.corr_promised_vs_next_12_months)} and{" "}
            {p(k60.corr_promised_vs_next_12_months)} for the 60-month window. An unusually high promise is no reason to expect an unusually good year.
          </p>
          <PromiseScatterChart
            title="Figure 2. Each year's promised Sharpe ratio and the next 12 months"
            note="120-month window. Points on the dashed line kept their promise exactly; points below it fell short."
            groups={["Sample estimates", "Shrinkage (Bayes-Stein + Ledoit-Wolf)"].map((est) => ({
              name: est === "Sample estimates" ? "Sample estimates" : "Shrinkage estimates",
              points: years.filter((x) => x.estimator === est).map((x) => ({ year: x.year_end, promised: x.promised, realised: x.realised_next_12_months })),
            }))}
          />
        </Sub>

        <Sub n="4.4" title="An illustration: the frontier that was promised">
          <p>
            Figure 3 shows the same effect for a whole efficient frontier. Estimated from sample statistics over {il.estimated_on[0]!.slice(0, 4)} to{" "}
            {il.estimated_on[1]!.slice(0, 4)}, the frontier promised a combination of risk and return that no portfolio on it achieved over{" "}
            {il.realised_on[0]!.slice(0, 4)} to {il.realised_on[1]!.slice(0, 4)}: every one of its {il.promised.length} portfolios turned out both riskier and less
            rewarding than promised. The second period contains the 2008 crisis, which makes the illustration vivid; the systematic evidence is in Table 1.
          </p>
          <FrontierPairChart
            title={`Figure 3. The efficient frontier estimated on ${il.estimated_on[0]!.slice(0, 4)} to ${il.estimated_on[1]!.slice(0, 4)}, and what its portfolios did next`}
            note={`Sample estimates, long-only portfolios. Each point on the second line is the same portfolio as the corresponding point on the first, measured over ${il.realised_on[0]!.slice(0, 4)} to ${il.realised_on[1]!.slice(0, 4)}.`}
            curves={[
              { name: `Promised (${il.estimated_on[0]!.slice(0, 4)} to ${il.estimated_on[1]!.slice(0, 4)} estimates)`, points: il.promised },
              { name: `Realised (${il.realised_on[0]!.slice(0, 4)} to ${il.realised_on[1]!.slice(0, 4)})`, points: il.realised },
            ]}
          />
        </Sub>
      </Section>

      <Section n="5" title="Discussion">
        <p>
          The results put a number on a familiar warning. The Sharpe ratio an optimiser reports is not a forecast but the most flattering reading of noisy estimates, with
          sample estimates on this data it has overstated what was delivered by a factor of two or more. Errors in expected returns drive the effect, as{" "}
          <Cite k="bestGrauer1991" /> and <Cite k="chopraZiemba1993" /> show, which is why longer windows and shrinkage, both of which reduce the noise in the estimated means, narrow the gap. That the
          delivered performance never beats equal weighting is consistent with <Cite k="demiguel2009" />: removing estimation error from the promise does not create
          information that was not in the data.
        </p>
        <p>
          The practical lesson concerns how results are reported. An optimiser&apos;s promised Sharpe ratio should be read alongside an estimate of its uncertainty and,
          where possible, an out-of-sample test. Ardentum reports a confidence interval for every Sharpe ratio and lets any optimised portfolio be tested walk-forward against
          equal weights for this reason.
        </p>
      </Section>

      <Section n="6" title="Limitations">
        <p>
          The universe is 12 industry portfolios, the portfolios are long only and held for a year without trading costs, and portfolios are formed annually, so the
          observations are few and the standard errors wide. The standard error of equation 2 assumes independent returns, and the gap measured in standard errors treats the
          promise as known. The results concern maximum-Sharpe portfolios only; minimum-variance portfolios, which do not use estimated means, are outside the scope of this
          note. The results describe US data over one historical period.
        </p>
      </Section>

      <Section n="7" title="Conclusion">
        <p>
          Over more than five decades of US industry returns, maximum-Sharpe portfolios built from sample estimates delivered less than half of the
          Sharpe ratio they promised. Shrinkage estimators make
          the promise more realistic but do not improve the outcome enough to beat equal weighting. An optimiser&apos;s promise is best treated as an upper bound, and its
          portfolio judged only on data it has not seen.
        </p>
      </Section>
    </Paper>
  );
}
