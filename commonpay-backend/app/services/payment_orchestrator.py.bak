from decimal import Decimal

from app.core.config import settings
from app.core.exceptions import ProviderUnavailable
from app.domain.payments import PaymentIntent
from app.providers.registry import get_provider


async def create_checkout(
    amount: Decimal,
    currency: str,
    email: str,
    provider_name: str,
    description: str,
    callback_url: str,
):
    if not settings.payments_enabled:
        raise ProviderUnavailable("Payment initiation is disabled.")

    if settings.environment == "production" and not settings.live_payments_enabled:
        raise ProviderUnavailable("Live payments are disabled.")

    intent = PaymentIntent.create(
        amount=amount,
        currency=currency,
        customer_email=email,
        provider=provider_name,
        description=description,
    )

    provider = get_provider(provider_name)

    result = await provider.initialize_payment(
        reference=intent.reference,
        amount=intent.amount.amount,
        currency=intent.amount.currency,
        customer_email=intent.customer_email,
        description=intent.description,
        callback_url=callback_url,
    )

    return {
        "reference": intent.reference,
        "provider": result.provider,
        "checkout_url": result.checkout_url,
        "provider_reference": result.provider_reference,
        "status": "PENDING",
        "message": (
            "Checkout created. Payment is not confirmed until "
            "provider verification and reconciliation."
        ),
    }
