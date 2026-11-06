import os

from mirror.payout import FundingSource, InsufficientFunds, PayoutEngine, PrefundedFunding
from mirror.rail_paystack import PaystackPayoutRail
from mirror.runtime import get_store

_engine = None


class CappedFunding(FundingSource):
    """Refuses any single run above a hard cap, before anything is sent."""
    def __init__(self, inner, cap_minor):
        self.inner, self.cap = inner, cap_minor

    def ensure(self, ref, total_minor, currency):
        if total_minor > self.cap:
            raise InsufficientFunds(f"run total {total_minor} exceeds PAYOUTS_MAX_TOTAL_MINOR {self.cap}")
        return self.inner.ensure(ref, total_minor, currency)


def build_engine(store, env, secret=None, client=None):
    if env.get("PAYOUTS_LIVE_ENABLED", "false").strip().lower() != "true":
        return None
    if secret is None:
        from app.core.config import settings
        secret = settings.paystack_secret_key
    if not secret:
        return None
    rail = PaystackPayoutRail(secret=secret, client=client)

    def balance():
        try:
            return rail.balance_minor("NGN")
        except Exception as e:  # nothing has been sent yet, so refusing is safe
            raise InsufficientFunds("could not read provider balance") from e

    cap = int(env.get("PAYOUTS_MAX_TOTAL_MINOR", "5000000"))
    return PayoutEngine(store, [rail], CappedFunding(PrefundedFunding(balance), cap))


def get_live_engine():
    global _engine
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    if _engine is None:
        _engine = build_engine(get_store(), os.environ)
    return _engine
