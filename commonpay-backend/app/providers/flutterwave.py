import httpx
from decimal import Decimal

from app.core.config import settings
from app.core.exceptions import ProviderUnavailable
from app.providers.base import PaymentProvider, CheckoutResult


class FlutterwaveProvider(PaymentProvider):
    name = "flutterwave"
    base_url = "https://api.flutterwave.com/v3"

    async def initialize_payment(
        self,
        reference,
        amount: Decimal,
        currency,
        customer_email,
        description,
        callback_url,
    ):
        if not settings.flutterwave_secret_key:
            raise ProviderUnavailable("Flutterwave credentials are not configured.")

        payload = {
            "tx_ref": reference,
            "amount": str(amount),
            "currency": currency,
            "redirect_url": callback_url,
            "customer": {"email": customer_email},
            "customizations": {
                "title": "CommonPay",
                "description": description,
            },
        }

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/payments",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.flutterwave_secret_key}",
                    "Content-Type": "application/json",
                },
            )

        response.raise_for_status()
        data = response.json()

        if data.get("status") != "success":
            raise ProviderUnavailable("Flutterwave did not create checkout.")

        checkout_url = data.get("data", {}).get("link")

        if not checkout_url:
            raise ProviderUnavailable("Flutterwave returned no checkout URL.")

        return CheckoutResult(
            provider=self.name,
            reference=reference,
            checkout_url=checkout_url,
        )
