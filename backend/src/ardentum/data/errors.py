"""Data-layer errors."""

from ardentum.quant.errors import QuantError


class DataProviderError(QuantError):
    """An external data provider failed or rejected the request."""


class DataNotConfiguredError(DataProviderError):
    """A provider is not configured (e.g. missing API key)."""
