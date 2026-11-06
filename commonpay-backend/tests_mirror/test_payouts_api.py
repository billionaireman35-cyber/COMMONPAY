import os

import pytest
from fastapi.testclient import TestClient

from app.api.v1.payouts import get_engine
from app.core.auth import get_auth_store, hash_pin, require_user
from app.core.security import require_api_key
from mirror.auth_store import AuthStore
from app.main import app as fastapi_app
from mirror.payout import MockFunding, MockRail, PayoutEngine, PayoutStore

NAMES = {"0123456789": "ADA OBI", "0123456790": "TUNDE BELLO"}
BODY = {"batch_key": "b1", "currency": "NGN", "rows": [
    {"name": "Ada Obi", "account_number": "0123456789", "bank_code": "058", "amount": "1500.00"},
    {"name": "Tunde Bello", "account_number": "0123456790", "bank_code": "044", "amount": 2500.5},
]}
URL = "/api/v1/payouts/batches"


def make(tmp_path, funding=None):
    rail = MockRail("a", NAMES)
    eng = PayoutEngine(PayoutStore(str(tmp_path / "p.db")), [rail], funding or MockFunding())
    os.environ.setdefault("COMMONPAY_AUTH_SECRET", "t" * 40)
    auth = AuthStore(str(tmp_path / "a.db"))
    me = auth.get_or_create_user("t@example.com")
    auth.set_pins(me["id"], hash_pin("482913"), hash_pin("7391"))
    fastapi_app.dependency_overrides[get_auth_store] = lambda: auth
    fastapi_app.dependency_overrides[require_user] = lambda: dict(auth.get_user(me["id"]))
    fastapi_app.dependency_overrides[require_api_key] = lambda: None
    fastapi_app.dependency_overrides[get_engine] = lambda: eng
    client = TestClient(fastapi_app)
    client.headers["X-Transaction-Pin"] = "7391"
    return client, rail


@pytest.fixture(autouse=True)
def _clean():
    yield
    fastapi_app.dependency_overrides.clear()


def test_full_flow(tmp_path):
    c, rail = make(tmp_path)
    r = c.post(URL, json=BODY)
    assert r.status_code == 200 and r.json()["created"] is True
    assert r.json()["summary"]["pending"]["count"] == 2
    assert c.post(f"{URL}/b1/run").json()["summary"]["submitted"]["count"] == 2
    assert c.post(f"{URL}/b1/refresh").json()["summary"]["confirmed"]["count"] == 2
    g = c.get(f"{URL}/b1").json()
    assert [i["status"] for i in g["items"]] == ["confirmed", "confirmed"]
    assert g["items"][1]["amount"] == "2500.50"
    assert rail.calls == 2


def test_repeat_upload_and_run_never_resend(tmp_path):
    c, rail = make(tmp_path)
    c.post(URL, json=BODY)
    c.post(f"{URL}/b1/run")
    assert c.post(URL, json=BODY).json()["created"] is False
    c.post(f"{URL}/b1/run")
    assert rail.calls == 2


def test_same_key_different_rows_conflict(tmp_path):
    c, _ = make(tmp_path)
    c.post(URL, json=BODY)
    assert c.post(URL, json=dict(BODY, rows=BODY["rows"][:1])).status_code == 409


def test_unknown_batch_404(tmp_path):
    c, _ = make(tmp_path)
    assert c.post(f"{URL}/nope/run").status_code == 404
    assert c.post(f"{URL}/nope/refresh").status_code == 404
    assert c.get(f"{URL}/nope").status_code == 404


def test_insufficient_funds_409_sends_nothing(tmp_path):
    c, rail = make(tmp_path, funding=MockFunding(balance_minor=100))
    c.post(URL, json=BODY)
    assert c.post(f"{URL}/b1/run").status_code == 409
    assert rail.calls == 0


def test_validation(tmp_path):
    c, _ = make(tmp_path)
    assert c.post(URL, json=dict(BODY, rows=[])).status_code == 422
    assert c.post(URL, json=dict(BODY, batch_key="bad key!")).status_code == 422


def test_no_rails_configured_is_503(tmp_path):
    c, _ = make(tmp_path)
    fastapi_app.dependency_overrides.pop(get_engine)
    assert c.post(URL, json=BODY).status_code == 503




def test_verify_resolves_names_and_sends_nothing(tmp_path):
    c, rail = make(tmp_path)
    c.post(URL, json=BODY)
    items = c.post(f"{URL}/b1/verify").json()["items"]
    assert [i["resolved_name"] for i in items] == ["ADA OBI", "TUNDE BELLO"]
    assert [i["status"] for i in items] == ["pending", "pending"]
    assert rail.calls == 0


def test_verify_flags_mismatch_and_404(tmp_path):
    c, rail = make(tmp_path)
    rail.names["0123456789"] = "SOMEONE ELSE"
    c.post(URL, json=BODY)
    items = c.post(f"{URL}/b1/verify").json()["items"]
    assert items[0]["status"] == "rejected" and items[0]["detail"] == "name mismatch"
    assert c.post(f"{URL}/nope/verify").status_code == 404


def test_resolve_and_banks(tmp_path):
    c, _ = make(tmp_path)
    u = "/api/v1/payouts/resolve"
    assert c.get(u, params={"account_number": "0123456789", "bank_code": "058"}).json() == {"account_name": "ADA OBI"}
    assert c.get(u, params={"account_number": "0123456799", "bank_code": "058"}).status_code == 404
    assert c.get(u, params={"account_number": "12", "bank_code": "058"}).status_code == 422
    assert c.get("/api/v1/payouts/banks").json() == {"banks": []}


def test_duplicate_list_blocked_after_send_unless_allowed(tmp_path):
    c, rail = make(tmp_path)
    c.post(URL, json=BODY)
    c.post(f"{URL}/b1/run")
    again = dict(BODY, batch_key="b2")
    r = c.post(URL, json=again)
    assert r.status_code == 409 and r.json()["detail"].startswith("duplicate-list:")
    assert c.post(URL, json=dict(again, allow_repeat=True)).status_code == 200
    assert rail.calls == 2  # nothing was re-sent by uploading


def test_duplicate_not_blocked_if_never_sent(tmp_path):
    c, _ = make(tmp_path)
    c.post(URL, json=BODY)
    assert c.post(URL, json=dict(BODY, batch_key="b2")).status_code == 200


def test_duplicate_ignores_row_order_and_names(tmp_path):
    c, _ = make(tmp_path)
    c.post(URL, json=BODY)
    c.post(f"{URL}/b1/run")
    rows = [dict(r, name="X") for r in reversed(BODY["rows"])]
    assert c.post(URL, json=dict(BODY, batch_key="b2", rows=rows)).status_code == 409


def test_same_key_same_count_different_accounts_conflict(tmp_path):
    c, _ = make(tmp_path)
    c.post(URL, json=BODY)
    rows = [dict(BODY["rows"][0], account_number="0123456799"), BODY["rows"][1]]
    assert c.post(URL, json=dict(BODY, rows=rows)).status_code == 409
