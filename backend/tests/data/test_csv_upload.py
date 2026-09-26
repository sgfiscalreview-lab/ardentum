import pytest

from ardentum.data.models import AssetClass
from ardentum.data.providers.csv_upload import parse_metadata_csv, parse_price_csv
from ardentum.quant.errors import InvalidInputError


def test_wide_format() -> None:
    csv = b"date,aaa,BBB\n2024-01-03,10,20\n2024-01-02,9,19\n2024-01-04,11,\n"
    df = parse_price_csv(csv)
    assert list(df.columns) == ["AAA", "BBB"]
    assert df.index[0].isoformat()[:10] == "2024-01-02"  # sorted
    assert df.isna().sum().sum() == 1


def test_long_format() -> None:
    csv = (
        b"Date,Ticker,Adj_Close\n2024-01-02,AAA,10\n2024-01-02,BBB,20\n"
        b"2024-01-03,AAA,11\n2024-01-03,BBB,21\n2024-01-04,AAA,12\n2024-01-04,BBB,22\n"
    )
    df = parse_price_csv(csv)
    assert df.shape == (3, 2)
    assert df.loc["2024-01-03", "BBB"] == 21


def test_utf8_bom_and_thousands_separator() -> None:
    csv = '﻿date,AAA\n2024-01-02,"1,000.5"\n2024-01-03,1001\n2024-01-04,1002\n'.encode()
    assert parse_price_csv(csv).iloc[0, 0] == 1000.5


@pytest.mark.parametrize(
    ("csv", "match"),
    [
        (b"date,AAA\n02/01/2024,1\n03/01/2024,2\n04/01/2024,3\n", "ISO-8601"),
        (b"date,AAA\n2024-01-02,abc\n2024-01-03,2\n2024-01-04,3\n", "non-numeric"),
        (b"date,AAA\n2024-01-02,-1\n2024-01-03,2\n2024-01-04,3\n", "positive"),
        (b"date,AAA\n2024-01-02,1\n2024-01-02,2\n2024-01-04,3\n", "Duplicate dates"),
        (b"date,A A\n2024-01-02,1\n2024-01-03,2\n2024-01-04,3\n", "Invalid ticker"),
        (b"date,ticker,volume\n2024-01-02,AAA,1\n", "price column"),
        (b"date,AAA\n2024-01-02,1\n", "three dates"),
        (b"", "Could not parse"),
    ],
)
def test_rejections(csv: bytes, match: str) -> None:
    with pytest.raises(InvalidInputError, match=match):
        parse_price_csv(csv)


def test_metadata_with_esg_provenance() -> None:
    csv = (
        b"ticker,name,sector,asset_class,esg_score,esg_source,esg_as_of\n"
        b"aaa,Alpha Corp,Tech,equity,71.5,MyVendor,2025-06-30\n"
        b"BBB,Beta Bonds,,fixed_income,,,\n"
    )
    assets = parse_metadata_csv(csv)
    a, b = assets
    assert a.ticker == "AAA"
    assert a.esg is not None
    assert a.esg.score == 71.5
    assert a.esg.source == "MyVendor"
    assert not a.esg.is_synthetic
    assert b.esg is None
    assert b.asset_class is AssetClass.FIXED_INCOME
    assert b.sector is None


def test_metadata_requires_esg_source() -> None:
    with pytest.raises(InvalidInputError, match="esg_source"):
        parse_metadata_csv(b"ticker,esg_score\nAAA,50\n")
    with pytest.raises(InvalidInputError, match="between 0 and 100"):
        parse_metadata_csv(b"ticker,esg_score,esg_source\nAAA,150,X\n")
