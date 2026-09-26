"""Mapping of domain exceptions to consistent JSON error responses.

Every error body has the shape ``{"error": {"type", "message", "details"}}``.
Messages from the quant engine are written for end users and are safe to show.
Unexpected exceptions never leak internals: they return a generic message and a
request id that correlates with the server log.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ardentum.api.auth import AuthError
from ardentum.data.errors import DataNotConfiguredError, DataProviderError
from ardentum.quant.errors import (
    InfeasibleProblemError,
    InsufficientDataError,
    InvalidInputError,
    QuantError,
    SolverError,
    UndefinedMetricError,
)
from ardentum.services.market_data import NotFoundError

log = logging.getLogger("ardentum.api")

_QUANT_TYPES: list[tuple[type[QuantError], str, int]] = [
    (DataNotConfiguredError, "not_configured", 503),
    (DataProviderError, "data_provider_error", 502),
    (InfeasibleProblemError, "infeasible", 422),
    (InsufficientDataError, "insufficient_data", 422),
    (UndefinedMetricError, "undefined_metric", 422),
    (InvalidInputError, "invalid_input", 422),
    (SolverError, "solver_error", 500),
]


def _body(kind: str, message: str, details: object = None) -> dict[str, object]:
    return {"error": {"type": kind, "message": message, "details": details}}


def install(app: FastAPI) -> None:
    @app.exception_handler(QuantError)
    async def _quant(request: Request, exc: QuantError) -> JSONResponse:
        for cls, kind, status in _QUANT_TYPES:
            if isinstance(exc, cls):
                if status >= 500:
                    log.warning("quant error %s on %s: %s", kind, request.url.path, exc)
                return JSONResponse(_body(kind, str(exc)), status_code=status)
        return JSONResponse(_body("quant_error", str(exc)), status_code=422)

    @app.exception_handler(AuthError)
    async def _auth(_request: Request, exc: AuthError) -> JSONResponse:
        return JSONResponse(
            _body("unauthorized", str(exc)), status_code=401, headers={"WWW-Authenticate": "Bearer"}
        )

    @app.exception_handler(NotFoundError)
    async def _nf(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(_body("not_found", str(exc)), status_code=404)

    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"loc": [str(p) for p in e.get("loc", ())], "message": e.get("msg", "")}
            for e in exc.errors()
        ]
        first = details[0] if details else {"loc": [], "message": "Invalid request."}
        where = ".".join(first["loc"][1:]) if len(first["loc"]) > 1 else ""
        msg = f"{where}: {first['message']}" if where else str(first["message"])
        return JSONResponse(_body("validation_error", msg, details), status_code=422)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, _exc: Exception) -> JSONResponse:
        rid = getattr(request.state, "request_id", "unknown")
        log.exception("unhandled error on %s (request %s)", request.url.path, rid)
        return JSONResponse(
            _body(
                "internal_error",
                f"An unexpected error occurred (reference {rid}).",
                {"request_id": rid},
            ),
            status_code=500,
        )
