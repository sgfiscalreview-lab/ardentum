"""FastAPI dependencies: settings, database session, authentication, services."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from ardentum.api.auth import AuthError, Principal, verify_token
from ardentum.config import Settings
from ardentum.db.models import User
from ardentum.services.market_data import MarketDataService


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_db(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.sessionmaker()
    try:
        yield session
    finally:
        session.close()


DbDep = Annotated[Session, Depends(get_db)]


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthError("Authorization header must be 'Bearer <token>'.")
    return token.strip()


def optional_principal(
    settings: SettingsDep, authorization: Annotated[str | None, Header()] = None
) -> Principal | None:
    token = _bearer(authorization)
    return None if token is None else verify_token(settings, token)


OptionalPrincipal = Annotated[Principal | None, Depends(optional_principal)]


def require_principal(principal: OptionalPrincipal, db: DbDep) -> Principal:
    if principal is None:
        raise AuthError("Sign in to use this feature.")
    user = db.get(User, principal.user_id)
    if user is None:
        db.add(User(id=principal.user_id, email=principal.email))
        db.commit()
    elif principal.email and user.email != principal.email:
        user.email = principal.email
        db.commit()
    return principal


RequiredPrincipal = Annotated[Principal, Depends(require_principal)]


def market_service(
    settings: SettingsDep, db: DbDep, principal: OptionalPrincipal
) -> MarketDataService:
    return MarketDataService(settings, db, principal)


MarketService = Annotated[MarketDataService, Depends(market_service)]
