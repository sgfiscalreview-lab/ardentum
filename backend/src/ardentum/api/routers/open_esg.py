"""Open ESG data: browse WikiRate metrics and companies, build and save score overlays."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from ardentum.api import schemas as s
from ardentum.api.deps import MarketService, RequiredPrincipal
from ardentum.services.open_esg import OpenEsgService, get_overlay, metric_out, overlay_out

router = APIRouter(prefix="/esg", tags=["open ESG data"])


@router.get("/open/metrics", response_model=list[s.OpenMetricOut])
def search_metrics(
    service: MarketService,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[s.OpenMetricOut]:
    """Search WikiRate metrics by name (CC BY 4.0 open data)."""
    return [metric_out(m) for m in OpenEsgService(service).search_metrics(q, limit)]


@router.get("/open/companies", response_model=list[s.OpenCompanyOut])
def search_companies(
    service: MarketService,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
) -> list[s.OpenCompanyOut]:
    """Search WikiRate companies by name, to confirm matches for assets without an ISIN."""
    return [
        s.OpenCompanyOut(
            id=c.id, name=c.name, headquarters=c.headquarters, isins=list(c.isins[:5]), url=c.url
        )
        for c in OpenEsgService(service).search_companies(q, limit)
    ]


@router.post("/open/preview", response_model=s.OverlayPreviewOut)
def preview_overlay(req: s.OverlayPreviewRequest, service: MarketService) -> s.OverlayPreviewOut:
    """Match assets to companies, fetch answers and compute 0-100 scores (not saved)."""
    return OpenEsgService(service).preview(req)


@router.post("/overlays", response_model=s.OverlayOut, status_code=status.HTTP_201_CREATED)
def save_overlay(
    body: s.OverlaySaveIn, service: MarketService, _user: RequiredPrincipal
) -> s.OverlayOut:
    """Recompute the preview on the server and save it for use in analyses."""
    return OpenEsgService(service).save(body.name, body.preview)


@router.get("/overlays", response_model=list[s.OverlaySummaryOut])
def list_overlays(service: MarketService, _user: RequiredPrincipal) -> list[s.OverlaySummaryOut]:
    return OpenEsgService(service).list()


@router.get("/overlays/{overlay_id}", response_model=s.OverlayOut)
def get_overlay_detail(
    overlay_id: str, service: MarketService, _user: RequiredPrincipal
) -> s.OverlayOut:
    return overlay_out(get_overlay(service, overlay_id))


@router.delete("/overlays/{overlay_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_overlay(overlay_id: str, service: MarketService, _user: RequiredPrincipal) -> None:
    OpenEsgService(service).delete(overlay_id)
