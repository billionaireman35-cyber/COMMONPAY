import asyncio, types
from decimal import Decimal
import pytest
import app.services.payment_orchestrator as orch
import mirror.runtime as runtime
from app.core.exceptions import ProviderUnavailable
from app.providers.base import CheckoutResult
from mirror.reconcile import reconcile
from mirror.router import Router
from mirror.store import Store
from mirror.webhook_ingest import ingest

class Fake:
    def __init__(self, name):
        self.name, self.fail, self.calls = name, False, 0
    async def initialize_payment(self, **kw):
        self.calls += 1
        if self.fail:
            raise ProviderUnavailable("down")
        return CheckoutResult(provider=self.name, reference=kw["reference"],
                              checkout_url=f"https://{self.name}.test/{kw['reference']}")

@pytest.fixture
def env(tmp_path, monkeypatch):
    store = Store(str(tmp_path / "w.db"))
    monkeypatch.setattr(runtime, "_store", store)
    monkeypatch.setattr(orch, "settings", types.SimpleNamespace(
        payments_enabled=True, environment="development", live_payments_enabled=False))
    monkeypatch.delenv("ROUTING_FAILOVER_ENABLED", raising=False)
    fakes = {"paystack": Fake("paystack"), "flutterwave": Fake("flutterwave")}
    monkeypatch.setattr(orch, "get_provider", lambda n: fakes[n.lower()])
    return store, fakes

def checkout(provider="paystack", **kw):
    return asyncio.run(orch.create_checkout(
        Decimal("1500.00"), "NGN", "buyer@example.com", provider, "test", "http://localhost/cb", **kw))

def test_checkout_is_persisted(env):
    store, _ = env
    r = checkout()
    p = store.list_payments()[0]
    assert p["amount_minor"] == 150000 and p["checkout_url"] == r["checkout_url"]
    assert p["provider_ref"] == r["reference"]

def test_idempotent_replay(env):
    _, fakes = env
    a = checkout(idempotency_key="k1"); b = checkout(idempotency_key="k1")
    assert a["checkout_url"] == b["checkout_url"] and fakes["paystack"].calls == 1

def test_no_failover_by_default(env):
    _, fakes = env
    fakes["paystack"].fail = True
    with pytest.raises(ProviderUnavailable):
        checkout()

def test_failover_when_enabled(env, monkeypatch):
    _, fakes = env
    fakes["paystack"].fail = True
    monkeypatch.setenv("ROUTING_FAILOVER_ENABLED", "true")
    assert checkout()["provider"] == "flutterwave"

def test_webhook_ingest_dedupes(env):
    store, _ = env
    body = b'{"event":"charge.success","data":{"reference":"r1","amount":150000,"currency":"NGN"}}'
    assert ingest(store, "paystack", body) is True
    assert ingest(store, "paystack", body) is False
    assert ingest(store, "paystack", b"not json") is False

def test_flutterwave_amount_to_minor(env):
    store, _ = env
    body = b'{"event":"charge.completed","data":{"tx_ref":"r2","amount":1500.5,"currency":"NGN","status":"successful"}}'
    ingest(store, "flutterwave", body)
    assert store.events_for("flutterwave", "r2")[0]["amount_minor"] == 150050

def test_webhook_alone_is_not_confirmation(env):
    store, _ = env
    Router(store, {"paystack": lambda **k: "r1"}).charge("k", 150000, "NGN")
    ingest(store, "paystack", b'{"event":"charge.success","data":{"reference":"r1","amount":150000,"currency":"NGN"}}')
    assert reconcile(store)[0]["verdict"] == "AWAITING_CONFIRMATION"
