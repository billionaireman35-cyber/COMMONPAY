import os
from mirror.store import Store

_store = None

def get_store():
    global _store
    if _store is None:
        path = os.environ.get("COMMONPAY_MIRROR_DB")
        if path is None and os.environ.get("PYTEST_CURRENT_TEST"):
            path = ":memory:"
        _store = Store(path)
    return _store
