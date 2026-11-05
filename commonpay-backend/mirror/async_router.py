from mirror.router import Router, ProviderDown, AllProvidersFailed

class AsyncRouter(Router):
    async def charge(self, key, amount_minor, currency, preferred=None):
        order = self.ranked(preferred)
        p, created = self.store.create_payment(key, order[0], amount_minor, currency)
        if not created:
            if (p["amount_minor"], p["currency"]) != (amount_minor, currency):
                raise ValueError("idempotency key reused with a different payload")
            if p["provider_ref"] or p["status"] == "unknown":
                return p
        last = None
        for name in order:
            try:
                ref = await self.adapters[name](key=key, amount_minor=amount_minor, currency=currency)
            except ProviderDown as e:
                self.store.add_attempt(name, False); last = e
                continue
            except Exception:
                self.store.add_attempt(name, False)
                self.store.set_status(p["id"], "unknown")
                raise
            self.store.add_attempt(name, True)
            self.store.set_submitted(p["id"], name, ref)
            return self.store.get_payment(p["id"])
        self.store.set_status(p["id"], "failed")
        raise AllProvidersFailed(str(last))
