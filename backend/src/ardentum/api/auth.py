"""Authentication: verification of bearer tokens.

Production (``auth_mode=supabase``): the frontend authenticates users with
Supabase Auth and sends the Supabase access token (a JWT) as
``Authorization: Bearer <token>``. The backend verifies the signature
(asymmetric keys via the project's JWKS endpoint, or the legacy HS256 project
secret), expiry, audience (``authenticated``) and issuer
(``<SUPABASE_URL>/auth/v1``). The backend never sees passwords.

Development/testing (``auth_mode=dev``): ``POST /api/v1/auth/dev-login`` issues
short-lived HS256 tokens for any email, so the full product can run locally
without external services. Settings validation forbids this mode in production.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from ardentum.config import AuthMode, Settings

DEV_ISSUER = "ardentum-dev"
DEV_TOKEN_TTL = dt.timedelta(hours=8)
_ALLOWED_ASYMMETRIC = ["ES256", "RS256", "EdDSA"]


class AuthError(Exception):
    """The request is not authenticated."""


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    email: str | None


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, lifespan=600)


def dev_user_id(email: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"ardentum-dev:{email.strip().lower()}")


def issue_dev_token(settings: Settings, email: str) -> tuple[str, dt.datetime]:
    if settings.auth_mode is not AuthMode.DEV:
        raise AuthError("Developer sign-in is disabled.")
    now = dt.datetime.now(dt.UTC)
    exp = now + DEV_TOKEN_TTL
    claims = {
        "sub": str(dev_user_id(email)),
        "email": email.strip().lower(),
        "aud": "authenticated",
        "iss": DEV_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(claims, settings.dev_jwt_secret, algorithm="HS256"), exp


def _principal(claims: dict[str, Any]) -> Principal:
    try:
        uid = uuid.UUID(str(claims["sub"]))
    except (KeyError, ValueError) as exc:
        raise AuthError("Token subject is not a valid user id.") from exc
    email = claims.get("email")
    return Principal(uid, str(email) if email else None)


def verify_token(settings: Settings, token: str) -> Principal:
    """Verify a bearer token according to the configured auth mode."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise AuthError("Malformed token.") from exc
    alg = header.get("alg")
    options: Any = {"require": ["exp", "sub", "aud"]}
    try:
        if settings.auth_mode is AuthMode.DEV:
            claims = jwt.decode(
                token,
                settings.dev_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                issuer=DEV_ISSUER,
                options=options,
            )
            return _principal(claims)

        if not settings.supabase_url:
            raise AuthError("Authentication is not configured.")
        issuer = settings.supabase_url.rstrip("/") + "/auth/v1"
        if alg == "HS256":
            if not settings.supabase_jwt_secret:
                raise AuthError("HS256 tokens are not accepted by this deployment.")
            key: Any = settings.supabase_jwt_secret
            algorithms = ["HS256"]
        elif alg in _ALLOWED_ASYMMETRIC:
            key = (
                _jwks_client(issuer + "/.well-known/jwks.json").get_signing_key_from_jwt(token).key
            )
            algorithms = [alg]
        else:
            raise AuthError("Unsupported token algorithm.")
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=settings.supabase_jwt_audience,
            issuer=issuer,
            options=options,
        )
        return _principal(claims)
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Session expired; please sign in again.") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid authentication token.") from exc
