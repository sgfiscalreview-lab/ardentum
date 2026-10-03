"""Application settings loaded from environment variables (prefix ``ARDENTUM_``)."""

from __future__ import annotations

import json
from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class AuthMode(StrEnum):
    SUPABASE = "supabase"  # verify Supabase-issued JWTs (production)
    DEV = "dev"  # local development/testing only: backend-issued tokens


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARDENTUM_", env_file=".env", extra="ignore")

    env: Environment = Environment.DEVELOPMENT
    database_url: str = "sqlite:///./ardentum-dev.sqlite3"
    # A JSON list (["https://a", "https://b"]) or comma-separated addresses.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    # Optional regex for preview deployments, e.g. r"https://[a-z0-9-]+\.ardentum\.pages\.dev"
    cors_origin_regex: str | None = None

    auth_mode: AuthMode = AuthMode.DEV
    dev_jwt_secret: str = "dev-only-insecure-secret-change-me-0123456789"
    supabase_url: str | None = None
    supabase_jwt_secret: str | None = None  # legacy HS256 projects
    supabase_jwt_audience: str = "authenticated"
    # Optional: lets account deletion also remove the Supabase sign-in record.
    supabase_service_key: str | None = None

    tiingo_api_key: str | None = None
    fred_api_key: str | None = None
    wikirate_api_key: str | None = None  # free account at wikirate.org
    wikirate_base_url: str = "https://wikirate.org"
    kenfrench_base_url: str = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"

    max_upload_bytes: int = 5 * 1024 * 1024
    compute_rate_limit: int = 60  # compute requests per client per minute (0 disables)
    # Saves, uploads, deletions, sign-in and WikiRate lookups per client per minute.
    write_rate_limit: int = 60
    # "database" shares limits across instances (PostgreSQL); "auto" = database unless SQLite.
    rate_limit_store: Literal["auto", "memory", "database"] = "auto"
    # Proxies in front of the API that append to X-Forwarded-For (Cloud Run / Render: 1).
    # 0 uses the socket address and ignores the header, which clients can forge.
    trusted_proxy_hops: int = Field(0, ge=0, le=5)
    # Key for hashing client IP addresses in rate-limit counters, so raw addresses are never
    # stored. Instances that share the database need the same value; when unset, each
    # process draws a random key at start-up.
    rate_limit_secret: str | None = None
    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, v: Any) -> Any:
        """Accept JSON or comma-separated values; drop spaces and trailing slashes, which a
        browser's Origin header never has (a mismatch would block every request)."""
        if isinstance(v, str):
            text = v.strip()
            if text.startswith("["):
                try:
                    v = json.loads(text)
                except ValueError as exc:
                    raise ValueError(
                        "ARDENTUM_CORS_ORIGINS is not valid JSON; use "
                        '["https://your-site"] or plain comma-separated addresses.'
                    ) from exc
            else:
                v = text.split(",")
        if isinstance(v, list):
            return [o.strip().rstrip("/") for o in v if isinstance(o, str) and o.strip()]
        return v

    @model_validator(mode="after")
    def _production_safety(self) -> Settings:
        if self.env is Environment.PRODUCTION:
            if self.auth_mode is not AuthMode.SUPABASE:
                raise ValueError("Production requires ARDENTUM_AUTH_MODE=supabase.")
            if not self.supabase_url:
                raise ValueError("Production requires ARDENTUM_SUPABASE_URL.")
            if self.database_url.startswith("sqlite"):
                raise ValueError("Production requires a PostgreSQL ARDENTUM_DATABASE_URL.")
            if any(o == "*" for o in self.cors_origins):
                raise ValueError("Wildcard CORS origins are not allowed in production.")
        if self.auth_mode is AuthMode.DEV and len(self.dev_jwt_secret) < 32:
            raise ValueError("ARDENTUM_DEV_JWT_SECRET must be at least 32 characters.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
