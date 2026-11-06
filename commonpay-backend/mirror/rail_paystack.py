import hashlib

import httpx

from app.core.config import settings
from mirror.payout import AccountNotFound, PayoutRail
from mirror.router import ProviderDown

BASE = "https://api.paystack.co"


def paystack_reference(key):
    """Deterministic, Paystack-legal reference (lowercase, 43 chars) for an idem key."""
    return "cp-" + hashlib.sha256(key.encode()).hexdigest()[:40]


class PaystackPayoutRail(PayoutRail):
    name = "paystack"

    def __init__(self, secret=None, client=None, timeout=20):
        self._secret = secret
        self._client = client or httpx.Client(base_url=BASE, timeout=timeout)

    def _headers(self):
        key = self._secret if self._secret is not None else settings.paystack_secret_key
        if not key:
            raise ProviderDown("paystack key not configured")  # nothing was sent
        return {"Authorization": f"Bearer {key}"}

    def resolve_name(self, account_number, bank_code):
        h = self._headers()
        r = self._client.get("/bank/resolve", headers=h,
                             params={"account_number": account_number, "bank_code": bank_code})
        if r.status_code in (400, 422):
            raise AccountNotFound(account_number)
        r.raise_for_status()
        name = (r.json().get("data") or {}).get("account_name")
        if not name:
            raise AccountNotFound(account_number)
        return name

    def transfer(self, key, amount_minor, currency, account_number, bank_code, name):
        h = self._headers()
        ref = paystack_reference(key)
        # Step 1: recipient. Failing here means no transfer was ever sent: definite.
        try:
            rr = self._client.post("/transferrecipient", headers=h, json={
                "type": "nuban", "name": name, "account_number": account_number,
                "bank_code": bank_code, "currency": currency})
            ok = rr.status_code in (200, 201) and rr.json().get("status")
            code = (rr.json().get("data") or {}).get("recipient_code") if ok else None
        except httpx.HTTPError as e:
            raise ProviderDown(f"recipient step failed: {type(e).__name__}")
        except ValueError:
            raise ProviderDown("recipient step: unreadable reply")
        if not code:
            raise ProviderDown(f"recipient step rejected ({rr.status_code})")
        # Step 2: the transfer itself.
        try:
            r = self._client.post("/transfer", headers=h, json={
                "source": "balance", "amount": amount_minor, "recipient": code,
                "reason": "CommonPay payout", "reference": ref, "currency": currency})
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise ProviderDown(f"could not connect: {type(e).__name__}")
        # any other exception (read timeout, etc.) propagates: ambiguous
        if r.status_code in (401, 403, 429):
            raise ProviderDown(f"refused ({r.status_code})")
        if r.status_code == 400:
            if self.status(key) == "not_found":  # if this raises, it stays ambiguous
                raise ProviderDown("rejected: " + r.text[:120])
            return ref  # the reference already exists at Paystack
        if r.status_code not in (200, 201):
            raise RuntimeError(f"ambiguous HTTP {r.status_code}")
        if not r.json().get("status"):
            raise RuntimeError("ambiguous: 2xx without status")
        return ref

    def status(self, key):
        r = self._client.get(f"/transfer/verify/{paystack_reference(key)}", headers=self._headers())
        if r.status_code == 404:
            return "not_found"
        r.raise_for_status()
        s = ((r.json().get("data") or {}).get("status") or "").lower()
        if s == "success":
            return "success"
        if s in ("failed", "reversed"):
            return "failed"
        return "pending"  # pending, otp, received, etc.

    def balance_minor(self, currency="NGN"):
        r = self._client.get("/balance", headers=self._headers())
        r.raise_for_status()
        for b in r.json().get("data") or []:
            if b.get("currency") == currency:
                return int(b["balance"])
        return 0

    def banks(self):
        r = self._client.get("/bank", headers=self._headers(),
                             params={"country": "nigeria", "perPage": 200})
        r.raise_for_status()
        rows = [b for b in (r.json().get("data") or []) if b.get("active", True)]
        return sorted(({"name": b["name"], "code": b["code"]} for b in rows), key=lambda b: b["name"])
