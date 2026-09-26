from __future__ import annotations

from fastapi import APIRouter

from ardentum.api import schemas as s
from ardentum.api.auth import issue_dev_token, verify_token
from ardentum.api.deps import RequiredPrincipal, SettingsDep

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
