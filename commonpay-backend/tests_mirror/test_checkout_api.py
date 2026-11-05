import app.api.v1.payments as pay
from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.core.security import require_api_key

def test_checkout_forwards_idempotency_header(monkeypatch):
    seen = {}
    async def fake(**kw):
        seen.update(kw)
        return {"ok": True}
    monkeypatch.setattr(pay, "create_checkout", fake)
    fastapi_app.dependency_overrides[require_api_key] = lambda: None
    try:
        r = TestClient(fastapi_app).post(
            "/api/v1/payments/checkout",
            json={"amount": "1500.00", "currency": "NGN", "customer_email": "a@example.com",
                  "provider": "paystack", "description": "test payment", "callback_url": "http://localhost/cb"},
            headers={"Idempotency-Key": "abc-123"})
    finally:
        fastapi_app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    assert seen["idempotency_key"] == "abc-123"
