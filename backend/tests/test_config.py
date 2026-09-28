"""Settings parsing that deployments commonly get slightly wrong."""

from __future__ import annotations

import pytest

from ardentum.config import Settings


@pytest.mark.parametrize(
    "raw",
    [
        '["https://ardentum.pages.dev"]',
        '["https://ardentum.pages.dev/"]',
        "https://ardentum.pages.dev",
        " https://ardentum.pages.dev/ ",
    ],
)
def test_cors_origins_accept_json_or_plain_and_drop_trailing_slash(
    raw: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARDENTUM_CORS_ORIGINS", raw)
    assert Settings().cors_origins == ["https://ardentum.pages.dev"]


def test_cors_origins_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARDENTUM_CORS_ORIGINS", "https://a.dev, https://b.dev/,")
    assert Settings().cors_origins == ["https://a.dev", "https://b.dev"]


def test_invalid_json_says_how_to_fix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARDENTUM_CORS_ORIGINS", '["https://a.dev"')
    with pytest.raises(ValueError, match="comma-separated"):
        Settings()
