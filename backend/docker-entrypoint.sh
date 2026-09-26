#!/bin/sh
set -e
# Apply database migrations (idempotent), then serve.
if [ "${ARDENTUM_SKIP_MIGRATIONS:-0}" != "1" ]; then
  alembic upgrade head
fi
exec uvicorn ardentum.api.main:create_app --factory --host 0.0.0.0 --port "${PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips="*" --workers "${WEB_CONCURRENCY:-2}"
