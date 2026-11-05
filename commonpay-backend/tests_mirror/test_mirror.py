import pytest
from mirror.store import Store
from mirror.router import Router, ProviderDown, AllProvidersFailed
from mirror.reconcile import reconcile
from mirror.wallet import WalletService, WalletDisabledError

@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "t.db"))

def v(results):
    return {(r["provider"], r["provider_ref"]): r["verdict"] for r in results}

def test_idempotent_charge(store):
    calls = []
    r = Router(store, {"a": lambda **k: calls.append(1) or "ref1"})
    r.charge("k1", 1000, "NGN"); r.charge("k1", 1000, "NGN")
    assert len(calls) == 1 and len(store.list_payments()) == 1

def test_key_reuse_different_payload(store):
    r = Router(store, {"a": lambda **k: "ref1"})
    r.charge("k1", 1000, "NGN")
    with pytest.raises(ValueError):
        r.charge("k1", 2000, "NGN")

def test_failover_on_definite_error(store):
    def down(**k): raise ProviderDown("down")
    r = Router(store, {"a": down, "b": lambda **k: "refB"})
    p = r.charge("k1", 1000, "NGN")
    assert p["provider"] == "b" and p["provider_ref"] == "refB"

def test_no_failover_on_ambiguous_error(store):
    calls = []
    def flaky(**k): calls.append(1); raise TimeoutError()
    r = Router(store, {"a": flaky, "b": lambda **k: "refB"})
    with pytest.raises(TimeoutError):
        r.charge("k1", 1000, "NGN")
    r.charge("k1", 1000, "NGN")
    assert len(calls) == 1
    assert store.list_payments()[0]["status"] == "unknown"

def test_all_fail(store):
    def down(**k): raise ProviderDown("x")
    r = Router(store, {"a": down, "b": down})
    with pytest.raises(AllProvidersFailed):
        r.charge("k1", 1000, "NGN")

def test_reconcile_matched(store):
    Router(store, {"a": lambda **k: "r1"}).charge("k1", 1000, "NGN")
    store.add_event("a", "r1", "charge.success", 1000, "NGN")
    store.add_settlement("a", "r1", 1000, "NGN")
    assert v(reconcile(store))[("a", "r1")] == "MATCHED"

def test_reconcile_awaiting_and_overdue(store):
    Router(store, {"a": lambda **k: "r1"}).charge("k1", 1000, "NGN")
    store.add_event("a", "r1", "charge.success", 1000, "NGN")
    assert v(reconcile(store))[("a", "r1")] == "AWAITING_SETTLEMENT"
    import time
    assert v(reconcile(store, now=time.time() + 5 * 86400))[("a", "r1")] == "SETTLEMENT_OVERDUE"

def test_amount_mismatch(store):
    Router(store, {"a": lambda **k: "r1"}).charge("k1", 1000, "NGN")
    store.add_event("a", "r1", "charge.success", 900, "NGN")
    assert v(reconcile(store))[("a", "r1")] == "AMOUNT_MISMATCH"

def test_orphans(store):
    store.add_event("a", "ghost", "charge.success", 500, "NGN")
    store.add_settlement("a", "ghost2", 500, "NGN")
    res = v(reconcile(store))
    assert res[("a", "ghost")] == "ORPHAN_EVENT"
    assert res[("a", "ghost2")] == "ORPHAN_SETTLEMENT"

def test_wallet_disabled_by_default(store, monkeypatch):
    monkeypatch.delenv("CUSTOMER_WALLETS_LIVE_ENABLED", raising=False)
    with pytest.raises(WalletDisabledError):
        WalletService(store).open_account("c1")
