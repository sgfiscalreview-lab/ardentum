"""Open ESG data (WikiRate, CC BY 4.0) turned into explained, sourced 0-100 scores.

Pipeline for a dataset's assets:

1. **Match companies** — automatically only by ISIN (an exact identifier); other matches
   must be confirmed by the user (``company_overrides``). Names are never fuzzy-matched
   silently: a wrong match would attach another company's data.
2. **Pick answers** — per company, the latest answer up to the chosen year.
3. **Score** — numeric answers are mapped to 0-100 by a fixed linear scale or by
   percentile rank within the matched group (:mod:`ardentum.quant.esg`), with the
   direction chosen by the user (e.g. lower emissions are better).

Assets without a company match, an answer or a numeric value get **no score** (never
imputed); each carries the reason. Saved overlays replace the dataset's ESG scores for
the selected assets when a universe references them.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from collections.abc import Sequence
from dataclasses import replace
from typing import Any
from urllib.parse import urlencode

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ardentum.api import schemas as s
from ardentum.api.auth import Principal
from ardentum.data.errors import DataProviderError
from ardentum.data.models import AssetInfo, DatasetInfo, EsgRecord
from ardentum.data.providers import demo, kenfrench, wikirate
from ardentum.db.models import EsgOverlay, User
from ardentum.quant.errors import InvalidInputError
from ardentum.quant.esg import composite_scores, percentile_scores, scale_linear
from ardentum.services.market_data import MarketDataService, NotFoundError
from ardentum.services.provider_cache import CachedPayload

WIKIRATE_MAX_AGE = dt.timedelta(days=1)
MAX_OVERLAYS_PER_USER = 100
ISIN_CHUNK = 20
COMPANY_CHUNK = 25
SOURCE = "wikirate"


def _cache_key(path: str, params: Sequence[tuple[str, str]]) -> str:
    key = path + "?" + urlencode(list(params))
    return key if len(key) <= 200 else "sha256:" + hashlib.sha256(key.encode()).hexdigest()


def metric_out(m: wikirate.OpenMetric) -> s.OpenMetricOut:
    return s.OpenMetricOut(
        id=m.id,
        designer=m.designer,
        title=m.title,
        value_type=m.value_type,
        metric_type=m.metric_type,
        unit=m.unit,
        range=m.range,
        answers=m.answers,
        topics=list(m.topics),
        url=m.url,
        numeric=m.numeric,
    )


def parse_range(r: str | None) -> tuple[float, float] | None:
    """WikiRate ranges look like '0-10'."""
    if not r:
        return None
    parts = r.replace("–", "-").split("-")
    if len(parts) != 2:
        return None
    try:
        lo, hi = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    return (lo, hi) if hi > lo else None


def describe_transform(t: s.EsgTransformIn) -> str:
    direction = "higher is better" if t.higher_is_better else "lower is better"
    if t.method == "linear":
        return f"linear scale from {t.lower:g} (score 0) to {t.upper:g} (score 100), {direction}"
    return f"percentile rank among matched companies, {direction}"


def composite_attribution(metrics: Sequence[s.OpenMetricOut]) -> str:
    listed = "; ".join(f"“{m.title}” by {m.designer} ({m.url})" for m in metrics)
    return (
        f"ESG data from WikiRate.org, licensed CC BY 4.0: {listed}. Scores are Ardentum "
        "transformations of the published answers, combined with the weights shown."
    )


def attribution(metric: wikirate.OpenMetric) -> str:
    return (
        f"ESG data: “{metric.title}” by {metric.designer}, from WikiRate.org "
        f"({metric.url}), licensed CC BY 4.0. Scores are Ardentum transformations of "
        "the published answers."
    )


class OpenEsgService:
    def __init__(self, market: MarketDataService) -> None:
        self.market = market
        self.client = wikirate.WikiRateClient(
            market.settings.wikirate_api_key, base_url=market.settings.wikirate_base_url
        )

    def _get(self, path: str, params: list[tuple[str, str]]) -> CachedPayload:
        return self.market.cache.get_or_fetch(
            SOURCE,
            _cache_key(path, params),
            WIKIRATE_MAX_AGE,
            lambda: self.client.get(path, params),
        )

    # ------------------------------------------------------------------ browse

    def search_metrics(self, q: str, limit: int = 20) -> list[wikirate.OpenMetric]:
        return wikirate.parse_metrics(self._get(*wikirate.metrics_query(q, limit)).payload)

    def search_companies(self, q: str, limit: int = 10) -> list[wikirate.OpenCompany]:
        return wikirate.parse_companies(
            self._get(*wikirate.companies_by_name_query(q, limit)).payload
        )

    def metric(self, metric_id: int) -> wikirate.OpenMetric:
        return wikirate.parse_metric(self._get(wikirate.metric_path(metric_id), []).payload)

    def company_name(self, company_id: int) -> str:
        payload = self._get(f"/~{company_id}.json", []).payload
        try:
            return str(json.loads(payload)["name"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DataProviderError("Unexpected company format from WikiRate.") from exc

    # ------------------------------------------------------------------ preview

    def _check_dataset(self, info: DatasetInfo) -> None:
        if info.id == demo.DATASET_ID or info.provenance.is_synthetic:
            raise InvalidInputError(
                "The demo assets are fictional, so real companies' ESG data cannot be matched "
                "to them. Upload your own price data (with ISINs) to use open ESG data."
            )
        if info.id in kenfrench.DATASETS:
            raise InvalidInputError(
                "Industry portfolios are not companies; company-level ESG data does not apply."
            )

    def _companies_by_isin(self, isins: list[str]) -> dict[str, wikirate.OpenCompany]:
        found: dict[str, wikirate.OpenCompany] = {}
        for i in range(0, len(isins), ISIN_CHUNK):
            chunk = isins[i : i + ISIN_CHUNK]
            for c in wikirate.parse_companies(
                self._get(*wikirate.companies_by_isin_query(chunk)).payload
            ):
                for isin in chunk:
                    if isin in c.isins:
                        found[isin] = c
        return found

    def _answers(
        self, metric_id: int, company_ids: list[int]
    ) -> dict[str, list[wikirate.OpenAnswer]]:
        by_company: dict[str, list[wikirate.OpenAnswer]] = {}
        for i in range(0, len(company_ids), COMPANY_CHUNK):
            chunk = company_ids[i : i + COMPANY_CHUNK]
            for page in range(wikirate.MAX_PAGES):
                answers, nxt = wikirate.parse_answers(
                    self._get(
                        *wikirate.answers_query(metric_id, chunk, page * wikirate.PAGE)
                    ).payload
                )
                for a in answers:
                    by_company.setdefault(a.company, []).append(a)
                if not nxt or len(answers) < wikirate.PAGE:
                    break
        return by_company

    def preview(self, req: s.OverlayPreviewRequest) -> s.OverlayPreviewOut:
        info, _ = self.market.get_dataset(req.dataset_id)
        self._check_dataset(info)
        metric = self.metric(req.metric_id)
        if not metric.numeric:
            raise InvalidInputError(
                f"“{metric.title}” is a {metric.value_type or 'non-numeric'} metric; only numeric "
                "metrics (numbers, money, scores) can be turned into ESG scores."
            )
        t = req.transform
        if t.method == "linear" and (t.lower is None or t.upper is None):
            bounds = parse_range(metric.range)
            if bounds is None:
                raise InvalidInputError(
                    "A linear scale needs the raw values that map to 0 and 100; set lower "
                    "and upper, or use percentile ranks."
                )
            t = t.model_copy(update={"lower": bounds[0], "upper": bounds[1]})
        assets = [info.asset(x) or AssetInfo(ticker=x, name=x) for x in req.tickers]
        unknown_overrides = [x for x in req.company_overrides if x not in req.tickers]
        if unknown_overrides:
            raise InvalidInputError(
                f"Company overrides for assets not selected: {', '.join(unknown_overrides)}."
            )

        # 1. companies
        company: dict[str, tuple[int, str, str]] = {}  # ticker -> (id, name, matched_by)
        for x, cid in req.company_overrides.items():
            company[x] = (cid, self.company_name(cid), "user")
        isins = sorted({a.isin for a in assets if a.isin and a.ticker not in company})
        by_isin = self._companies_by_isin(isins) if isins else {}
        for a in assets:
            if a.ticker not in company and a.isin and a.isin in by_isin:
                c = by_isin[a.isin]
                company[a.ticker] = (c.id, c.name, "isin")

        # 2. answers
        ids = sorted({cid for cid, _, _ in company.values()})
        answers = self._answers(metric.id, ids) if ids else {}

        rows: list[dict[str, object]] = []
        for a in assets:
            row: dict[str, object] = {
                "ticker": a.ticker,
                "asset_name": a.name,
                "isin": a.isin,
                "company": None,
                "company_id": None,
                "matched_by": None,
                "year": None,
                "raw_value": None,
                "score": None,
                "answer_url": None,
            }
            if a.ticker not in company:
                row["status"] = "no_company"
                row["note"] = (
                    "No WikiRate company has this ISIN; choose the company manually."
                    if a.isin
                    else "No ISIN in the dataset metadata; choose the company manually."
                )
                rows.append(row)
                continue
            cid, cname, how = company[a.ticker]
            row.update(company=cname, company_id=cid, matched_by=how)
            cands = [x for x in answers.get(cname, []) if req.year is None or x.year <= req.year]
            if not cands:
                row["status"] = "no_answer"
                row["note"] = f"{cname} has no answer for this metric" + (
                    f" up to {req.year}." if req.year else "."
                )
                rows.append(row)
                continue
            best = max(cands, key=lambda x: x.year)
            row.update(year=best.year, answer_url=best.url or None)
            value = wikirate.parse_number(best.value)
            if value is None:
                row["status"] = "not_numeric"
                row["note"] = f"The {best.year} answer is “{best.value}”, not a number."
            else:
                row["raw_value"] = value
                row["status"] = "scored"
                row["note"] = f"{best.year} answer" + (f" ({metric.unit})" if metric.unit else "")
            rows.append(row)

        # 3. scores
        warnings: list[str] = []
        scored = [r for r in rows if r["status"] == "scored"]
        if scored:
            raw = np.array([float(r["raw_value"]) for r in scored])  # type: ignore[arg-type]
            if t.method == "linear":
                scores = scale_linear(raw, t.lower or 0.0, t.upper or 0.0, t.higher_is_better)
            elif len(scored) >= 2:
                scores = percentile_scores(raw, t.higher_is_better)
            else:
                scores = None
                warnings.append(
                    "Only one company has a value, so percentile ranks are undefined; match more "
                    "companies or use a fixed linear scale."
                )
            if scores is not None:
                for r, sc in zip(scored, scores, strict=True):
                    r["score"] = round(float(sc), 4)
        entries = [s.OverlayEntryOut.model_validate(r) for r in rows]
        return s.OverlayPreviewOut(
            metric=metric_out(metric),
            transform=t,
            year=req.year,
            entries=entries,
            scored=sum(1 for e in entries if e.score is not None),
            warnings=warnings,
            license=wikirate.LICENSE,
            attribution=attribution(metric),
        )

    def composite_preview(self, req: s.CompositePreviewRequest) -> s.CompositePreviewOut:
        """Score every metric separately, then take the weighted average per asset.

        An asset gets a composite score only with a score for every metric; otherwise its
        parts are shown with the reason (never averaged over the metrics it happens to
        have, which would impute the missing ones).
        """
        parts = [
            self.preview(
                s.OverlayPreviewRequest(
                    dataset_id=req.dataset_id,
                    tickers=req.tickers,
                    metric_id=c.metric_id,
                    year=c.year,
                    transform=c.transform,
                    company_overrides=req.company_overrides,
                )
            )
            for c in req.components
        ]
        weights = np.array([c.weight for c in req.components])
        matrix = np.array(
            [[np.nan if e.score is None else e.score for e in p.entries] for p in parts]
        ).T  # assets x metrics
        combined = composite_scores(matrix, weights)
        entries: list[s.OverlayEntryOut] = []
        for i, base in enumerate(parts[0].entries):
            own = [p.entries[i] for p in parts]
            part_out = [
                s.CompositePartOut(
                    metric_id=p.metric.id,
                    metric_title=p.metric.title,
                    year=e.year,
                    raw_value=e.raw_value,
                    score=e.score,
                    answer_url=e.answer_url,
                    status=e.status,
                )
                for p, e in zip(parts, own, strict=True)
            ]
            score = None if np.isnan(combined[i]) else round(float(combined[i]), 4)
            missing = [pt.metric_title for pt in part_out if pt.score is None]
            if base.status == "no_company":
                status, note = "no_company", base.note
            elif score is not None:
                status, note = "scored", f"Weighted average of {len(parts)} metric scores."
            else:
                status = "incomplete"
                note = (
                    f"Scored on {len(parts) - len(missing)} of {len(parts)} metrics; a composite "
                    f"needs all of them. Missing: {', '.join(missing)}."
                )
            years = [pt.year for pt in part_out if pt.score is not None and pt.year is not None]
            entries.append(
                base.model_copy(
                    update={
                        "year": max(years) if years else None,
                        "raw_value": None,
                        "score": score,
                        "answer_url": None,
                        "status": status,
                        "note": note,
                        "parts": part_out,
                    }
                )
            )
        norm = weights / weights.sum()
        warnings = [f"{p.metric.title}: {w}" for p in parts for w in p.warnings]
        return s.CompositePreviewOut(
            components=[
                s.CompositeComponentOut(
                    metric=p.metric,
                    weight=float(wt),
                    year=c.year,
                    transform=p.transform,
                    scored=p.scored,
                )
                for p, c, wt in zip(parts, req.components, norm, strict=True)
            ],
            entries=entries,
            scored=sum(1 for e in entries if e.score is not None),
            warnings=warnings,
            license=wikirate.LICENSE,
            attribution=composite_attribution([p.metric for p in parts]),
        )

    # ------------------------------------------------------------------ saved overlays

    def _owner(self) -> tuple[Principal, Session]:
        p, session = self.market.principal, self.market.session
        if p is None or session is None:
            raise NotFoundError("Sign in to save ESG overlays.")
        return p, session

    def _room(self, principal: Principal, session: Session) -> None:
        n = session.scalar(
            select(func.count())
            .select_from(EsgOverlay)
            .where(EsgOverlay.owner_id == principal.user_id)
        )
        if (n or 0) >= MAX_OVERLAYS_PER_USER:
            raise InvalidInputError(
                f"You can save at most {MAX_OVERLAYS_PER_USER} ESG overlays; delete one first."
            )

    def save(self, name: str, req: s.OverlayPreviewRequest) -> s.OverlayOut:
        principal, session = self._owner()
        self._room(principal, session)
        preview = self.preview(req)  # recomputed server-side: never trust client scores
        if preview.scored == 0:
            raise InvalidInputError("None of the assets received a score; nothing to save.")
        uid = principal.user_id
        if session.get(User, uid) is None:
            session.add(User(id=uid, email=principal.email))
        row = EsgOverlay(
            owner_id=uid,
            name=name.strip(),
            dataset_id=req.dataset_id,
            source=SOURCE,
            spec={
                "metric": preview.metric.model_dump(mode="json"),
                "transform": preview.transform.model_dump(mode="json"),
                "year": req.year,
                "company_overrides": req.company_overrides,
                "attribution": preview.attribution,
            },
            entries=[e.model_dump(mode="json") for e in preview.entries],
            license=preview.license,
        )
        session.add(row)
        session.commit()
        return overlay_out(row)

    def save_composite(self, name: str, req: s.CompositePreviewRequest) -> s.OverlayOut:
        principal, session = self._owner()
        self._room(principal, session)
        preview = self.composite_preview(req)  # recomputed server-side
        if preview.scored == 0:
            raise InvalidInputError(
                "No asset has a score for every metric, so no composite score exists; "
                "nothing to save."
            )
        uid = principal.user_id
        if session.get(User, uid) is None:
            session.add(User(id=uid, email=principal.email))
        row = EsgOverlay(
            owner_id=uid,
            name=name.strip(),
            dataset_id=req.dataset_id,
            source=SOURCE,
            spec={
                "kind": "composite",
                "components": [c.model_dump(mode="json") for c in preview.components],
                "company_overrides": req.company_overrides,
                "attribution": preview.attribution,
            },
            entries=[e.model_dump(mode="json") for e in preview.entries],
            license=preview.license,
        )
        session.add(row)
        session.commit()
        return overlay_out(row)

    def list(self) -> list[s.OverlaySummaryOut]:
        principal, session = self._owner()
        rows = session.scalars(
            select(EsgOverlay)
            .where(EsgOverlay.owner_id == principal.user_id)
            .order_by(EsgOverlay.created_at.desc())
        ).all()
        return [
            s.OverlaySummaryOut(
                id=str(r.id),
                name=r.name,
                dataset_id=r.dataset_id,
                metric_title=overlay_title(r),
                scored=sum(1 for e in r.entries if e.get("score") is not None),
                total=len(r.entries),
                created_at=r.created_at,
            )
            for r in rows
        ]

    def delete(self, overlay_id: str) -> None:
        _, session = self._owner()
        session.delete(get_overlay(self.market, overlay_id))
        session.commit()


def get_overlay(market: MarketDataService, overlay_id: str) -> EsgOverlay:
    try:
        oid = uuid.UUID(overlay_id)
    except ValueError as exc:
        raise NotFoundError("ESG overlay not found.") from exc
    if market.principal is None or market.session is None:
        raise NotFoundError("Sign in to use saved ESG overlays.")
    row = market.session.get(EsgOverlay, oid)
    if row is None or row.owner_id != market.principal.user_id:
        raise NotFoundError("ESG overlay not found.")
    return row


def is_composite(r: EsgOverlay) -> bool:
    return r.spec.get("kind") == "composite"


def overlay_title(r: EsgOverlay) -> str:
    if not is_composite(r):
        return str(r.spec["metric"]["title"])
    titles = ", ".join(str(c["metric"]["title"]) for c in r.spec["components"])
    return f"Composite: {titles}"[:200]


def overlay_out(r: EsgOverlay) -> s.OverlayOut:
    entries = [s.OverlayEntryOut.model_validate(e) for e in r.entries]
    composite = is_composite(r)
    return s.OverlayOut(
        id=str(r.id),
        name=r.name,
        dataset_id=r.dataset_id,
        source=r.source,
        metric=None if composite else s.OpenMetricOut.model_validate(r.spec["metric"]),
        transform=None if composite else s.EsgTransformIn.model_validate(r.spec["transform"]),
        components=(
            [s.CompositeComponentOut.model_validate(c) for c in r.spec["components"]]
            if composite
            else None
        ),
        year=r.spec.get("year"),
        entries=entries,
        scored=sum(1 for e in entries if e.score is not None),
        license=r.license,
        attribution=str(r.spec.get("attribution", "")),
        created_at=r.created_at,
    )


def overlay_assets(
    info: DatasetInfo, tickers: Sequence[str], r: EsgOverlay
) -> tuple[AssetInfo, ...]:
    """The dataset's assets with ESG scores taken only from the overlay.

    Assets the overlay does not score have no ESG score (never imputed, and never mixed
    with scores from another source).
    """
    by_ticker = {e["ticker"]: e for e in r.entries}
    names = set(tickers) | {a.ticker for a in info.assets}
    out = []
    for t in sorted(names, key=lambda x: (x not in tickers, x)):
        a = info.asset(t) or AssetInfo(ticker=t, name=t)
        e = by_ticker.get(t)
        esg = None
        if e and e.get("score") is not None:
            year = int(e["year"])
            esg = EsgRecord(
                score=float(e["score"]), source=_score_source(r, e), as_of=dt.date(year, 12, 31)
            )
        out.append(replace(a, esg=esg))
    return tuple(out)


def _score_source(r: EsgOverlay, e: dict[str, Any]) -> str:
    """Provenance of one asset's overlay score, as shown next to the score."""
    if not is_composite(r):
        metric = r.spec["metric"]
        method = describe_transform(s.EsgTransformIn.model_validate(r.spec["transform"]))
        return (
            f"WikiRate (CC BY 4.0): {metric['designer']}, {metric['title']}, {e['year']} "
            f"answer for {e['company']}; {method}"
        )
    comps = {int(c["metric"]["id"]): c for c in r.spec["components"]}
    pieces = []
    for p in e.get("parts") or []:
        c = comps[int(p["metric_id"])]
        method = describe_transform(s.EsgTransformIn.model_validate(c["transform"]))
        pieces.append(
            f"{p['metric_title']} ({float(c['weight']):.0%} weight, {p['year']} answer, "
            f"score {float(p['score']):.0f}; {method})"
        )
    return f"WikiRate (CC BY 4.0) composite for {e['company']}, weighted average of: " + "; ".join(
        pieces
    )
