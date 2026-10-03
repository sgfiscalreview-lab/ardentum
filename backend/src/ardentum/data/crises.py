"""Historical market crises used by the crisis replay.

Each episode runs from the US stock market's closing high before the crisis to its
closing low, so every portfolio is measured over the same dates. Dates are the S&P 500's
closing high and low (S&P Dow Jones Indices); for 1929 to 1932, before the S&P 500
existed in its current form, the Dow Jones Industrial Average's. A portfolio's own worst
point can fall on other dates; the replay reports it separately.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

SOURCE = (
    "Peak and low dates: S&P 500 closing levels (S&P Dow Jones Indices); "
    "Dow Jones Industrial Average for 1929 to 1932."
)


@dataclass(frozen=True)
class Episode:
    key: str
    name: str
    start: dt.date  # the market's closing high: the replay starts at this close
    end: dt.date  # the market's closing low: the replay ends at this close
    summary: str


EPISODES: tuple[Episode, ...] = (
    Episode(
        "crash_1929",
        "1929 crash and Great Depression",
        dt.date(1929, 9, 3),
        dt.date(1932, 7, 8),
        "Shares fell for almost three years as the US economy collapsed.",
    ),
    Episode(
        "oil_1973",
        "1973 to 1974 oil crisis",
        dt.date(1973, 1, 11),
        dt.date(1974, 10, 3),
        "An oil embargo, high inflation and a deep recession.",
    ),
    Episode(
        "crash_1987",
        "1987 crash (Black Monday)",
        dt.date(1987, 8, 25),
        dt.date(1987, 12, 4),
        "The market fell more than 20% in a single day on 19 October 1987.",
    ),
    Episode(
        "dotcom_2000",
        "Dot-com crash",
        dt.date(2000, 3, 24),
        dt.date(2002, 10, 9),
        "Technology shares collapsed after a speculative boom.",
    ),
    Episode(
        "gfc_2007",
        "Global financial crisis",
        dt.date(2007, 10, 9),
        dt.date(2009, 3, 9),
        "House prices and mortgage lending collapsed; several large banks failed or were rescued.",
    ),
    Episode(
        "covid_2020",
        "COVID-19 crash",
        dt.date(2020, 2, 19),
        dt.date(2020, 3, 23),
        "Markets fell sharply as the pandemic shut down economies.",
    ),
    Episode(
        "inflation_2022",
        "2022 inflation and rate rises",
        dt.date(2022, 1, 3),
        dt.date(2022, 10, 12),
        "Central banks raised interest rates quickly to fight inflation; shares and "
        "bonds fell together.",
    ),
)

BY_KEY = {e.key: e for e in EPISODES}
