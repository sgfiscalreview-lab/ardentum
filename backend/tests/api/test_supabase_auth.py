"""Production auth path: Supabase-issued JWTs (asymmetric via JWKS, or legacy HS256)."""

import datetime as dt
import uuid
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from ardentum.api import auth
from ardentum.config import AuthMode, Environment, Settings

URL = "https://project.supabase.co"
ISS = URL + "/auth/v1"


@pytest.fixture
def keypair(monkeypatch: pytest.MonkeyPatch) -> ec.EllipticCurvePrivateKey:
    key = ec.generate_private_key(ec.SECP256R1())

    class FakeJwks:
        def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
            return SimpleNamespace(key=key.public_key())

    monkeypatch.setattr(auth, "_jwks_client", lambda url: FakeJwks())
    return key


def _settings(**kw: object) -> Settings:
    base: dict[str, object] = {
        "env": Environment.TEST,
        "auth_mode": AuthMode.SUPABASE,
        "supabase_url": URL,
        "database_url": "sqlite://",
    }
    base.update(kw)
    return Settings(**base)  # type: ignore[arg-type]


def _claims(**kw: object) -> dict[str, object]:
    now = dt.datetime.now(dt.UTC)
    c: dict[str, object] = {
        "sub": str(uuid.uuid4()),
        "email": "u@example.com",
        "aud": "authenticated",
        "iss": ISS,
        "exp": int((now + dt.timedelta(hours=1)).timestamp()),
        "role": "authenticated",
    }
    c.update(kw)
    return c


def test_es256_token_accepted(keypair: ec.EllipticCurvePrivateKey) -> None:
    claims = _claims()
    token = jwt.encode(claims, keypair, algorithm="ES256")
    p = auth.verify_token(_settings(), token)
    assert str(p.user_id) == claims["sub"]
    assert p.email == "u@example.com"


@pytest.mark.parametrize(
    "override",
    [{"iss": "https://evil.example/auth/v1"}, {"aud": "anon"}, {"sub": "not-a-uuid"}],
)
def test_bad_claims_rejected(
    keypair: ec.EllipticCurvePrivateKey, override: dict[str, object]
) -> None:
    token = jwt.encode(_claims(**override), keypair, algorithm="ES256")
    with pytest.raises(auth.AuthError):
        auth.verify_token(_settings(), token)


def test_wrong_key_rejected(keypair: ec.EllipticCurvePrivateKey) -> None:
    other = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode(_claims(), other, algorithm="ES256")
    with pytest.raises(auth.AuthError):
        auth.verify_token(_settings(), token)


def test_legacy_hs256() -> None:
    secret = "super-secret-jwt-token-with-at-least-32-characters-long"
    token = jwt.encode(_claims(), secret, algorithm="HS256")
    assert auth.verify_token(_settings(supabase_jwt_secret=secret), token)
    with pytest.raises(auth.AuthError, match="HS256"):
        auth.verify_token(_settings(), token)


def test_dev_tokens_rejected_in_supabase_mode() -> None:
    dev = Settings(env=Environment.TEST, database_url="sqlite://")
    token, _ = auth.issue_dev_token(dev, "a@b.co")
    with pytest.raises(auth.AuthError):
        auth.verify_token(_settings(), token)
    with pytest.raises(auth.AuthError, match="disabled"):
        auth.issue_dev_token(_settings(), "a@b.co")


def test_production_settings_are_guarded() -> None:
    with pytest.raises(ValueError, match="supabase"):
        Settings(env=Environment.PRODUCTION, auth_mode=AuthMode.DEV, database_url="postgresql://x")
    with pytest.raises(ValueError, match="PostgreSQL"):
        Settings(
            env=Environment.PRODUCTION,
            auth_mode=AuthMode.SUPABASE,
            supabase_url=URL,
            database_url="sqlite://",
        )
    ok = Settings(
        env=Environment.PRODUCTION,
        auth_mode=AuthMode.SUPABASE,
        supabase_url=URL,
        database_url="postgresql://u@h/db",
    )
    assert ok.env is Environment.PRODUCTION
