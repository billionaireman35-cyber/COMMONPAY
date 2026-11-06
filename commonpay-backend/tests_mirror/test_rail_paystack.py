import json
import re

import httpx
import pytest

from mirror.payout import AccountNotFound
from mirror.rail_paystack import PaystackPayoutRail, paystack_reference
from mirror.router import ProviderDown

REF = paystack_reference("b1:1")
OK = httpx.Response(200, json={"status": True, "data": {"recipient_code": "RCP_1", "reference": REF}})


def mk(routes, secret="sk_test_x"):
    calls = []

    def handler(req):
        calls.append((req.url.path, json.loads(req.content) if req.content else None))
        h = routes[req.url.path]
        if isinstance(h, Exception):
            raise h
        return h

    c = httpx.Client(base_url="https://api.paystack.co", transport=httpx.MockTransport(handler))
    return PaystackPayoutRail(secret=secret, client=c), calls


def send(rail):
    return rail.transfer("b1:1", 150000, "NGN", "0123456789", "058", "ADA OBI")


def test_reference_is_paystack_legal():
    assert re.fullmatch(r"[a-z0-9_-]{16,50}", REF) and REF == paystack_reference("b1:1")
    assert paystack_reference("b1:2") != REF


def test_resolve():
    r, _ = mk({"/bank/resolve": httpx.Response(200, json={"status": True, "data": {"account_name": "ADA OBI"}})})
    assert r.resolve_name("0123456789", "058") == "ADA OBI"
    r, _ = mk({"/bank/resolve": httpx.Response(422, json={"status": False})})
    with pytest.raises(AccountNotFound):
        r.resolve_name("0123456789", "058")


def test_transfer_happy_sends_kobo_and_reference():
    r, calls = mk({"/transferrecipient": OK, "/transfer": httpx.Response(200, json={"status": True})})
    assert send(r) == REF
    body = calls[1][1]
    assert body["amount"] == 150000 and body["reference"] == REF and body["source"] == "balance"


def test_connect_error_is_definite():
    r, _ = mk({"/transferrecipient": OK, "/transfer": httpx.ConnectError("x")})
    with pytest.raises(ProviderDown):
        send(r)


def test_read_timeout_is_ambiguous():
    r, _ = mk({"/transferrecipient": OK, "/transfer": httpx.ReadTimeout("x")})
    with pytest.raises(httpx.ReadTimeout):
        send(r)


def test_5xx_is_ambiguous():
    r, _ = mk({"/transferrecipient": OK, "/transfer": httpx.Response(502)})
    with pytest.raises(RuntimeError) as e:
        send(r)
    assert not isinstance(e.value, ProviderDown)


def test_auth_and_ratelimit_are_definite():
    for code in (401, 403, 429):
        r, _ = mk({"/transferrecipient": OK, "/transfer": httpx.Response(code)})
        with pytest.raises(ProviderDown):
            send(r)


def test_400_not_found_at_provider_is_definite():
    r, _ = mk({"/transferrecipient": OK, "/transfer": httpx.Response(400, json={"message": "Insufficient balance"}),
               f"/transfer/verify/{REF}": httpx.Response(404)})
    with pytest.raises(ProviderDown):
        send(r)


def test_400_but_reference_exists_is_not_failover():
    r, _ = mk({"/transferrecipient": OK, "/transfer": httpx.Response(400, json={"message": "duplicate"}),
               f"/transfer/verify/{REF}": httpx.Response(200, json={"data": {"status": "success"}})})
    assert send(r) == REF


def test_400_and_verify_unreachable_stays_ambiguous():
    r, _ = mk({"/transferrecipient": OK, "/transfer": httpx.Response(400),
               f"/transfer/verify/{REF}": httpx.ReadTimeout("x")})
    with pytest.raises(httpx.ReadTimeout):
        send(r)


def test_recipient_failure_never_reaches_transfer():
    r, calls = mk({"/transferrecipient": httpx.Response(500)})
    with pytest.raises(ProviderDown):
        send(r)
    assert [p for p, _ in calls] == ["/transferrecipient"]


def test_no_key_sends_nothing():
    r, calls = mk({}, secret="")
    with pytest.raises(ProviderDown):
        send(r)
    assert calls == []


def test_status_mapping():
    for raw, want in (("success", "success"), ("failed", "failed"), ("reversed", "failed"),
                      ("pending", "pending"), ("otp", "pending")):
        r, _ = mk({f"/transfer/verify/{REF}": httpx.Response(200, json={"data": {"status": raw}})})
        assert r.status("b1:1") == want
    r, _ = mk({f"/transfer/verify/{REF}": httpx.Response(404)})
    assert r.status("b1:1") == "not_found"
