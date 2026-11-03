from app.providers.flutterwave import FlutterwaveProvider
from app.providers.paystack import PaystackProvider


PROVIDERS = {
    "flutterwave": FlutterwaveProvider,
    "paystack": PaystackProvider,
}


def get_provider(name: str):
    provider = PROVIDERS.get(name.lower())

    if provider is None:
        raise ValueError("Unsupported payment provider.")

    return provider()
