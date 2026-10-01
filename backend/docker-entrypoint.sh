#!/bin/sh
set -e
# Apply database migrations (idempotent), then serve.
if [ "${ARDENTUM_SKIP_MIGRATIONS:-0}" != "1" ]; then
  alembic upgrade head
fi
# Client addresses: uvicorn trusts forwarded headers only from FORWARDED_ALLOW_IPS
# (default: localhost). Do not use "*": uvicorn would then take the left-most
# X-Forwarded-For entry, which clients can forge. Behind Cloud Run/Render, set
# ARDENTUM_TRUSTED_PROXY_HOPS=1 instead; the API then reads the proxy-appended entry.
# --no-server-header: answers do not name the server software. --no-access-log: the
# API logs each request itself, without the client's address (Privacy Policy).
exec uvicorn ardentum.api.main:create_app --factory --host 0.0.0.0 --port "${PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-127.0.0.1}" \
  --workers "${WEB_CONCURRENCY:-2}" --no-server-header --no-access-log
