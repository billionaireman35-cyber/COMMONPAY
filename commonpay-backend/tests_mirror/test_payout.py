import pytest
from mirror.payout import (PayoutEngine, PayoutStore, MockRail, MockFunding,
                           InsufficientFunds, names_match)

NAMES = {"0123456789": "ADA OBI", "0123456790": "TUNDE BELLO CHUKWU"}
ROWS = [
    {"name": "Ada Obi", "account_number": "0123456789", "bank_code": "058", "amount": "1500.00"},
    {"name": "Tunde Bello", "account_number": "0123456790", "bank_code": "044", "amount": "2500.50"},
]


def mk(rails, funding=None, **kw):
    s = PayoutStore(":memory:")
    e = PayoutEngine(s, rails, funding or MockFunding(), **kw)
    e.load("b1", ROWS)
    return s, e


def st(s, e="b1"):
    return {i["row_no"]: i["status"] for i in s.items(s.get_batch(e)["id"])}


def test_happy_path():
    a = MockRail("a", NAMES)
    s, e = mk([a])
    e.run("b1")
    assert st(s) == {1: "submitted", 2: "submitted"}
    e.refresh("b1")
    assert st(s) == {1: "confirmed", 2: "confirmed"}


def test_name_mismatch_never_sent():
    a = MockRail("a", {"0123456789": "SOMEONE ELSE", "0123456790": "TUNDE BELLO"})
    s, e = mk([a])
    e.run("b1")
    assert st(s)[1] == "rejected" and st(s)[2] == "submitted"
    assert len(a.sent) == 1


def test_bad_rows_rejected():
    s = PayoutStore(":memory:")
    e = PayoutEngine(s, [MockRail("a", NAMES)], MockFunding())
    rows = [dict(ROWS[0], account_number="123"), dict(ROWS[0]), dict(ROWS[0]),
            dict(ROWS[1], amount="0"), dict(ROWS[1], amount="10.555")]
    e.load("bx", rows)
    assert list(st(s, "bx").values()) == ["rejected", "pending", "rejected", "rejected", "rejected"]


def test_failover_on_definite_down():
    a, b = MockRail("a", NAMES, down=True), MockRail("b", NAMES)
    s, e = mk([a, b])
    e.run("b1")
    assert all(i["provider"] == "b" for i in s.items(s.get_batch("b1")["id"]))


def test_ambiguous_goes_unknown_no_retry():
    a, b = MockRail("a", NAMES, ambiguous=True), MockRail("b", NAMES)
    s, e = mk([a, b])
    e.run("b1"); e.run("b1")
    assert b.calls == 0 and a.calls == 2 or a.calls == 1
    assert set(st(s).values()) == {"unknown"} or st(s)[2] == "unknown"
    e.refresh("b1")
    assert st(s)[1] == "confirmed"


def test_run_twice_sends_once():
    a = MockRail("a", NAMES)
    s, e = mk([a])
    e.run("b1"); e.run("b1")
    assert a.calls == 2


def test_insufficient_funds_sends_nothing():
    a = MockRail("a", NAMES)
    s, e = mk([a], funding=MockFunding(balance_minor=100))
    with pytest.raises(InsufficientFunds):
        e.run("b1")
    assert a.calls == 0 and set(st(s).values()) == {"pending"}


def test_all_down_stays_pending_then_retries():
    a = MockRail("a", NAMES)
    s, e = mk([a])
    e.run("b1")  # names resolve, sent
    s2, e2 = mk([MockRail("a", NAMES)])
    e2.rails[0].down = True
    e2.run("b1")
    assert set(st(s2).values()) == {"pending"}
    e2.rails[0].down = False
    e2.run("b1")
    assert set(st(s2).values()) == {"submitted"}


def test_interrupted_send_becomes_unknown_not_resent():
    a = MockRail("a", NAMES)
    s, e = mk([a], stale_sending=0)
    first = s.items(s.get_batch("b1")["id"])[0]
    s.set_fields(first["id"], resolved_name="ADA OBI", provider="a")
    assert s.move(first["id"], "pending", "sending")
    e.run("b1")
    assert st(s)[1] == "unknown" and a.calls == 1  # only row 2 was sent


def test_illegal_transition():
    s, e = mk([MockRail("a", NAMES)])
    it = s.items(s.get_batch("b1")["id"])[0]
    with pytest.raises(ValueError):
        s.move(it["id"], "pending", "confirmed")


def test_names_match():
    assert names_match("Ada Obi", "OBI ADA")
    assert not names_match("Ada Obi", "Ada Okafor")
