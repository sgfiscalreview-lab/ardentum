"""FastAPI application factory.

Run with ``uvicorn ardentum.api.main:create_app --factory``.
"""

from __future__ import annotations

import logging
import re
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
from ardentum.api.bodylimit import FORM_OVERHEAD, JSON_BODY_LIMIT, BodySizeLimitMiddleware
from ardentum.api.ratelimit import (
    DatabaseRateLimiter,
    Limiter,
    RateLimiter,
    address_key,
    budget_for,
    client_ip,
)
from ardentum.api.routers import analysis, auth, datasets, jobs, meta, open_esg, portfolios
from ardentum.config import Environment, Settings, get_settings
from ardentum.db.models import Base
from ardentum.db.session import make_engine
from ardentum.services import usage

API_PREFIX = "/api/v1"
# A caller-supplied request id is echoed and logged only if it looks like one.
_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


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
    # Middleware added first sits innermost. Unexpected errors become JSON 500s, and CORS
    # (added last) wraps everything, so browsers can read every answer, refusals included.
    app.add_middleware(errors.UnexpectedErrorMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=2048)
    upload_limit = 2 * settings.max_upload_bytes + FORM_OVERHEAD

    def _body_limit(method: str, path: str) -> int:
        return upload_limit if method == "POST" and path == "/api/v1/datasets" else JSON_BODY_LIMIT

    app.add_middleware(BodySizeLimitMiddleware, limit_for=_body_limit)

    engine = make_engine(settings.database_url, settings.env is Environment.PRODUCTION)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    store = settings.rate_limit_store
    if store == "auto":
        store = "memory" if settings.database_url.startswith("sqlite") else "database"
    limiters: dict[str, Limiter] = {}
    for budget, limit in (
        ("compute", settings.compute_rate_limit),
        ("write", settings.write_rate_limit),
    ):
        if limit > 0:
            limiters[budget] = (
                DatabaseRateLimiter(factory, limit)
                if store == "database"
                else RateLimiter(limit, 60.0)
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
        budget = budget_for(request.method, request.url.path)
        limiter = limiters.get(budget) if budget else None
        if budget and limiter is not None:
            key = await run_in_threadpool(_client_key, request)
            wait = await run_in_threadpool(limiter.check, f"{budget[0]}:{key}")
            if wait is not None:
                what = "calculations" if budget == "compute" else "requests"
                return JSONResponse(
                    {
                        "error": {
                            "type": "rate_limited",
                            "message": f"Too many {what}; try again in {int(wait) + 1} s.",
                            "details": None,
                        }
                    },
                    status_code=429,
                    headers={"Retry-After": str(int(wait) + 1)},
                )
        return await call_next(request)

    @app.middleware("http")
    async def _count_usage(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        event = usage.event_for(request.method, request.url.path)
        if (
            event is not None
            and 200 <= response.status_code < 300
            and usage.MONITOR_HEADER not in request.headers
        ):
            await run_in_threadpool(usage.record, factory, event)
        return response

    @app.middleware("http")
    async def _context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        given = request.headers.get("x-request-id", "")
        rid = given if _REQUEST_ID.fullmatch(given) else uuid.uuid4().hex[:16]
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Retry-After", "X-Request-ID"],
        max_age=600,
    )

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
