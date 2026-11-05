import os

class WalletDisabledError(RuntimeError):
    pass

def wallets_enabled():
    return os.environ.get("CUSTOMER_WALLETS_LIVE_ENABLED", "false").strip().lower() == "true"

class WalletService:
    """PSP-held virtual accounts only. We keep references and provider-reported
    balances. We never hold or move customer funds ourselves."""
    def __init__(self, store, issuer=None):
        self.store, self.issuer = store, issuer

    def _guard(self):
        if not wallets_enabled():
            raise WalletDisabledError("Customer wallets are disabled")

    def open_account(self, customer_id):
        self._guard()
        if self.issuer is None:
            raise RuntimeError("No provider issuer configured")
        provider, ref = self.issuer(customer_id=customer_id)
        self.store.add_wallet(customer_id, provider, ref)
        return provider, ref

    def record_reported_balance(self, customer_id, balance_minor):
        self._guard()
        self.store.set_wallet_balance(customer_id, balance_minor)

    def reported_balance(self, customer_id):
        self._guard()
        r = self.store.get_wallet(customer_id)
        return r["reported_balance_minor"] if r is not None else None
