"""Export and deletion of everything Ardentum stores about a user."""

from __future__ import annotations

import datetime as dt
import logging

import httpx
from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session

from ardentum.api import schemas as s
from ardentum.api.auth import Principal
from ardentum.config import AuthMode, Settings
from ardentum.db.models import Dataset, EsgOverlay, Job, Portfolio, RateLimitCounter, User

log = logging.getLogger("ardentum.account")


def export_account(session: Session, principal: Principal) -> s.AccountExportOut:
    uid = principal.user_id
    portfolios = session.scalars(select(Portfolio).where(Portfolio.owner_id == uid)).all()
    datasets = session.scalars(select(Dataset).where(Dataset.owner_id == uid)).all()
    overlays = session.scalars(select(EsgOverlay).where(EsgOverlay.owner_id == uid)).all()
    return s.AccountExportOut(
        exported_at=dt.datetime.now(dt.UTC),
        user_id=str(uid),
        email=principal.email,
        portfolios=[
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "dataset_id": p.dataset_id,
                "weights": p.weights,
                "spec": p.spec,
            }
            for p in portfolios
        ],
        datasets=[
            {
                "id": str(d.id),
                "name": d.name,
                "description": d.description,
                "source_filename": d.source_filename,
                "assets": d.assets,
                "start_date": d.start_date.isoformat() if d.start_date else None,
                "end_date": d.end_date.isoformat() if d.end_date else None,
            }
            for d in datasets
        ],
        esg_overlays=[
            {
                "id": str(o.id),
                "name": o.name,
                "dataset_id": o.dataset_id,
                "spec": o.spec,
                "entries": o.entries,
            }
            for o in overlays
        ],
    )


def _delete_identity(settings: Settings, principal: Principal) -> bool:
    """Remove the Supabase Auth user (needs the project's secret/service key)."""
    if settings.auth_mode is not AuthMode.SUPABASE or not settings.supabase_url:
        return False
    key = settings.supabase_service_key
    if not key:
        return False
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{principal.user_id}"
    try:
        resp = httpx.delete(
            url, headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=15
        )
    except httpx.HTTPError as exc:
        log.warning("could not delete Supabase user %s: %s", principal.user_id, exc)
        return False
    if resp.status_code in (200, 204, 404):
        return True
    log.warning("Supabase refused to delete user %s: HTTP %s", principal.user_id, resp.status_code)
    return False


def delete_account(
    settings: Settings, session: Session, principal: Principal
) -> s.AccountDeletedOut:
    uid = principal.user_id

    def count(stmt: Select[int]) -> int:
        return int(session.scalar(stmt) or 0)

    counts = {
        "portfolios": count(select(func.count(Portfolio.id)).where(Portfolio.owner_id == uid)),
        "datasets": count(select(func.count(Dataset.id)).where(Dataset.owner_id == uid)),
        "esg_overlays": count(select(func.count(EsgOverlay.id)).where(EsgOverlay.owner_id == uid)),
        "jobs": count(select(func.count(Job.id)).where(Job.owner_id == uid)),
    }
    session.execute(delete(Portfolio).where(Portfolio.owner_id == uid))
    session.execute(delete(Dataset).where(Dataset.owner_id == uid))
    session.execute(delete(EsgOverlay).where(EsgOverlay.owner_id == uid))
    session.execute(delete(Job).where(Job.owner_id == uid))
    session.execute(delete(RateLimitCounter).where(RateLimitCounter.key == f"u:{uid}"))
    session.execute(delete(User).where(User.id == uid))
    session.commit()
    identity = _delete_identity(settings, principal)
    message = (
        "Your Ardentum data and your sign-in record have been deleted."
        if identity
        else "Your Ardentum data has been deleted. Your sign-in record with the identity "
        "provider was not removed automatically; ask the operator to remove it, or simply "
        "stop using it."
    )
    return s.AccountDeletedOut(**counts, identity_deleted=identity, message=message)
