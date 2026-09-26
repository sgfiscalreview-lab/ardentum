from __future__ import annotations

from fastapi import APIRouter

from ardentum.api import schemas as s
from ardentum.api.auth import issue_dev_token, verify_token
from ardentum.api.deps import DbDep, RequiredPrincipal, SettingsDep
from ardentum.services.account import delete_account, export_account

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/dev-login", response_model=s.TokenOut)
def dev_login(body: s.DevLoginRequest, settings: SettingsDep) -> s.TokenOut:
    """Development-only sign-in. Disabled unless ARDENTUM_AUTH_MODE=dev (never in production)."""
    token, exp = issue_dev_token(settings, body.email)
    principal = verify_token(settings, token)
    return s.TokenOut(
        access_token=token, expires_at=exp, user_id=str(principal.user_id), email=body.email.lower()
    )


@router.get("/me", response_model=s.MeOut)
def me(principal: RequiredPrincipal) -> s.MeOut:
    return s.MeOut(user_id=str(principal.user_id), email=principal.email)


@router.get("/me/export", response_model=s.AccountExportOut)
def export_me(principal: RequiredPrincipal, db: DbDep) -> s.AccountExportOut:
    """Everything Ardentum stores about the signed-in user, as JSON."""
    return export_account(db, principal)


@router.delete("/me", response_model=s.AccountDeletedOut)
def delete_me(
    principal: RequiredPrincipal, db: DbDep, settings: SettingsDep
) -> s.AccountDeletedOut:
    """Permanently delete the user's portfolios, datasets, ESG overlays, jobs and profile."""
    return delete_account(settings, db, principal)
