from fastapi.testclient import TestClient

import app.api.v1.reconciliation as rec
import mirror.runtime as runtime
from app.core.security import require_api_key
from app.main import app as fastapi_app
from mirror.reconcile import reconcile
from mirror.router import Router
from mirror.store import Store


def _get():
    fastapi_app.dependency_overrides[require_api_key] = lambda: None
    try:
        return TestClient(fastapi_app).get("/api/v1/reconciliation")
    finally:
        fastapi_app.dependency_overrides.clear()


def test_empty_report(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "_store", Store(str(tmp_path / "r.db")))
    r = _get()
    assert r.status_code == 200
    body = r.json()
    assert body["payments_total"] == 0 and body["summary"] == {}
    assert body["last_checked_at"] is None and body["flagged"] == []


def test_report_flags_problems(tmp_path, monkeypatch):
    store = Store(str(tmp_path / "r.db"))
    monkeypatch.setattr(runtime, "_store", store)
    Router(store, {"paystack": lambda **k: "r1"}).charge("k1", 1000, "NGN")
    Router(store, {"paystack": lambda **k: "r2"}).charge("k2", 1000, "NGN")
    store.add_event("paystack", "r1", "charge.success", 900, "NGN")      # amount mismatch
    store.add_event("paystack", "ghost", "charge.success", 500, "NGN")   # orphan
    reconcile(store)
    body = _get().json()
    assert body["summary"]["AMOUNT_MISMATCH"] == 1
    assert body["summary"]["AWAITING_CONFIRMATION"] == 1
    assert body["summary"]["ORPHAN_EVENT"] == 1
    assert body["flagged_count"] == 2
    assert {f["verdict"] for f in body["flagged"]} == {"AMOUNT_MISMATCH", "ORPHAN_EVENT"}
    assert body["last_checked_at"]


def test_route_is_protected():
    assert rec.router.dependencies, "reconciliation route must require the API key"


def test_get_never_writes(tmp_path, monkeypatch):
    store = Store(str(tmp_path / "r.db"))
    monkeypatch.setattr(runtime, "_store", store)
    Router(store, {"paystack": lambda **k: "r1"}).charge("k1", 1000, "NGN")
    before = store._one("SELECT COUNT(*) AS n FROM recon_results")["n"]
    _get()
    assert store._one("SELECT COUNT(*) AS n FROM recon_results")["n"] == before == 0
