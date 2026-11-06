import hashlib
import hmac
import math
import os
import re
import secrets
import time

from fastapi import Depends, Header, HTTPException

_store = None
_ITER = 120_000


def get_auth_store():
    global _store
    if _store is None:
        from mirror.auth_store import AuthStore
        _store = AuthStore()
    return _store


def secret() -> bytes:
    s = os.environ.get("COMMONPAY_AUTH_SECRET", "")
    if len(s) < 32:
        raise HTTPException(status_code=503, detail="Sign-in is not configured.")
    return s.encode()


def hash_pin(pin, salt=None):
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", secret() + b"|" + pin.encode(), salt, _ITER)
    return salt.hex() + "$" + dk.hex()


def check_pin(pin, stored):
    try:
        salt_hex, dk_hex = stored.split("$")
        salt = bytes.fromhex(salt_hex)
    except Exception:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", secret() + b"|" + pin.encode(), salt, _ITER)
    return hmac.compare_digest(dk.hex(), dk_hex)


def new_token():
    return secrets.token_urlsafe(32)


def token_hash(t):
    return hashlib.sha256(t.encode()).hexdigest()


def code_hash(email, code):
    return hmac.new(secret(), f"{email}|{code}".encode(), hashlib.sha256).hexdigest()


def wait_text(seconds):
    m = max(1, math.ceil(seconds / 60))
    if m >= 120:
        return f"{math.ceil(m / 60)} hours"
    return f"{m} minute" + ("s" if m > 1 else "")


def require_user(authorization: str | None = Header(default=None), store=Depends(get_auth_store)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="session-expired: Please sign in.")
    s = store.session_by_hash(token_hash(authorization[7:].strip()), time.time())
    if s is None:
        raise HTTPException(status_code=401, detail="session-expired: Please sign in again.")
    return dict(s)


def check_txn_pin(store, user, pin):
    """Raises unless the 4-digit transaction PIN is right. Locks after 3 wrong tries."""
    if not pin or not re.fullmatch(r"\d{4}", pin):
        raise HTTPException(status_code=403, detail="txn-pin: Enter your 4-digit transaction PIN.")
    u = store.get_user(user["id"])
    now = time.time()
    if u["txn_locked_until"] > now:
        raise HTTPException(status_code=423, detail="txn-pin: Too many wrong tries. Try again in "
                            + wait_text(u["txn_locked_until"] - now) + ".")
    if not u["txn_pin_hash"]:
        raise HTTPException(status_code=403, detail="txn-pin: Set your transaction PIN first.")
    if check_pin(pin, u["txn_pin_hash"]):
        store.record_success(u["id"], "txn")
        return
    left = max(0, 3 - store.record_failure(u["id"], "txn", 3, 1800))
    raise HTTPException(status_code=403, detail="txn-pin: Wrong transaction PIN. " + (
        f"{left} tries left." if left else "Transactions are locked for a while."))
