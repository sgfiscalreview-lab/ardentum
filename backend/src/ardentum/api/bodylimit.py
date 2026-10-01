"""Request body size limits.

The server accepts request bodies of any size and the free API host has 512 MB of
memory, so every body is capped: dataset uploads (two CSV files) at twice the upload
limit plus room for the form fields, everything else at 1 MB, far above any real
request. A declared Content-Length over the cap is refused before anything is read; a
body sent without one is counted as it arrives and refused once it passes the cap.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

JSON_BODY_LIMIT = 1024 * 1024
FORM_OVERHEAD = 64 * 1024


def too_large_message(limit: int) -> str:
    size = f"{limit // (1024 * 1024)} MB" if limit >= 1024 * 1024 else f"{limit // 1024} KB"
    return f"The request is too large (at most {size}); send less data."


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, limit_for: Callable[[str, str], int]) -> None:
        self.app = app
        self.limit_for = limit_for

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.limit_for(scope["method"], scope["path"])
        declared = _content_length(scope)
        if declared is not None and declared > limit:
            body = {
                "error": {
                    "type": "payload_too_large",
                    "message": too_large_message(limit),
                    "details": None,
                }
            }
            await JSONResponse(body, status_code=413)(scope, receive, send)
            return
        received = 0

        async def _receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # Raised while the endpoint reads its body; errors.py answers it in the
                    # usual error format.
                    raise HTTPException(413, too_large_message(limit))
            return message

        await self.app(scope, _receive, send)


def _content_length(scope: Scope) -> int | None:
    for name, value in scope["headers"]:
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None
