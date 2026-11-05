import os
from decimal import Decimal

import httpx

from app.core.config import settings
from app.core.exceptions import ProviderUnavailable
from app.domain.payments import PaymentIntent
from app.providers.registry import PROVIDERS, get_provider
from mirror.async_router import AsyncRouter
from mirror.router import AllProvidersFailed, ProviderDown
from mirror.runtime import get_store

_MESSAGE = (
    "Checkout created. Payment is not confirmed until "
    "provider verification and reconciliation."
)


def _minor(amount) -> int:
    return int((Decimal(str(amount)) * 100).to_integral_value())


def _response(reference, provider, checkout_url, provider_reference):
    return {
        "reference": reference,
        "provider": provider,
        "checkout_url": checkout_url,
        "provider_reference": provider_reference,
        "status": "PENDING",
        "message": _MESSAGE,
    }


async def create_checkout(
    amount: Decimal,
    currency: str,
    email: str,
    provider_name: str,
    description: str,
    callback_url: str,
    idempotency_key: str | None = None,
):
    if not settings.payments_enabled:
        raise ProviderUnavailable("Payment initiation is disabled.")

    if settings.environment == "production" and not settings.live_payments_enabled:
        raise ProviderUnavailable("Live payments are disabled.")

    store = get_store()

    if idempotency_key:
        prior = store.get_by_key(idempotency_key)
        if prior and prior["provider_ref"] and prior["checkout_url"]:
            if prior["currency"] != currency or prior["amount_minor"] != _minor(amount):
                raise ValueError("Idempotency key was already used with a different request.")
            return _response(prior["provider_ref"], prior["provider"], prior["checkout_url"], None)

    intent = PaymentIntent.create(
        amount=amount,
        currency=currency,
        customer_email=email,
        provider=provider_name,
        description=description,
    )

    get_provider(provider_name)  # unsupported provider still raises ValueError

    chosen = provider_name.lower()
    failover = os.getenv("ROUTING_FAILOVER_ENABLED", "false").lower() == "true"
    names = [chosen] + ([n for n in PROVIDERS if n != chosen] if failover else [])
    created = {}

    def make_adapter(name):
        async def adapter(**_):
            try:
                result = await get_provider(name).initialize_payment(
                    reference=intent.reference,
                    amount=intent.amount.amount,
                    currency=intent.amount.currency,
                    customer_email=intent.customer_email,
                    description=intent.description,
                    callback_url=callback_url,
                )
            except (ProviderUnavailable, httpx.HTTPError, ValueError) as exc:
                # Checkout creation moves no money, so failing over is safe.
                raise ProviderDown(str(exc)) from exc
            created[name] = result
            return intent.reference
        return adapter

    router = AsyncRouter(store, {n: make_adapter(n) for n in names})

    try:
        payment = await router.charge(
            idempotency_key or intent.reference,
            _minor(intent.amount.amount),
            intent.amount.currency,
            preferred=chosen,
        )
    except AllProvidersFailed as exc:
        raise ProviderUnavailable(f"No provider could create the checkout: {exc}") from exc

    result = created.get(payment["provider"])
    if result is None:
        raise ProviderUnavailable("A checkout for this key is already in progress. Retry shortly.")

    store.set_checkout_url(payment["id"], result.checkout_url)
    return _response(intent.reference, result.provider, result.checkout_url, result.provider_reference)
