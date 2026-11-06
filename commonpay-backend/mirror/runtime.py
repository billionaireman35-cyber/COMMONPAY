import os
from mirror.payout_store import PayoutStore

_store = None

def get_store():
    global _store
    if _store is None:
        # Under pytest always in-memory; DATABASE_URL is never consulted.
        _store = PayoutStore(":memory:" if os.environ.get("PYTEST_CURRENT_TEST") else None)
    return _store
