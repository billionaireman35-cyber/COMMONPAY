import pytest
from mirror.store import Store, _resolve_url
from mirror.reconcile import reconcile
from mirror.router import Router
from mirror.wallet import WalletService

def test_store_refuses_postgres_under_pytest():
    with pytest.raises(RuntimeError):
        Store("postgresql://u:p@localhost/db")

def test_store_refuses_non_temp_sqlite():
    with pytest.raises(RuntimeError):
        Store("/home/never_created_live.db")

def test_production_requires_database_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("COMMONPAY_MIRROR_DB", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        Store()

def test_render_url_normalised(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/db")
    assert _resolve_url(None) == "postgresql+psycopg2://u:p@h:5432/db"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    assert _resolve_url(None) == "postgresql+psycopg2://u:p@h/db"

def test_recon_results_is_latest_snapshot(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    Router(s, {"a": lambda **k: "r1"}).charge("k1", 1000, "NGN")
    reconcile(s); reconcile(s); reconcile(s)
    assert s._one("SELECT COUNT(*) AS n FROM recon_results")["n"] == 1

def test_wallet_enabled_roundtrip(tmp_path, monkeypatch):
    s = Store(str(tmp_path / "w.db"))
    monkeypatch.setenv("CUSTOMER_WALLETS_LIVE_ENABLED", "true")
    w = WalletService(s, issuer=lambda customer_id: ("paystack", f"acct-{customer_id}"))
    assert w.open_account("c1") == ("paystack", "acct-c1")
    w.record_reported_balance("c1", 5000)
    assert w.reported_balance("c1") == 5000

def test_celery_schedule_defined():
    pytest.importorskip("celery")
    from mirror.tasks import celery_app
    assert "mirror-sweep" in celery_app.conf.beat_schedule
