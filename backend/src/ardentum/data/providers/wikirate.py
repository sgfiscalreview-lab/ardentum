"""WikiRate (https://wikirate.org): open ESG data, mostly licensed CC BY 4.0.

WikiRate is a non-profit, community-researched database of company ESG disclosures
(emissions, energy, labour, governance, ...) with each answer linked to its source
document. Its REST API (``https://data.wikirate.org/rest/v1``, documented at
https://wikirate.org/api) is read-only and answers every request with a JSON array of
rows:

* ``/v1_metrics`` — ``id``, ``metric_name``, ``metric_designer``, ``metric_type``
  (researched, formula, score, ...), ``value_type`` (number, money, category, ...),
  ``unit``, ``range``.
* ``/v1_companies`` — ``id``, ``name``, ``headquarters`` (an object with ``name``) and
  ``company_identifiers`` (an object such as ``{"lei": "...", "isin": ["..."]}``).
* ``/v1_answers`` — one value for one company, metric and year: ``company_id``,
  ``company``, ``year``, ``value`` (always text), ``sources`` and ``license``.

Requests are shaped with query parameters: ``select`` (columns), ``column=operator.value``
filters (``eq``, ``in``, ``like``/``ilike`` with ``*`` as the wildcard, ``->>`` to reach
into an object), ``order``, and ``limit``/``offset`` (at most 1,000 rows a response).

Every request needs a free account's two values: the publishable key (header ``apikey``)
and a personal token (``x-api-token``), plus ``Accept-Profile: api``. The API that
answered at ``wikirate.org/*.json`` without a key stopped answering in autumn 2026.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from ardentum.data.errors import DataProviderError
from ardentum.data.http import shared_client

BASE_URL = "https://data.wikirate.org/rest/v1"
SITE_URL = "https://wikirate.org"
LICENSE = "WikiRate.org, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0)"
NUMERIC_TYPES = frozenset({"number", "money", "score", "percentage", "float", "integer"})
PAGE = 1000  # the most rows the API returns in one response
MAX_PAGES = 5
NOT_SET_UP = (
    "Open ESG data is switched off on this server: WikiRate now asks for a free account. "
    "The operator can switch it on by setting ARDENTUM_WIKIRATE_PUBLISHABLE_KEY and "
    "ARDENTUM_WIKIRATE_API_TOKEN (wikirate.org, account menu, API access)."
)
METRIC_COLUMNS = "id,metric_name,metric_designer,metric_type,value_type,unit,range"
COMPANY_COLUMNS = "id,name,headquarters,company_identifiers"
ANSWER_COLUMNS = "id,company_id,company,year,value,sources,license"
ISIN_RE = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")


class BadRequestError(DataProviderError):
    """WikiRate did not accept a filter (HTTP 400)."""


@dataclass(frozen=True)
class OpenMetric:
    id: int
    designer: str
    title: str
    value_type: str | None
    metric_type: str | None
    unit: str | None
    range: str | None
    answers: int | None
    topics: tuple[str, ...]
    url: str

    @property
    def name(self) -> str:
        return f"{self.designer}+{self.title}"

    @property
    def numeric(self) -> bool:
        return (self.value_type or "").lower() in NUMERIC_TYPES or (
            self.metric_type or ""
        ).lower() in {"score", "wikirating"}


@dataclass(frozen=True)
class OpenCompany:
    id: int
    name: str
    headquarters: str | None
    isins: tuple[str, ...]
    url: str


@dataclass(frozen=True)
class OpenAnswer:
    company_id: int
    company: str
    year: int
    value: str
    url: str  # the answer's source document, when WikiRate lists one
    license: str | None  # as stated by the answer, e.g. "CC BY 4.0"
    cc_by: bool  # False only when the answer states a licence other than CC BY 4.0


def _str(v: Any) -> str | None:
    return v.strip() or None if isinstance(v, str) else None


def _range(v: Any) -> str | None:
    """The allowed range as 'low-high'. The object's field names are not documented, so the
    usual pairs are read and anything else is left out (the user then sets the scale)."""
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, dict):
        for lo, hi in (("min", "max"), ("from", "to"), ("lower", "upper"), ("low", "high")):
            if lo in v and hi in v:
                v = [v[lo], v[hi]]
                break
    if isinstance(v, list) and len(v) == 2:
        try:
            return f"{float(v[0]):g}-{float(v[1]):g}"
        except (TypeError, ValueError):
            return None
    return None


def page_url(*names: str) -> str:
    """The page of a company (its name) or a metric (designer, title) on wikirate.org,
    which addresses pages by name with every run of other characters as one underscore."""
    parts = [re.sub(r"[^\w]+", "_", n).strip("_") for n in names]
    return f"{SITE_URL}/{'+'.join(parts)}" if all(parts) else ""


def _web_url(value: Any) -> str:
    """A link to show users: only http(s) addresses, so a stray ``javascript:`` or
    ``data:`` value from the source can never become a link."""
    url = str(value or "").strip()
    return url if url.lower().startswith(("https://", "http://")) else ""


def check_json(payload: bytes) -> None:
    """Every WikiRate response used here is a JSON array; anything else is not cached."""
    rows(payload)


def rows(payload: bytes) -> list[dict[str, Any]]:
    try:
        data = json.loads(payload)
    except ValueError as exc:
        raise DataProviderError("Unexpected response format from WikiRate.") from exc
    if not isinstance(data, list):
        raise DataProviderError("Unexpected response format from WikiRate.")
    return [row for row in data if isinstance(row, dict)]


def parse_metrics(payload: bytes) -> list[OpenMetric]:
    out = []
    for it in rows(payload):
        try:
            designer = str(it.get("metric_designer") or "")
            title = str(it["metric_name"])
            out.append(
                OpenMetric(
                    id=int(it["id"]),
                    designer=designer,
                    title=title,
                    value_type=_str(it.get("value_type")),
                    metric_type=_str(it.get("metric_type")),
                    unit=_str(it.get("unit")),
                    range=_range(it.get("range")),
                    answers=None,  # the API no longer reports how many answers a metric has
                    topics=(),
                    url=page_url(designer, title),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue  # skip malformed rows rather than fail the whole search
    return out


def parse_metric(payload: bytes) -> OpenMetric:
    """The one metric of a ``metric_query`` response."""
    metrics = parse_metrics(payload)
    if not metrics:
        raise DataProviderError("WikiRate has no such metric.")
    return metrics[0]


def _isins(identifiers: Any) -> tuple[str, ...]:
    v = identifiers.get("isin") if isinstance(identifiers, dict) else None
    v = [v] if isinstance(v, str) else v if isinstance(v, list) else []
    return tuple(i.strip().upper() for i in v if isinstance(i, str) and i.strip())


def parse_companies(payload: bytes) -> list[OpenCompany]:
    out = []
    for it in rows(payload):
        try:
            hq = it.get("headquarters")
            name = str(it["name"])
            out.append(
                OpenCompany(
                    id=int(it["id"]),
                    name=name,
                    headquarters=_str(hq.get("name") if isinstance(hq, dict) else hq),
                    isins=_isins(it.get("company_identifiers")),
                    url=page_url(name),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _license(v: Any) -> tuple[str | None, bool]:
    """The licence an answer states, and whether it is CC BY 4.0 (or none is stated)."""
    if isinstance(v, str):
        v = {"abbreviation": v}
    if not isinstance(v, dict):
        return None, True
    short, name = _str(v.get("abbreviation")), _str(v.get("name"))
    cc_by = (
        bool(re.fullmatch(r"cc[ -]?by[ -]?4\.0", (short or "").lower()))
        or (name or "").lower().startswith("creative commons attribution 4.0")
        or "creativecommons.org/licenses/by/4.0" in str(v.get("reference_url") or "")
    )
    stated = short or name
    return stated, cc_by or stated is None


def _source_url(sources: Any) -> str:
    for src in sources if isinstance(sources, list) else []:
        if isinstance(src, dict) and (url := _web_url(src.get("original_url"))):
            return url
    return ""


def parse_answers(payload: bytes) -> list[OpenAnswer]:
    out = []
    for it in rows(payload):
        try:
            stated, cc_by = _license(it.get("license"))
            out.append(
                OpenAnswer(
                    company_id=int(it["company_id"]),
                    company=str(it.get("company") or ""),
                    year=int(it["year"]),
                    value=str(it.get("value") or ""),
                    url=_source_url(it.get("sources")),
                    license=stated,
                    cc_by=cc_by,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def parse_number(value: str) -> float | None:
    """Numeric answer values; 'Unknown', categories and text are not numbers."""
    try:
        x = float(value.replace(",", "").strip())
    except (AttributeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


class WikiRateClient:
    def __init__(
        self,
        publishable_key: str | None = None,
        api_token: str | None = None,
        *,
        client: httpx.Client | None = None,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        self.configured = bool(publishable_key and api_token)
        self._base = base_url.rstrip("/")
        self._client = client or shared_client()
        self._timeout = timeout
        self._headers = {
            "Accept": "application/json",
            "Accept-Profile": "api",
            "apikey": publishable_key or "",
            "x-api-token": api_token or "",
        }

    def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._client.get(url, timeout=self._timeout, **kwargs)

    def get(self, path: str, params: list[tuple[str, str]]) -> bytes:
        if not self.configured:
            raise DataProviderError(NOT_SET_UP)
        try:
            resp = self._get(f"{self._base}{path}", params=tuple(params), headers=self._headers)
        except httpx.HTTPError as exc:
            raise DataProviderError(f"WikiRate is unreachable: {exc}") from exc
        if resp.status_code in (401, 403):
            raise DataProviderError(
                "WikiRate refused the server's keys; the operator should check "
                "ARDENTUM_WIKIRATE_PUBLISHABLE_KEY and ARDENTUM_WIKIRATE_API_TOKEN (a token "
                "may have been revoked)."
            )
        if resp.status_code == 400:
            raise BadRequestError("WikiRate did not accept the request (HTTP 400).")
        if resp.status_code == 416:  # an offset past the last row: no more rows
            return b"[]"
        if resp.status_code != 200:
            raise DataProviderError(f"WikiRate request failed (HTTP {resp.status_code}).")
        return resp.content


def _pattern(q: str) -> str:
    """A search text inside ``ilike.*...*``, where ``*`` is the wildcard."""
    return " ".join(q.replace("*", " ").split())


def metrics_query(q: str, limit: int) -> tuple[str, list[tuple[str, str]]]:
    return "/v1_metrics", [
        ("select", METRIC_COLUMNS),
        ("metric_name", f"ilike.*{_pattern(q)}*"),
        ("order", "metric_name"),
        ("limit", str(limit)),
    ]


def metric_query(metric_id: int) -> tuple[str, list[tuple[str, str]]]:
    return "/v1_metrics", [("select", METRIC_COLUMNS), ("id", f"eq.{metric_id}")]


def companies_by_name_query(q: str, limit: int) -> tuple[str, list[tuple[str, str]]]:
    return "/v1_companies", [
        ("select", COMPANY_COLUMNS),
        ("name", f"ilike.*{_pattern(q)}*"),
        ("order", "name"),
        ("limit", str(limit)),
    ]


def company_query(company_id: int) -> tuple[str, list[tuple[str, str]]]:
    return "/v1_companies", [("select", COMPANY_COLUMNS), ("id", f"eq.{company_id}")]


def companies_by_isin_query(isins: list[str]) -> tuple[str, list[tuple[str, str]]]:
    """Companies listing any of the ISINs. The identifiers are an object, read as text, so
    callers keep only the companies whose parsed ISINs match exactly. Anything that is not
    an ISIN is left out: it cannot match, and must not become part of the filter."""
    tests = [f"company_identifiers->>isin.like.*{i}*" for i in isins if ISIN_RE.fullmatch(i)]
    if not tests:
        raise ValueError("no valid ISIN to look up")
    if len(tests) == 1:
        test = ("company_identifiers->>isin", tests[0].split(".", 1)[1])
    else:
        test = ("or", f"({','.join(tests)})")
    return "/v1_companies", [("select", COMPANY_COLUMNS), test, ("limit", str(PAGE))]


def answers_query(
    metric_id: int, company_ids: list[int], offset: int
) -> tuple[str, list[tuple[str, str]]]:
    return "/v1_answers", [
        ("select", ANSWER_COLUMNS),
        ("metric_id", f"eq.{metric_id}"),
        ("company_id", f"in.({','.join(str(int(c)) for c in company_ids)})"),
        ("order", "id"),
        ("limit", str(PAGE)),
        ("offset", str(offset)),
    ]
