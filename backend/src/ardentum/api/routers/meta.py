from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from ardentum import __version__
from ardentum.api import schemas as s
from ardentum.api.deps import DbDep, SettingsDep

router = APIRouter(tags=["meta"])
METHODOLOGY_VERSION = "2026.1"


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def health_db(db: DbDep) -> dict[str, str]:
    """Touches the database; a daily ping keeps free-tier databases from pausing."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


@router.get("/meta", response_model=s.MetaOut)
def meta(settings: SettingsDep) -> s.MetaOut:
    return s.MetaOut(
        version=__version__,
        environment=settings.env.value,
        auth_mode=settings.auth_mode.value,
        supabase_url=settings.supabase_url,
        live_data_available=bool(settings.tiingo_api_key),
        methodology_version=METHODOLOGY_VERSION,
    )
