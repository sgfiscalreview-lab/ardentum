/**
 * Works cited by the research notes (/research/studies). Each entry gives the short form
 * used in the text and the full reference in APA style. A unit test checks that every
 * citation in a note points at an entry here and appears in that note's reference list.
 */
export interface Reference {
  /** Authors as cited in running text, e.g. "DeMiguel, Garlappi and Uppal". */
  cite: string;
  year: number;
  full: string;
}

export const REFERENCES = {
  bestGrauer1991: {
    cite: "Best and Grauer",
    year: 1991,
    full: "Best, M. J., & Grauer, R. R. (1991). On the sensitivity of mean-variance-efficient portfolios to changes in asset means: Some analytical and computational results. Review of Financial Studies, 4(2), 315–342.",
  },
  black1989: {
    cite: "Black",
    year: 1989,
    full: "Black, F. (1989). Universal hedging: Optimizing currency risk and reward in international equity portfolios. Financial Analysts Journal, 45(4), 16–22.",
  },
  campbell2010: {
    cite: "Campbell, Serfaty-de Medeiros and Viceira",
    year: 2010,
    full: "Campbell, J. Y., Serfaty-de Medeiros, K., & Viceira, L. M. (2010). Global currency hedging. Journal of Finance, 65(1), 87–121.",
  },
  charnesCooper1962: {
    cite: "Charnes and Cooper",
    year: 1962,
    full: "Charnes, A., & Cooper, W. W. (1962). Programming with linear fractional functionals. Naval Research Logistics Quarterly, 9(3–4), 181–186.",
  },
  chopraZiemba1993: {
    cite: "Chopra and Ziemba",
    year: 1993,
    full: "Chopra, V. K., & Ziemba, W. T. (1993). The effect of errors in means, variances, and covariances on optimal portfolio choice. Journal of Portfolio Management, 19(2), 6–11.",
  },
  demiguel2009: {
    cite: "DeMiguel, Garlappi and Uppal",
    year: 2009,
    full: "DeMiguel, V., Garlappi, L., & Uppal, R. (2009). Optimal versus naive diversification: How inefficient is the 1/N portfolio strategy? Review of Financial Studies, 22(5), 1915–1953.",
  },
  du2018: {
    cite: "Du, Tepper and Verdelhan",
    year: 2018,
    full: "Du, W., Tepper, A., & Verdelhan, A. (2018). Deviations from covered interest rate parity. Journal of Finance, 73(3), 915–957.",
  },
  ederington1979: {
    cite: "Ederington",
    year: 1979,
    full: "Ederington, L. H. (1979). The hedging performance of the new futures markets. Journal of Finance, 34(1), 157–170.",
  },
  frenchData: {
    cite: "French",
    year: 2026,
    full: "French, K. R. (2026). Data library: 12 industry portfolios and Fama/French 3 factors [Data set]. Tuck School of Business at Dartmouth. https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html",
  },
  froot1993: {
    cite: "Froot",
    year: 1993,
    full: "Froot, K. A. (1993). Currency hedging over long horizons (NBER Working Paper No. 4355). National Bureau of Economic Research.",
  },
  glenJorion1993: {
    cite: "Glen and Jorion",
    year: 1993,
    full: "Glen, J., & Jorion, P. (1993). Currency hedging for international portfolios. Journal of Finance, 48(5), 1865–1886.",
  },
  jagannathanMa2003: {
    cite: "Jagannathan and Ma",
    year: 2003,
    full: "Jagannathan, R., & Ma, T. (2003). Risk reduction in large portfolios: Why imposing the wrong constraints helps. Journal of Finance, 58(4), 1651–1683.",
  },
  jobsonKorkie1980: {
    cite: "Jobson and Korkie",
    year: 1980,
    full: "Jobson, J. D., & Korkie, B. (1980). Estimation for Markowitz efficient portfolios. Journal of the American Statistical Association, 75(371), 544–554.",
  },
  jobsonKorkie1981: {
    cite: "Jobson and Korkie",
    year: 1981,
    full: "Jobson, J. D., & Korkie, B. M. (1981). Performance hypothesis testing with the Sharpe and Treynor measures. Journal of Finance, 36(4), 889–908.",
  },
  jorion1986: {
    cite: "Jorion",
    year: 1986,
    full: "Jorion, P. (1986). Bayes-Stein estimation for portfolio analysis. Journal of Financial and Quantitative Analysis, 21(3), 279–292.",
  },
  kanZhou2007: {
    cite: "Kan and Zhou",
    year: 2007,
    full: "Kan, R., & Zhou, G. (2007). Optimal portfolio choice with parameter uncertainty. Journal of Financial and Quantitative Analysis, 42(3), 621–656.",
  },
  kirbyOstdiek2012: {
    cite: "Kirby and Ostdiek",
    year: 2012,
    full: "Kirby, C., & Ostdiek, B. (2012). It's all in the timing: Simple active portfolio strategies that outperform naive diversification. Journal of Financial and Quantitative Analysis, 47(2), 437–467.",
  },
  ledoitWolf2004: {
    cite: "Ledoit and Wolf",
    year: 2004,
    full: "Ledoit, O., & Wolf, M. (2004). A well-conditioned estimator for large-dimensional covariance matrices. Journal of Multivariate Analysis, 88(2), 365–411.",
  },
  ledoitWolf2008: {
    cite: "Ledoit and Wolf",
    year: 2008,
    full: "Ledoit, O., & Wolf, M. (2008). Robust performance hypothesis testing with the Sharpe ratio. Journal of Empirical Finance, 15(5), 850–859.",
  },
  lo2002: {
    cite: "Lo",
    year: 2002,
    full: "Lo, A. W. (2002). The statistics of Sharpe ratios. Financial Analysts Journal, 58(4), 36–52.",
  },
  markowitz1952: {
    cite: "Markowitz",
    year: 1952,
    full: "Markowitz, H. (1952). Portfolio selection. Journal of Finance, 7(1), 77–91.",
  },
  memmel2003: {
    cite: "Memmel",
    year: 2003,
    full: "Memmel, C. (2003). Performance hypothesis testing with the Sharpe ratio. Finance Letters, 1, 21–23.",
  },
  michaud1989: {
    cite: "Michaud",
    year: 1989,
    full: "Michaud, R. O. (1989). The Markowitz optimization enigma: Is 'optimized' optimal? Financial Analysts Journal, 45(1), 31–42.",
  },
  neweyWest1994: {
    cite: "Newey and West",
    year: 1994,
    full: "Newey, W. K., & West, K. D. (1994). Automatic lag selection in covariance matrix estimation. Review of Economic Studies, 61(4), 631–653.",
  },
  perold1988: {
    cite: "Perold and Schulman",
    year: 1988,
    full: "Perold, A. F., & Schulman, E. C. (1988). The free lunch in currency hedging: Implications for investment policy and performance standards. Financial Analysts Journal, 44(3), 45–50.",
  },
  rockafellarUryasev2000: {
    cite: "Rockafellar and Uryasev",
    year: 2000,
    full: "Rockafellar, R. T., & Uryasev, S. (2000). Optimization of conditional value-at-risk. Journal of Risk, 2(3), 21–41.",
  },
  sharpe1966: {
    cite: "Sharpe",
    year: 1966,
    full: "Sharpe, W. F. (1966). Mutual fund performance. Journal of Business, 39(1), 119–138.",
  },
  tuZhou2011: {
    cite: "Tu and Zhou",
    year: 2011,
    full: "Tu, J., & Zhou, G. (2011). Markowitz meets Talmud: A combination of sophisticated and naive diversification strategies. Journal of Financial Economics, 99(1), 204–215.",
  },
  ecbRates: {
    cite: "European Central Bank",
    year: 2026,
    full: "European Central Bank. (2026). Euro foreign exchange reference rates [Data set], retrieved through the Frankfurter service. https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html",
  },
  bisRates: {
    cite: "Bank for International Settlements",
    year: 2026,
    full: "Bank for International Settlements. (2026). Central bank policy rates (WS_CBPOL) [Data set]. https://data.bis.org",
  },
} satisfies Record<string, Reference>;

export type RefKey = keyof typeof REFERENCES;
