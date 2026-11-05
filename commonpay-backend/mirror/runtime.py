import os
from mirror.store import Store

_store = None

def get_store():
    global _store
    if _store is None:
        # Under pytest always in-memory; DATABASE_URL is never consulted.
        _store = Store(":memory:" if os.environ.get("PYTEST_CURRENT_TEST") else None)
    return _store
