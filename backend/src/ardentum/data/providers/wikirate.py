"""WikiRate (https://wikirate.org): open ESG data, licensed CC BY 4.0.

WikiRate is a non-profit, community-researched database of company ESG disclosures
(emissions, energy, labour, governance, ...) with each answer linked to its source
document. The REST API serves JSON "cards":

* ``/Metrics.json`` — metrics, with ``filter[name]``; items carry ``id``, ``designer``,
  ``title``, ``value_type`` (Number, Money, Category, ...), ``unit``, ``range``,
  ``metric_type`` (Researched, Score, Formula, ...), ``answer`` (count), ``topics``.
* ``/Companies.json`` — companies, with ``filter[name]`` or
  ``filter[company_identifier[value]]`` (ISIN, LEI, ...); items carry ``id``, ``name``,
  ``headquarters`` and ``international_securities_identification_number`` (a list).
* ``/~{metric_id}+Answers.json`` — answers of one metric, with ``filter[company][]``
  (``~{company_id}``); items carry ``company``, ``year``, ``value`` (a string) and
  ``answer_url``/``url``.

Collections page with ``limit``/``offset`` and report ``paging.next``. Every response
states its licence. An API key (free account) is sent as ``X-API-Key`` when
configured. (Format per the WikiRate API documentation and the recorded responses
of the wikirate4py client.)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from ardentum.data.errors import DataProviderError
from ardentum.data.http import shared_client

BASE_URL = "https://wikirate.org"
LICENSE = "WikiRate.org, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0)"
NUMERIC_TYPES = frozenset({"Number", "Money", "Score", "Percentage", "Float", "Integer"})
PAGE = 100
MAX_PAGES = 20


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
        return self.value_type in NUMERIC_TYPES or self.metric_type in {"Score", "WikiRating"}


@dataclass(frozen=True)
class OpenCompany:
    id: int
    name: str
    headquarters: str | None
    isins: tuple[str, ...]
    url: str


@dataclass(frozen=True)
class OpenAnswer:
    company: str
    year: int
    value: str
    url: str


def _text(v: Any) -> str | None:
    """Card fields are plain values in list views and nested cards in single-card views,
    where the value is under ``content`` (absent or null when the field is empty)."""
    if v is None:
        return None
    if isinstance(v, dict):
        return _text(v.get("content"))
    if isinstance(v, list):
        return ", ".join(t for x in v if (t := _text(x))) or None
    return str(v)


def _list(v: Any) -> list[str]:
    if isinstance(v, dict):
        v = v.get("content")
    if isinstance(v, str):
        return [v]
    return [str(x) for x in v if isinstance(x, str)] if isinstance(v, list) else []


def _items(payload: bytes) -> tuple[list[dict[str, Any]], str | None]:
    try:
        data = json.loads(payload)
        items = data["items"]
        nxt = (data.get("paging") or {}).get("next")
    except (KeyError, TypeError, ValueError) as exc:
        raise DataProviderError("Unexpected response format from WikiRate.") from exc
    if not isinstance(items, list):
        raise DataProviderError("Unexpected response format from WikiRate.")
    return items, nxt


def parse_metrics(payload: bytes) -> list[OpenMetric]:
    out = []
    for it in _items(payload)[0]:
        try:
            out.append(
                OpenMetric(
                    id=int(it["id"]),
                    designer=str(_text(it.get("designer")) or ""),
                    title=str(_text(it.get("title")) or it.get("name", "")),
                    value_type=_text(it.get("value_type")),
                    metric_type=_text(it.get("metric_type")),
                    unit=(_text(it.get("unit")) or "").strip() or None,
                    range=_text(it.get("range")),
                    answers=int(it["answer"]) if isinstance(it.get("answer"), int) else None,
                    topics=tuple(t.split("+")[-1] for t in _list(it.get("topics"))),
                    url=_web_url(it.get("url")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue  # skip malformed cards rather than fail the whole search
    return out


def parse_companies(payload: bytes) -> list[OpenCompany]:
    out = []
    for it in _items(payload)[0]:
        try:
            isins = _list(it.get("international_securities_identification_number"))
            out.append(
                OpenCompany(
                    id=int(it["id"]),
                    name=str(it["name"]),
                    headquarters=_text(it.get("headquarters")),
                    isins=tuple(i.strip().upper() for i in isins),
                    url=_web_url(it.get("url")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _web_url(value: Any) -> str:
    """A link to show users: only http(s) addresses, so a stray ``javascript:`` or
    ``data:`` value from the source can never become a link."""
    url = str(value or "").strip().removesuffix(".json")
    return url if url.lower().startswith(("https://", "http://")) else ""


def parse_answers(payload: bytes) -> tuple[list[OpenAnswer], str | None]:
    items, nxt = _items(payload)
    out = []
    for it in items:
        try:
            out.append(
                OpenAnswer(
                    company=str(it["company"]),
                    year=int(it["year"]),
                    value=str(_text(it.get("value")) or ""),
                    url=_web_url(it.get("url") or it.get("answer_url")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out, nxt


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
        api_key: str | None = None,
        *,
        client: httpx.Client | None = None,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        self._base = base_url.rstrip("/")
        self._client = client or shared_client()
        self._timeout = timeout
        self._headers = headers

    def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._client.get(url, timeout=self._timeout, **kwargs)

    def get(self, path: str, params: list[tuple[str, str]]) -> bytes:
        try:
            resp = self._get(f"{self._base}{path}", params=tuple(params), headers=self._headers)
        except httpx.HTTPError as exc:
            raise DataProviderError(f"WikiRate is unreachable: {exc}") from exc
        if resp.status_code in (401, 403):
            raise DataProviderError(
                "WikiRate refused the request; the server may need a (free) WikiRate API key "
                "in ARDENTUM_WIKIRATE_API_KEY."
            )
        if resp.status_code == 404:
            raise DataProviderError("WikiRate has no such metric or company.")
        if resp.status_code != 200:
            raise DataProviderError(f"WikiRate request failed (HTTP {resp.status_code}).")
        return resp.content


def metrics_query(q: str, limit: int) -> tuple[str, list[tuple[str, str]]]:
    return "/Metrics.json", [("filter[name]", q), ("limit", str(limit))]


def metric_path(metric_id: int) -> str:
    return f"/~{metric_id}.json"


def companies_by_name_query(q: str, limit: int) -> tuple[str, list[tuple[str, str]]]:
    return "/Companies.json", [("filter[name]", q), ("limit", str(limit))]


def companies_by_isin_query(isins: list[str]) -> tuple[str, list[tuple[str, str]]]:
    return "/Companies.json", [
        ("filter[company_identifier[value]]", ", ".join(isins)),
        ("limit", str(PAGE)),
    ]


def answers_query(
    metric_id: int, company_ids: list[int], offset: int
) -> tuple[str, list[tuple[str, str]]]:
    params = [("filter[company][]", f"~{c}") for c in company_ids]
    params += [("limit", str(PAGE)), ("offset", str(offset))]
    return f"/~{metric_id}+Answers.json", params


def parse_metric(payload: bytes) -> OpenMetric:
    """A single metric card (``/~{id}.json``), whose fields are nested cards."""
    try:
        data = json.loads(payload)
    except ValueError as exc:
        raise DataProviderError("Unexpected response format from WikiRate.") from exc
    metrics = parse_metrics(json.dumps({"items": [data]}).encode())
    if not metrics:
        raise DataProviderError("Unexpected metric format from WikiRate.")
    return metrics[0]
