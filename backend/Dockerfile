# Ardentum API — production image
# Python matches requires-python in pyproject.toml and the version CI tests (3.12). uv
# must use this interpreter: with downloads off, a base image outside requires-python fails
# the build here, instead of uv fetching its own Python into /root, which the app's user
# below cannot run (the image then builds but never starts; see DECISIONS D-044).
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv
WORKDIR /app

# Dependencies first for layer caching.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini docker-entrypoint.sh ./
RUN uv sync --frozen --no-dev && chmod +x docker-entrypoint.sh \
    && useradd --create-home --uid 10001 ardentum
USER ardentum
ENV PATH="/app/.venv/bin:$PATH" PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/v1/health')"
ENTRYPOINT ["./docker-entrypoint.sh"]
