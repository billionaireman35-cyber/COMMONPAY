import uuid


class PartnerNotConfiguredError(RuntimeError):
    pass


class PartnerAdapter:
    """Interface a licensed partner must implement. CommonPay never holds the funds."""
    name = "base"

    def hold(self, trader_id, amount_minor, currency, reference):
        raise NotImplementedError

    def release(self, partner_ref):
        raise NotImplementedError


class MockPartner(PartnerAdapter):
    """Sandbox only. Moves no money; returns fake references."""
    name = "mock"

    def hold(self, trader_id, amount_minor, currency, reference):
        return "MOCK-" + uuid.uuid4().hex[:12]

    def release(self, partner_ref):
        return True


def get_partner(live):
    if live:
        raise PartnerNotConfiguredError(
            "No licensed partner is configured; live locks are unavailable")
    return MockPartner()
