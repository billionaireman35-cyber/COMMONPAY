from decimal import Decimal
import httpx
from app.core.config import settings

def _minor(x):
    return None if x is None else int((Decimal(str(x)) * 100).to_integral_value())

async def verify(provider, reference):
    """Ask the provider directly. Returns (status, amount_minor, currency)."""
    async with httpx.AsyncClient(timeout=20) as c:
        if provider == "paystack":
            r = await c.get(f"https://api.paystack.co/transaction/verify/{reference}",
                            headers={"Authorization": f"Bearer {settings.paystack_secret_key}"})
            r.raise_for_status()
            d = r.json().get("data") or {}
            return d.get("status"), d.get("amount"), d.get("currency")
        if provider == "flutterwave":
            r = await c.get("https://api.flutterwave.com/v3/transactions/verify_by_reference",
                            params={"tx_ref": reference},
                            headers={"Authorization": f"Bearer {settings.flutterwave_secret_key}"})
            r.raise_for_status()
            d = r.json().get("data") or {}
            return d.get("status"), _minor(d.get("amount")), d.get("currency")
    raise ValueError(f"Unsupported provider: {provider}")
