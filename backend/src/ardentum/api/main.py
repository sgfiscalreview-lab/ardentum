"""FastAPI application factory.

Run with ``uvicorn ardentum.api.main:create_app --factory``.
"""

from __future__ import annotations

import logging
import secrets
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import sessionmaker
from starlette.concurrency import run_in_threadpool

from ardentum import __version__
from ardentum.api import errors
from ardentum.api.auth import AuthError, verify_token
from ardentum.api.ratelimit import (
    COMPUTE_PATHS,
    DatabaseRateLimiter,
    Limiter,
    RateLimiter,
    address_key,
    client_ip,
)
from ardentum.api.routers import analysis, auth, datasets, jobs, meta, open_esg, portfolios
from ardentum.config import Environment, Settings, get_settings
from ardentum.db.models import Base
from ardentum.db.session import make_engine

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("ardentum.request")
    app = FastAPI(
        title="Ardentum API",
        version=__version__,
        description="Quantitative portfolio analysis: optimisation, simulation, backtesting and ESG.",
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(GZipMiddleware, minimum_size=2048)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    engine = make_engine(settings.database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    limiter: Limiter | None = None
    if settings.compute_rate_limit > 0:
        store = settings.rate_limit_store
        if store == "auto":
            store = "memory" if settings.database_url.startswith("sqlite") else "database"
        limiter = (
            DatabaseRateLimiter(factory, settings.compute_rate_limit)
            if store == "database"
            else RateLimiter(settings.compute_rate_limit, 60.0)
        )

    address_secret = (
        settings.rate_limit_secret.encode()
        if settings.rate_limit_secret
        else secrets.token_bytes(32)
    )

    def _client_key(request: Request) -> str:
        auth = request.headers.get("authorization", "")
        scheme, _, token = auth.partition(" ")
        if scheme.lower() == "bearer" and token:
            try:
                return f"u:{verify_token(settings, token.strip()).user_id}"
            except AuthError:
                pass  # invalid tokens are rejected later; limit them by address
        peer = request.client.host if request.client else None
        ip = client_ip(request.headers.get("x-forwarded-for"), peer, settings.trusted_proxy_hops)
        return address_key(ip, address_secret)

    @app.middleware("http")
    async def _rate_limit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if (
            limiter is not None
            and request.method == "POST"
            and (path in COMPUTE_PATHS or path.startswith("/api/v1/jobs"))
        ):
            key = await run_in_threadpool(_client_key, request)
            wait = await run_in_threadpool(limiter.check, key)
            if wait is not None:
                return JSONResponse(
                    {
                        "error": {
                            "type": "rate_limited",
                            "message": f"Too many calculations; try again in {int(wait) + 1} s.",
                            "details": None,
                        }
                    },
                    status_code=429,
                    headers={"Retry-After": str(int(wait) + 1)},
                )
        return await call_next(request)

    @app.middleware("http")
    async def _context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.request_id = rid
        start = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith(API_PREFIX) and "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        log.info(
            "%s %s %d %.0fms rid=%s",
            request.method,
            request.url.path,
            response.status_code,
            ms,
            rid,
        )
        return response

    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = factory

    errors.install(app)
    for r in (
        meta.router,
        auth.router,
        datasets.router,
        analysis.router,
        portfolios.router,
        jobs.router,
        open_esg.router,
    ):
        app.include_router(r, prefix=API_PREFIX)

    if settings.env is not Environment.PRODUCTION and settings.database_url.startswith("sqlite"):
        # Local convenience only; PostgreSQL deployments are migrated with Alembic.
        Base.metadata.create_all(engine)
    return app
