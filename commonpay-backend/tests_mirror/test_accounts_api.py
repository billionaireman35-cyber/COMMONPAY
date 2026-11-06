import asyncio
import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1.payouts import get_engine
from app.core import auth as A
from app.core.auth import get_auth_store, require_user
from app.core.security import require_api_key
from app.main import app as fastapi_app
from mirror.auth_store import AuthStore
from mirror.payout import MockFunding, MockRail, PayoutEngine, PayoutStore

URL = "/api/v1/accounts"
GOOD = {"account_number": "0123456789", "bank_code": "058", "bank_name": "GTBank"}


@pytest.fixture(autouse=True)
def _clean():
    yield
    fastapi_app.dependency_overrides.clear()


def setup(tmp_path):
    os.environ.setdefault("COMMONPAY_AUTH_SECRET", "t" * 40)
    auth = AuthStore(str(tmp_path / "a.db"))
    eng = PayoutEngine(PayoutStore(str(tmp_path / "p.db")),
                       [MockRail("a", {"0123456789": "ADA OBI"})], MockFunding())
    fastapi_app.dependency_overrides[get_auth_store] = lambda: auth
    fastapi_app.dependency_overrides[get_engine] = lambda: eng
    return auth


def be(auth, email):
    u = auth.get_or_create_user(email)
    fastapi_app.dependency_overrides[require_user] = lambda: dict(auth.get_user(u["id"]))


def test_add_list_remove(tmp_path):
    auth = setup(tmp_path)
    be(auth, "a@example.com")
    c = TestClient(fastapi_app)
    r = c.post(URL, json=GOOD)
    assert r.status_code == 200 and r.json()["account"]["account_name"] == "ADA OBI"
    assert c.post(URL, json=GOOD).status_code == 200
    accts = c.get(URL).json()["accounts"]
    assert len(accts) == 1
    assert c.post(f"{URL}/{accts[0]['id']}/remove").status_code == 200
    assert c.get(URL).json()["accounts"] == []
    assert c.post(f"{URL}/{accts[0]['id']}/remove").status_code == 404


def test_users_are_isolated(tmp_path):
    auth = setup(tmp_path)
    be(auth, "a@example.com")
    c = TestClient(fastapi_app)
    aid = c.post(URL, json=GOOD).json()["account"]["id"]
    be(auth, "b@example.com")
    assert c.get(URL).json()["accounts"] == []
    assert c.post(f"{URL}/{aid}/remove").status_code == 404
    be(auth, "a@example.com")
    assert len(c.get(URL).json()["accounts"]) == 1


def test_unknown_account_and_bad_number(tmp_path):
    auth = setup(tmp_path)
    be(auth, "a@example.com")
    c = TestClient(fastapi_app)
    assert c.post(URL, json=dict(GOOD, account_number="0123456000")).status_code == 404
    assert c.post(URL, json=dict(GOOD, account_number="12")).status_code == 422
    assert c.get(URL).json()["accounts"] == []


def test_requires_login(tmp_path):
    setup(tmp_path)
    assert TestClient(fastapi_app).get(URL).status_code == 401


def test_session_accepted_by_shared_key_guard(tmp_path, monkeypatch):
    store = setup(tmp_path)
    u = store.get_or_create_user("a@example.com")
    token = A.new_token()
    store.add_session(u["id"], A.token_hash(token), 3600)
    monkeypatch.setattr(A, "_store", store)
    assert asyncio.run(require_api_key(None, f"Bearer {token}")) is True
    with pytest.raises(HTTPException):
        asyncio.run(require_api_key(None, "Bearer not-a-real-session"))
