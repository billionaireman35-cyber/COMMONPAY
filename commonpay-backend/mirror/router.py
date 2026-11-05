class ProviderDown(Exception):
    """Definite failure: provider did NOT process the request. Safe to fail over."""

class AllProvidersFailed(Exception):
    pass

class Router:
    def __init__(self, store, adapters, window=50, min_samples=5):
        self.store, self.adapters = store, dict(adapters)
        self.window, self.min_samples = window, min_samples

    def health(self, name):
        rows = self.store.recent_attempts(name, self.window)
        if len(rows) < self.min_samples:
            return 1.0
        return sum(r["ok"] for r in rows) / len(rows)

    def ranked(self, preferred=None):
        order = sorted(self.adapters, key=lambda n: -self.health(n))
        if preferred in order and self.health(preferred) >= 0.5:
            order.remove(preferred); order.insert(0, preferred)
        return order

    def charge(self, key, amount_minor, currency, preferred=None):
        order = self.ranked(preferred)
        p, created = self.store.create_payment(key, order[0], amount_minor, currency)
        if not created:
            if (p["amount_minor"], p["currency"]) != (amount_minor, currency):
                raise ValueError("idempotency key reused with a different payload")
            if p["provider_ref"] or p["status"] == "unknown":
                return p  # never re-send: could double charge
        last = None
        for name in order:
            try:
                ref = self.adapters[name](key=key, amount_minor=amount_minor, currency=currency)
            except ProviderDown as e:
                self.store.add_attempt(name, False); last = e
                continue
            except Exception:
                # ambiguous (timeout etc.): do NOT fail over; reconciliation resolves it
                self.store.add_attempt(name, False)
                self.store.set_status(p["id"], "unknown")
                raise
            self.store.add_attempt(name, True)
            self.store.set_submitted(p["id"], name, ref)
            return self.store.get_payment(p["id"])
        self.store.set_status(p["id"], "failed")
        raise AllProvidersFailed(str(last))
