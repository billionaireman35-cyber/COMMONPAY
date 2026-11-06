import httpx
import pytest

from mirror.payout import InsufficientFunds, PayoutStore
from mirror.payout_runtime import build_engine

ROW = [{"name": "Ada Obi", "account_number": "0123456789", "bank_code": "058", "amount": "1500.00"}]
ON = {"PAYOUTS_LIVE_ENABLED": "true"}


def client(balance=10**9):
    calls = []

    def h(req):
        p = req.url.path
        calls.append(p)
        if p == "/bank/resolve":
            return httpx.Response(200, json={"status": True, "data": {"account_name": "ADA OBI"}})
        if p == "/balance":
            if balance is None:
                raise httpx.ReadTimeout("x")
            return httpx.Response(200, json={"data": [{"currency": "NGN", "balance": balance}]})
        if p == "/transferrecipient":
            return httpx.Response(200, json={"status": True, "data": {"recipient_code": "RCP_1"}})
        if p == "/transfer":
            return httpx.Response(200, json={"status": True})
        if p.startswith("/transfer/verify/"):
            return httpx.Response(200, json={"data": {"status": "success"}})
        return httpx.Response(404)

    return httpx.Client(base_url="https://api.paystack.co", transport=httpx.MockTransport(h)), calls


def eng(env=ON, **kw):
    c, calls = client(**kw)
    return build_engine(PayoutStore(":memory:"), env, secret="sk_test_x", client=c), calls


def test_off_by_default_and_needs_key():
    assert build_engine(PayoutStore(":memory:"), {}, secret="sk") is None
    assert build_engine(PayoutStore(":memory:"), ON, secret="") is None


def test_happy_path_sends_once_and_confirms():
    e, calls = eng()
    e.load("b1", ROW)
    assert e.run("b1")["submitted"]["count"] == 1
    assert e.refresh("b1")["confirmed"]["count"] == 1
    assert calls.count("/transfer") == 1


@pytest.mark.parametrize("kw,env", [
    ({}, dict(ON, PAYOUTS_MAX_TOTAL_MINOR="100")),   # over the cap
    ({"balance": 100}, ON),                          # balance too low
    ({"balance": None}, ON),                         # balance unreadable
])
def test_refusals_send_nothing(kw, env):
    e, calls = eng(env, **kw)
    e.load("b1", ROW)
    with pytest.raises(InsufficientFunds):
        e.run("b1")
    assert "/transfer" not in calls and "/transferrecipient" not in calls
