"""Exception hierarchy for the quantitative engine.

Every failure mode that could otherwise yield a financially misleading number
raises one of these explicitly. The API layer maps them to HTTP 422 responses
with the message shown to the user, so messages must be precise and actionable.
"""


class QuantError(Exception):
    """Base class for all quantitative-engine errors."""


class InvalidInputError(QuantError):
    """Inputs are malformed (NaNs, wrong shapes, non-positive prices, ...)."""


class InsufficientDataError(QuantError):
    """Too few observations for a statistically meaningful estimate."""


class UndefinedMetricError(QuantError):
    """A metric is mathematically undefined for the given inputs (e.g. zero volatility)."""


class InfeasibleProblemError(QuantError):
    """An optimisation problem has no solution under the requested constraints."""


class SolverError(QuantError):
    """The numerical solver failed or returned a solution that fails verification."""
