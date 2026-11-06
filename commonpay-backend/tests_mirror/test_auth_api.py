import re

import pytest
from fastapi.testclient import TestClient

import app.api.v1.auth as auth_api
from app.api.v1.payouts import get_engine
from app.core.auth import get_auth_store
from app.main import app as fastapi_app
from mirror.auth_store import AuthStore
from mirror.payout import MockFunding, MockRail, PayoutEngine, PayoutStore

AUTH = "/api/v1/auth"
P = "/api/v1/payouts/batches"
BODY = {"batch_key": "b1", "currency": "NGN", "rows": [
    {"name": "Ada", "account_number": "0123456789", "bank_code": "058", "amount": "1500.00"}]}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("COMMONPAY_AUTH_SECRET", "s" * 40)
    sent = {}
    monkeypatch.setattr(auth_api, "send_email", lambda to, subject, text: sent.__setitem__(to, text))
    store = AuthStore(str(tmp_path / "a.db"))
    rail = MockRail("a", {"0123456789": "ADA OBI"})
    eng = PayoutEngine(PayoutStore(str(tmp_path / "p.db")), [rail], MockFunding())
    fastapi_app.dependency_overrides[get_auth_store] = lambda: store
    fastapi_app.dependency_overrides[get_engine] = lambda: eng
    yield TestClient(fastapi_app), store, sent, rail
    fastapi_app.dependency_overrides.clear()


def ask(c, sent, email):
    r = c.post(f"{AUTH}/request-code", json={"email": email})
    assert r.status_code == 200, r.text
    return re.search(r"\b(\d{6})\b", sent[email]).group(1)


def verify(c, email, code):
    return c.post(f"{AUTH}/verify-code", json={"email": email, "code": code})


def bearer(r):
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


def with_pin(h, pin):
    return {**h, "X-Transaction-Pin": pin}


def signup(c, sent, email, login="482913", txn="7391"):
    r = verify(c, email, ask(c, sent, email))
    assert r.status_code == 200, r.text
    p = c.post(f"{AUTH}/set-pins", json={"login_pin": login, "txn_pin": txn}, headers=bearer(r))
    assert p.status_code == 200, p.text
    return r.json()["device_token"]


def signin(c, dev, pin):
    return c.post(f"{AUTH}/login", json={"device_token": dev, "pin": pin})


def test_signup_login_scoping_and_txn_pin(env):
    c, store, sent, rail = env
    h = bearer(signin(c, signup(c, sent, "ada@example.com"), "482913"))
    assert c.get(f"{AUTH}/me", headers=h).json() == {"email": "ada@example.com", "has_txn_pin": True}
    assert c.post(P, json=BODY, headers=h).status_code == 200
    assert c.post(f"{P}/b1/run", headers=h).status_code == 403
    assert rail.calls == 0
    assert c.post(f"{P}/b1/run", headers=with_pin(h, "7391")).status_code == 200
    assert rail.calls >= 1

    h2 = bearer(signin(c, signup(c, sent, "bola@example.com", "573921", "2846"), "573921"))
    assert c.get(f"{P}/b1", headers=h2).status_code == 404
    assert c.post(f"{P}/b1/run", headers=with_pin(h2, "2846")).status_code == 404
    assert c.post(P, json=BODY, headers=h2).status_code == 409
    assert c.post(P, json=dict(BODY, batch_key="b2"), headers=h2).status_code == 200


def test_requires_login(env):
    c, *_ = env
    assert c.get(f"{P}/b1").status_code == 401
    assert c.get(f"{P}/banks").status_code == 401
    assert c.get(f"{AUTH}/me", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_txn_pin_locks_after_three_wrong(env):
    c, store, sent, rail = env
    h = bearer(signin(c, signup(c, sent, "a@example.com"), "482913"))
    c.post(P, json=BODY, headers=h)
    for _ in range(3):
        assert c.post(f"{P}/b1/run", headers=with_pin(h, "0000")).status_code == 403
    assert c.post(f"{P}/b1/run", headers=with_pin(h, "7391")).status_code == 423
    assert rail.calls == 0


def test_login_lockout_cleared_by_email_code(env):
    c, store, sent, rail = env
    dev = signup(c, sent, "a@example.com")
    for _ in range(5):
        assert signin(c, dev, "111222").status_code == 401
    assert signin(c, dev, "482913").status_code == 423
    assert verify(c, "a@example.com", ask(c, sent, "a@example.com")).status_code == 200
    assert signin(c, dev, "482913").status_code == 200


def test_unknown_device(env):
    c, *_ = env
    r = signin(c, "x" * 30, "482913")
    assert r.status_code == 401 and r.json()["detail"].startswith("device-unknown:")


def test_wrong_code_five_times_burns_it(env):
    c, store, sent, rail = env
    code = ask(c, sent, "a@example.com")
    wrong = f"{(int(code) + 1) % 10 ** 6:06d}"
    for _ in range(5):
        assert verify(c, "a@example.com", wrong).status_code == 400
    assert verify(c, "a@example.com", code).status_code == 400


def test_expired_code_and_session(env):
    c, store, sent, rail = env
    code = ask(c, sent, "a@example.com")
    store._exec("UPDATE auth_codes SET expires_at=0")
    assert verify(c, "a@example.com", code).status_code == 400
    h = bearer(signin(c, signup(c, sent, "b@example.com"), "482913"))
    store._exec("UPDATE auth_sessions SET expires_at=0")
    assert c.get(f"{AUTH}/me", headers=h).status_code == 401


def test_code_request_rate_limit(env):
    c, store, sent, rail = env
    for _ in range(3):
        ask(c, sent, "a@example.com")
    assert c.post(f"{AUTH}/request-code", json={"email": "a@example.com"}).status_code == 429


def test_pin_setting_rules(env):
    c, store, sent, rail = env
    r = verify(c, "a@example.com", ask(c, sent, "a@example.com"))
    h = bearer(r)
    for bad in ({"login_pin": "123456", "txn_pin": "7391"}, {"login_pin": "111111", "txn_pin": "7391"},
                {"login_pin": "482913", "txn_pin": "0000"}, {"login_pin": "482913", "txn_pin": "4829"}):
        assert c.post(f"{AUTH}/set-pins", json=bad, headers=h).status_code == 422
    ok = {"login_pin": "482913", "txn_pin": "7391"}
    assert c.post(f"{AUTH}/set-pins", json=ok, headers=h).status_code == 200
    # a PIN-login session is not email-fresh, so it cannot change PINs
    h2 = bearer(signin(c, r.json()["device_token"], "482913"))
    assert c.post(f"{AUTH}/set-pins", json=ok, headers=h2).status_code == 403


def test_not_configured_is_503(env, monkeypatch):
    c, *_ = env
    monkeypatch.delenv("COMMONPAY_AUTH_SECRET")
    assert c.post(f"{AUTH}/request-code", json={"email": "a@example.com"}).status_code == 503
