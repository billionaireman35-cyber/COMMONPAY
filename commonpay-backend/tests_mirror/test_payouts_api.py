import pytest
from fastapi.testclient import TestClient

from app.api.v1.payouts import get_engine
from app.core.security import require_api_key
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
    fastapi_app.dependency_overrides[require_api_key] = lambda: None
    fastapi_app.dependency_overrides[get_engine] = lambda: eng
    return TestClient(fastapi_app), rail


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


def test_requires_api_key():
    assert TestClient(fastapi_app).post(URL, json=BODY).status_code >= 400
