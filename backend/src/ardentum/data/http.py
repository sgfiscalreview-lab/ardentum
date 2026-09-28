"""One pooled HTTP client for outbound data requests.

Creating an ``httpx.Client`` per request (and never closing it) leaks sockets until
garbage collection and repeats the TLS handshake every time. Providers use this shared
client unless a test injects its own, and pass their own timeout per request.
"""

from __future__ import annotations

import functools

import httpx


@functools.cache
def shared_client() -> httpx.Client:
    return httpx.Client(follow_redirects=True, timeout=30.0)
