from fastapi.testclient import TestClient

from ardentum.api.main import create_app
from ardentum.api.ratelimit import RateLimiter
from ardentum.config import Environment, Settings


def test_sliding_window() -> None:
    rl = RateLimiter(2, 10.0)
    assert rl.check("a", 0.0) is None
    assert rl.check("a", 1.0) is None
    wait = rl.check("a", 2.0)
    assert wait is not None
    assert abs(wait - 8.0) < 1e-9
    assert rl.check("b", 2.0) is None  # independent keys
    assert rl.check("a", 10.5) is None  # first hit expired


def test_compute_endpoints_are_limited() -> None:
    app = create_app(Settings(env=Environment.TEST, database_url="sqlite://", compute_rate_limit=2))
    with TestClient(app) as c:
        body = {"universe": {"dataset_id": "demo", "tickers": ["NWS.SYN", "GOVB.SYN"]}}
        assert c.post("/api/v1/analytics", json=body).status_code == 200
        assert c.post("/api/v1/analytics", json=body).status_code == 200
        r = c.post("/api/v1/analytics", json=body)
        assert r.status_code == 429
        assert r.json()["error"]["type"] == "rate_limited"
        assert "Retry-After" in r.headers
        assert c.get("/api/v1/health").status_code == 200  # non-compute unaffected
