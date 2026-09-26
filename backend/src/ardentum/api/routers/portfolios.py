from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Literal

from fastapi import APIRouter, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select

from ardentum.api import schemas as s
from ardentum.api.deps import DbDep, RequiredPrincipal
from ardentum.db.models import Portfolio
from ardentum.quant.errors import InvalidInputError
from ardentum.services.market_data import NotFoundError

router = APIRouter(prefix="/portfolios", tags=["portfolios"])
MAX_PORTFOLIOS_PER_USER = 200


def _out(p: Portfolio) -> s.PortfolioOut:
    return s.PortfolioOut(
        id=str(p.id),
        name=p.name,
        description=p.description,
        dataset_id=p.dataset_id,
        weights=p.weights,
        spec=p.spec,
        summary=p.summary,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _get(db: DbDep, principal: RequiredPrincipal, portfolio_id: str) -> Portfolio:
    try:
        uid = uuid.UUID(portfolio_id)
    except ValueError as exc:
        raise NotFoundError("Portfolio not found.") from exc
    row = db.get(Portfolio, uid)
    if row is None or row.owner_id != principal.user_id:
        raise NotFoundError("Portfolio not found.")
    return row


@router.get("", response_model=list[s.PortfolioOut])
def list_portfolios(principal: RequiredPrincipal, db: DbDep) -> list[s.PortfolioOut]:
    rows = db.scalars(
        select(Portfolio)
        .where(Portfolio.owner_id == principal.user_id)
        .order_by(Portfolio.updated_at.desc())
    ).all()
    return [_out(r) for r in rows]


@router.post("", response_model=s.PortfolioOut, status_code=status.HTTP_201_CREATED)
def create_portfolio(
    body: s.PortfolioIn, principal: RequiredPrincipal, db: DbDep
) -> s.PortfolioOut:
    n = db.scalar(
        select(func.count()).select_from(Portfolio).where(Portfolio.owner_id == principal.user_id)
    )
    if (n or 0) >= MAX_PORTFOLIOS_PER_USER:
        raise InvalidInputError(f"You can save at most {MAX_PORTFOLIOS_PER_USER} portfolios.")
    row = Portfolio(owner_id=principal.user_id, **_fields(body))
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)


def _fields(body: s.PortfolioIn) -> dict[str, object]:
    for blob in (body.spec, body.summary):
        if blob is not None and len(json.dumps(blob)) > 200_000:
            raise InvalidInputError("Saved specification or summary is too large.")
    return {
        "name": body.name.strip(),
        "description": body.description,
        "dataset_id": body.dataset_id,
        "weights": {k: float(v) for k, v in body.weights.items()},
        "spec": body.spec,
        "summary": body.summary,
    }


@router.get("/{portfolio_id}", response_model=s.PortfolioOut)
def get_portfolio(portfolio_id: str, principal: RequiredPrincipal, db: DbDep) -> s.PortfolioOut:
    return _out(_get(db, principal, portfolio_id))


@router.put("/{portfolio_id}", response_model=s.PortfolioOut)
def update_portfolio(
    portfolio_id: str, body: s.PortfolioIn, principal: RequiredPrincipal, db: DbDep
) -> s.PortfolioOut:
    row = _get(db, principal, portfolio_id)
    for k, v in _fields(body).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return _out(row)


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_portfolio(portfolio_id: str, principal: RequiredPrincipal, db: DbDep) -> None:
    row = _get(db, principal, portfolio_id)
    db.delete(row)
    db.commit()


@router.get("/{portfolio_id}/export")
def export_portfolio(
    portfolio_id: str,
    principal: RequiredPrincipal,
    db: DbDep,
    format: Literal["csv", "json"] = Query("csv"),
) -> Response:
    row = _get(db, principal, portfolio_id)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in row.name)[:60] or "portfolio"
    if format == "json":
        payload = _out(row).model_dump(mode="json")
        return Response(
            json.dumps(payload, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{safe}.json"'},
        )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ticker", "weight"])
    for t, v in sorted(row.weights.items(), key=lambda kv: -kv[1]):
        w.writerow([t, f"{v:.10f}"])
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{safe}.csv"'},
    )
