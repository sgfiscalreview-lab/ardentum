import "katex/dist/katex.min.css";

import type { Metadata } from "next";

import { Cite, Eq, M, Paper, PaperTable, Section, Sub } from "@/components/paper";
import { PairedBarChart, YearLinesChart } from "@/components/study-charts";
import { num, pct, signedPct } from "@/lib/typeset";
import type { RefKey } from "@/lib/study-references";
import { currencyHedging, getStudy, INDUSTRY, monthYear } from "@/lib/studies";

const META = getStudy("currency-hedging");

export const metadata: Metadata = { title: META.short, description: META.summary };

/** Every work cited below; a unit test checks each citation is listed here. */
const REFS: RefKey[] = [
  "perold1988",
  "black1989",
  "glenJorion1993",
  "froot1993",
  "campbell2010",
  "ederington1979",
  "du2018",
  "frenchData",
  "ecbRates",
  "bisRates",
];

const INVESTORS = ["euro", "sterling"] as const;
const MARKET = "US market";

export default function CurrencyHedgingPage() {
  const h = currencyHedging();
  const eu = h.euro;
  const gb = h.sterling;
  const assets = Object.keys(eu.assets);
  const start = monthYear(eu.sample[0]);
  const end = monthYear(eu.sample[1]);
  const months = eu.assets[MARKET]!.months;
  const m = { euro: eu.assets[MARKET]!, sterling: gb.assets[MARKET]! };
  const lower = (inv: (typeof INVESTORS)[number]) => Object.values(h[inv].assets).filter((a) => a.risk_change_from_hedging < 0).length;
  const crises = Object.keys(eu.crises_us_market);
  const years = Object.keys(eu.rolling_5y_hedge_ratio_us_market);
  const dotcom = crises[0]!; // the one episode before 2007, listed first
  const recent = crises.slice(1);
  const maxChange = Math.max(...INVESTORS.flatMap((inv) => Object.values(h[inv].assets).map((a) => Math.abs(a.risk_change_from_hedging))));
  const negativeYears = years.filter((y) => (eu.rolling_5y_hedge_ratio_us_market[y] ?? 0) < 0 && (gb.rolling_5y_hedge_ratio_us_market[y] ?? 0) < 0);

  return (
    <Paper
      meta={META}
      dataThrough={end}
      refs={REFS}
      abstract={
        <p>
          A euro or sterling investor who buys US shares takes on two risks: the shares and the dollar. Hedging the dollar removes the second, and textbook advice holds that
          it therefore reduces risk. We measure the effect for investments in the US market and 12 US industry portfolios over {months} months, from {start} to {end}, with a
          one-month forward hedge priced by covered interest parity from central-bank policy rates. Full hedging changes the volatility of the US market by{" "}
          {signedPct(m.euro.risk_change_from_hedging, 1)} for a euro investor and {signedPct(m.sterling.risk_change_from_hedging, 1)} for a sterling investor, because the
          dollar tends to rise when US shares fall: the correlation between the two is negative for every portfolio and both investors. This protection was not dependable in
          crises. In the three crises since 2007 the dollar appreciated and the unhedged investor lost less than the hedged one, but in the 2000 to 2002 bear market the dollar
          fell and hedging reduced the loss. The risk-minimising hedge ratio for the US market is {num(m.euro.min_variance_hedge_ratio, 2)}{" "}
          for the euro investor and {num(m.sterling.min_variance_hedge_ratio, 2)} for the sterling investor, and it has varied widely over time, turning negative in recent
          years.
        </p>
      }
    >
      <Section n="1" title="Introduction">
        <p>
          International equity investors face a basic policy question: should the currency exposure that comes with foreign shares be hedged? An influential answer is that
          hedging is a free lunch: it removes currency volatility without lowering expected return, so a risk-averse investor should hedge fully <Cite k="perold1988" p />.{" "}
          <Cite k="black1989" /> argues instead for a universal hedge ratio below one, and <Cite k="glenJorion1993" /> find that the benefit of hedging depends on the
          portfolio it is added to. <Cite k="froot1993" /> shows that at long horizons hedging does little to reduce risk.
        </p>
        <p>
          The answer turns on how currencies move with equities. <Cite k="campbell2010" /> find that the US dollar, the euro and the Swiss franc tend to appreciate when world
          equity markets fall, so an investor who keeps exposure to these currencies holds a natural hedge, and the risk-minimising hedge ratio can be well below one.
          This note measures that effect directly for the investor most often given the hedging advice: a European saver holding US shares. We report the change in risk from
          full hedging, the risk-minimising hedge ratio, its stability over time and the behaviour of both choices in crises, for euro and sterling investors, over the
          full period of the euro.
        </p>
      </Section>

      <Section n="2" title="Data">
        <p>
          US equity returns are the monthly value-weighted returns on the US market (the market return of the Fama-French factor file) and the 12 US industry portfolios of
          the Kenneth R. French Data Library <Cite k="frenchData" p />, in dollars. Exchange rates are month-end euro reference rates published by the European Central Bank{" "}
          <Cite k="ecbRates" p />, from which the euro and sterling prices of a dollar follow. Interest rates are the central-bank policy rates of the euro area, the United
          Kingdom and the United States from the Bank for International Settlements <Cite k="bisRates" p />. The sample runs from {start}, the first month for which a monthly
          return in euro can be measured, to {end}.
        </p>
      </Section>

      <Section n="3" title="Methodology">
        <Sub n="3.1" title="Unhedged and hedged returns">
          <p>
            Let <M tex="r_t" /> be the dollar return of a US portfolio in month <M tex="t" /> and <M tex="x_t" /> the change in the investor&apos;s currency price of one
            dollar. The unhedged return in the investor&apos;s currency is
          </p>
          <Eq tex="r^{U}_t = (1 + r_t)(1 + x_t) - 1." label="1" />
          <p>
            The hedged investor sells the starting value of the position forward for one month. Under covered interest parity the forward locks in the difference between
            the investor&apos;s interest rate <M tex="i^{*}" /> and the dollar rate <M tex="i" />, both known at the start of the month, so that
          </p>
          <Eq tex="r^{H}_t = r_t\,(1 + x_t) + \frac{1 + i^{*}_{t-1}\,\delta_t}{1 + i_{t-1}\,\delta_t} - 1," label="2" />
          <p>
            where <M tex="\delta_t" /> is the length of the month in years. The hedge removes the currency return on the starting value; only the currency return on the
            month&apos;s gain or loss remains. This is the method Ardentum uses for its currency-hedged returns, with policy rates standing in for the interbank rates that
            price traded forwards.
          </p>
        </Sub>

        <Sub n="3.2" title="The risk-minimising hedge ratio">
          <p>
            An investor who hedges a fraction <M tex="h" /> of the position earns <M tex="r^{U}_t + h\,d_t" />, with <M tex="d_t = r^{H}_t - r^{U}_t" />. The variance of this
            return is smallest at
          </p>
          <Eq tex="h^{*} = -\frac{\operatorname{Cov}(r^{U}_t, d_t)}{\operatorname{Var}(d_t)}," label="3" />
          <p>
            the minimum-variance hedge ratio of <Cite k="ederington1979" />. A value of one means full hedging minimises risk; zero means no hedging; a negative value means
            the investor would lower risk by holding more dollars than the investment brings. We estimate <M tex="h^{*}" /> over the full sample and over rolling five-year
            windows ending each December, requiring at least 48 months.
          </p>
        </Sub>
      </Section>

      <Section n="4" title="Results">
        <Sub n="4.1" title="Hedging and volatility">
          <p>
            Table 1 gives the results for the US market. For a euro investor, full hedging leaves volatility essentially unchanged, at {pct(m.euro.volatility_unhedged, 1)}{" "}
            unhedged and {pct(m.euro.volatility_hedged, 1)} hedged. For a sterling investor it raises volatility from {pct(m.sterling.volatility_unhedged, 1)} to{" "}
            {pct(m.sterling.volatility_hedged, 1)}. The reason is the negative correlation between US shares and the dollar, {num(m.euro.corr_us_stocks_vs_dollar, 2)} against
            the euro and {num(m.sterling.corr_us_stocks_vs_dollar, 2)} against sterling: currency movements have tended to offset share price movements rather than add to them.
            Hedging also lowered the average return, from {pct(m.euro.mean_unhedged_annual, 1)} to {pct(m.euro.mean_hedged_annual, 1)} a year for the euro investor and from{" "}
            {pct(m.sterling.mean_unhedged_annual, 1)} to {pct(m.sterling.mean_hedged_annual, 1)} for the sterling investor, reflecting the interest-rate differential locked in by the
            forward and the dollar&apos;s net movement over the period.
          </p>
          <PaperTable
            n={1}
            caption={`The US market for euro and sterling investors, ${start} to ${end}.`}
            head={["", "Euro investor", "Sterling investor"]}
            rows={[
              ["Volatility, unhedged", pct(m.euro.volatility_unhedged, 1), pct(m.sterling.volatility_unhedged, 1)],
              ["Volatility, hedged", pct(m.euro.volatility_hedged, 1), pct(m.sterling.volatility_hedged, 1)],
              ["Change in volatility from hedging", signedPct(m.euro.risk_change_from_hedging, 1), signedPct(m.sterling.risk_change_from_hedging, 1)],
              ["Average return, unhedged", pct(m.euro.mean_unhedged_annual, 1), pct(m.sterling.mean_unhedged_annual, 1)],
              ["Average return, hedged", pct(m.euro.mean_hedged_annual, 1), pct(m.sterling.mean_hedged_annual, 1)],
              ["Correlation of US shares with the dollar", num(m.euro.corr_us_stocks_vs_dollar, 2), num(m.sterling.corr_us_stocks_vs_dollar, 2)],
              ["Risk-minimising hedge ratio", num(m.euro.min_variance_hedge_ratio, 2), num(m.sterling.min_variance_hedge_ratio, 2)],
              ["Maximum drawdown, unhedged", pct(m.euro.max_drawdown_unhedged, 1), pct(m.sterling.max_drawdown_unhedged, 1)],
              ["Maximum drawdown, hedged", pct(m.euro.max_drawdown_hedged, 1), pct(m.sterling.max_drawdown_hedged, 1)],
            ]}
            note="Volatility and average return are annualised, in the investor's currency. The correlation is between the dollar return of US shares and the change in the investor's price of a dollar."
          />
          <p>
            The same holds across industries (Figure 1 and Table 2). Hedging lowered volatility for {lower("euro")} of the {assets.length} portfolios for a euro investor and{" "}
            {lower("sterling")} for a sterling investor, and in no case did it change volatility by more than {pct(maxChange, 1)} in either direction. The correlation between US shares and the dollar is negative
            for all {assets.length} portfolios and both investors.
          </p>
          <PairedBarChart
            title="Figure 1. Change in volatility from full hedging, by portfolio"
            note={`${start} to ${end}. Below zero, hedging reduced risk; above zero, it increased it.`}
            rows={assets.map((a) => ({ label: INDUSTRY[a] ?? a, a: eu.assets[a]!.risk_change_from_hedging, b: gb.assets[a]!.risk_change_from_hedging }))}
            names={["Euro investor", "Sterling investor"]}
            kind="signedPct"
            axisLabel="Change in annualised volatility"
          />
          <PaperTable
            n={2}
            caption={`Hedging by portfolio, ${start} to ${end}.`}
            head={["Portfolio", "Euro: volatility change", "Euro: correlation", "Euro: hedge ratio", "Sterling: volatility change", "Sterling: correlation", "Sterling: hedge ratio"]}
            rows={assets.map((a) => [
              INDUSTRY[a] ?? a,
              signedPct(eu.assets[a]!.risk_change_from_hedging, 1),
              num(eu.assets[a]!.corr_us_stocks_vs_dollar, 2),
              num(eu.assets[a]!.min_variance_hedge_ratio, 2),
              signedPct(gb.assets[a]!.risk_change_from_hedging, 1),
              num(gb.assets[a]!.corr_us_stocks_vs_dollar, 2),
              num(gb.assets[a]!.min_variance_hedge_ratio, 2),
            ])}
            note="Change in volatility is hedged volatility divided by unhedged volatility, minus one. Hedge ratio is the risk-minimising ratio of equation 3."
          />
        </Sub>

        <Sub n="4.2" title="The dollar in crises">
          <p>
            Table 3 reports cumulative returns over four episodes of US market stress. In the three since 2007 the dollar rose against both currencies, so the unhedged
            investor lost less than the hedged one. In the 2008 financial crisis US shares fell by {pct(-eu.crises_us_market[recent[0]!]!.local_usd, 1)} in dollars; a sterling
            investor who left the dollar unhedged lost {pct(-gb.crises_us_market[recent[0]!]!.unhedged, 1)}, against {pct(-gb.crises_us_market[recent[0]!]!.hedged, 1)} hedged,
            as sterling fell sharply.
          </p>
          <p>
            The 2000 to 2002 bear market went the other way. While US shares lost {pct(-eu.crises_us_market[dotcom]!.local_usd, 1)} in dollars, the price of a dollar fell by{" "}
            {pct(-eu.crises_us_market[dotcom]!.currency, 1)} in euro and {pct(-gb.crises_us_market[dotcom]!.currency, 1)} in sterling, so the unhedged investors lost more:{" "}
            {pct(-eu.crises_us_market[dotcom]!.unhedged, 1)} in euro and {pct(-gb.crises_us_market[dotcom]!.unhedged, 1)} in sterling, against{" "}
            {pct(-eu.crises_us_market[dotcom]!.hedged, 1)} and {pct(-gb.crises_us_market[dotcom]!.hedged, 1)} hedged. Over the whole sample the euro investor&apos;s maximum
            drawdown was deeper unhedged, at {pct(-m.euro.max_drawdown_unhedged, 1)}, than hedged, at {pct(-m.euro.max_drawdown_hedged, 1)}; for the sterling investor the two
            were similar, at {pct(-m.sterling.max_drawdown_unhedged, 1)} and {pct(-m.sterling.max_drawdown_hedged, 1)} (Table 1). The dollar&apos;s gains in recent crises are
            therefore a regularity of those episodes rather than a rule.
          </p>
          <PaperTable
            n={3}
            caption="The US market in four crises: cumulative returns."
            head={["Crisis", "US shares (USD)", "Dollar vs euro", "Euro, unhedged", "Euro, hedged", "Dollar vs sterling", "Sterling, unhedged", "Sterling, hedged"]}
            rows={crises.map((c) => [
              c,
              pct(eu.crises_us_market[c]!.local_usd, 1),
              signedPct(eu.crises_us_market[c]!.currency, 1),
              pct(eu.crises_us_market[c]!.unhedged, 1),
              pct(eu.crises_us_market[c]!.hedged, 1),
              signedPct(gb.crises_us_market[c]!.currency, 1),
              pct(gb.crises_us_market[c]!.unhedged, 1),
              pct(gb.crises_us_market[c]!.hedged, 1),
            ])}
            note="Dollar vs euro and dollar vs sterling are the changes in the investor's price of one dollar; a positive value means the dollar rose. The dot-com crash runs from September 2000 to September 2002, the 2008 financial crisis from November 2007 to March 2009, the Covid crash from February to March 2020, and the 2022 rate shock from January to September 2022."
          />
        </Sub>

        <Sub n="4.3" title="An unstable hedge ratio">
          <p>
            Figure 2 shows that the risk-minimising hedge ratio is far from constant. In five-year windows ending in the mid-2000s it was close to or above one for both investors:
            full hedging was then the low-risk choice. It fell steeply in the windows that include the 2008 crisis, and in windows ending {negativeYears[0]} to{" "}
            {negativeYears[negativeYears.length - 1]} it was negative for both: holding more dollars than the investment required would have lowered risk.
          </p>
          <YearLinesChart
            title="Figure 2. Risk-minimising hedge ratio for the US market, rolling five-year windows"
            note="1 means full hedging minimised risk; 0 means no hedging; below 0, extra dollar exposure would have reduced risk."
            years={years}
            series={INVESTORS.map((inv) => ({ name: `${inv === "euro" ? "Euro" : "Sterling"} investor`, values: years.map((y) => h[inv].rolling_5y_hedge_ratio_us_market[y] ?? null) }))}
            references={[
              { value: 1, label: "Fully hedged" },
              { value: 0, label: "Unhedged", position: "insideBottomLeft" },
            ]}
            kind="ratio"
            axisLabel="Hedge ratio"
          />
        </Sub>
      </Section>

      <Section n="5" title="Discussion">
        <p>
          The results support <Cite k="campbell2010" /> rather than the free-lunch view, with a qualification. Over the full sample the dollar has acted as a partial hedge
          against falls in US shares, so removing it has not reduced volatility, and in the three crises since 2007 hedging added to losses. The 2000 to 2002 bear market shows
          that this protection is not guaranteed: the dollar weakened over that episode, and hedging reduced losses. The risk-minimising hedge ratio is well below one over the
          full sample, closer to the partial hedge of <Cite k="black1989" /> than to full hedging. Its instability means that any fixed hedge ratio is a judgement about how
          currencies will behave in the next crisis, not a measured certainty.
        </p>
      </Section>

      <Section n="6" title="Limitations">
        <p>
          Forwards are priced from policy rates by covered interest parity. Since 2008 traded forwards have deviated from parity <Cite k="du2018" p />, and interbank rates
          differ from policy rates, so the cost of hedging in practice differs somewhat from that shown. We ignore transaction costs on the forwards and the residual currency
          exposure from monthly rebalancing of the hedge. The crises are fixed calendar windows around each episode, and other windows would give somewhat different
          numbers. The study covers US equities only, at a monthly frequency, and describes the past; it does not predict how
          currencies will behave.
        </p>
      </Section>

      <Section n="7" title="Conclusion">
        <p>
          For euro and sterling investors in US shares from {start} to {end}, hedging the dollar did not reduce volatility in any meaningful way and lowered the average
          return. It deepened losses in the three crises since 2007 and reduced them in the 2000 to 2002 bear market. The dollar&apos;s tendency to rise when shares fall
          has made it a natural, though unreliable, hedge. Over the full period a partial hedge minimised risk for both investors; hedging more or less than that amounts in
          practice to a view on currencies.
        </p>
      </Section>
    </Paper>
  );
}
