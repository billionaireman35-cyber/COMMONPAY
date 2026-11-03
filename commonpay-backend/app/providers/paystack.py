import httpx
from decimal import Decimal

from app.core.config import settings
from app.core.exceptions import ProviderUnavailable
from app.providers.base import PaymentProvider, CheckoutResult


class PaystackProvider(PaymentProvider):
    name = "paystack"
    base_url = "https://api.paystack.co"

    @staticmethod
    def to_minor_units(amount: Decimal, currency: str) -> int:
        if currency not in {"NGN", "USD", "GHS", "ZAR", "KES"}:
            raise ValueError("Currency requires provider capability verification.")

        return int(amount * Decimal("100"))

    async def initialize_payment(
        self,
        reference,
        amount: Decimal,
        currency,
        customer_email,
        description,
        callback_url,
    ):
        if not settings.paystack_secret_key:
            raise ProviderUnavailable("Paystack credentials are not configured.")

        payload = {
            "email": customer_email,
            "amount": self.to_minor_units(amount, currency),
            "currency": currency,
            "reference": reference,
            "callback_url": callback_url,
            "metadata": {
                "description": description,
                "platform": "CommonPay",
            },
        }

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/transaction/initialize",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.paystack_secret_key}",
                    "Content-Type": "application/json",
                },
            )

        response.raise_for_status()
        data = response.json()

        if not data.get("status"):
            raise ProviderUnavailable("Paystack did not create checkout.")

        result = data.get("data", {})
        checkout_url = result.get("authorization_url")

        if not checkout_url:
            raise ProviderUnavailable("Paystack returned no checkout URL.")

        return CheckoutResult(
            provider=self.name,
            reference=reference,
            checkout_url=checkout_url,
            provider_reference=result.get("reference"),
        )
