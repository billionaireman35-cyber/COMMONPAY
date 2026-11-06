from datetime import date, timedelta

import pytest

from mirror.daily_close import build_close, day_bounds
from mirror.locks import LockError, LockService
from mirror.partner import PartnerNotConfiguredError
from mirror.store import Store

DAY = date(2026, 11, 3)
NEXT = DAY + timedelta(days=1)


def seeded():
    store = Store(":memory:")
    spec = [("a", 1_500_000, "MATCHED"), ("b", 500_000, "MATCHED"),
            ("c", 200_000, "AWAITING_CONFIRMATION"), ("d", 100_000, "FAILED"),
            ("e", 300_000, "AMOUNT_MISMATCH")]
    results = []
    for key, amt, verdict in spec:
        p, _ = store.create_payment(key, "paystack", amt, "NGN")
        store._exec("UPDATE payments SET created_at=:t WHERE id=:i",
                    t=day_bounds(DAY, NEXT)[0] + 3600, i=p["id"])
        results.append({"payment_id": p["id"], "provider": "paystack",
                        "provider_ref": key, "verdict": verdict, "detail": ""})
    store.save_results(results)
    return store


def test_daily_close_totals():
    t = build_close(seeded(), DAY, NEXT)["totals"]["NGN"]
    assert t["confirmed_minor"] == 2_000_000
    assert t["pending_minor"] == 200_000
    assert t["failed_minor"] == 100_000
    assert t["flagged_minor"] == 300_000
    assert t["payments"] == 5


def test_monthly_close_matches_day():
    t = build_close(seeded(), date(2026, 11, 1), date(2026, 12, 1))["totals"]["NGN"]
    assert t["confirmed_minor"] == 2_000_000


def test_percent_lock_and_idempotent():
    svc = LockService(seeded())
    row, created = svc.create_lock("t1", DAY, NEXT + timedelta(days=30), percent_bps=1000)
    assert created and row["amount_minor"] == 200_000 and row["simulated"] == 1
    row2, created2 = svc.create_lock("t1", DAY, NEXT + timedelta(days=30), percent_bps=5000)
    assert not created2 and row2["id"] == row["id"]


def test_cannot_lock_more_than_confirmed():
    svc = LockService(seeded())
    with pytest.raises(LockError):
        svc.create_lock("t1", DAY, NEXT, amount_minor=2_000_001)


def test_release_only_after_date():
    svc = LockService(seeded())
    svc.create_lock("t1", DAY, NEXT, amount_minor=100_000)
    assert svc.release_due(DAY) == []
    assert len(svc.release_due(NEXT)) == 1
    assert svc.release_due(NEXT) == []


def test_live_mode_refuses_without_partner(monkeypatch):
    monkeypatch.setenv("TRADER_LOCKS_LIVE_ENABLED", "true")
    svc = LockService(seeded())
    with pytest.raises(PartnerNotConfiguredError):
        svc.create_lock("t1", DAY, NEXT, amount_minor=100_000)
