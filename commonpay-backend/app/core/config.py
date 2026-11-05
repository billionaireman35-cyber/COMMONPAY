import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "CommonPay")
    environment: str = os.getenv("APP_ENV", "development")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    api_prefix: str = os.getenv("API_V1_PREFIX", "/api/v1")
    api_key: str = os.getenv("COMMONPAY_API_KEY", "")

    flutterwave_secret_key: str = os.getenv("FLUTTERWAVE_SECRET_KEY", "")
    flutterwave_webhook_hash: str = os.getenv("FLUTTERWAVE_WEBHOOK_HASH", "")

    paystack_secret_key: str = os.getenv("PAYSTACK_SECRET_KEY", "")

    ai_provider: str = os.getenv("AI_PROVIDER", "")
    ai_api_key: str = os.getenv("AI_API_KEY", "")
    ai_model: str = os.getenv("AI_MODEL", "")

    payments_enabled: bool = os.getenv(
        "PAYMENTS_ENABLED", "false"
    ).lower() == "true"

    live_payments_enabled: bool = os.getenv(
        "PAYMENTS_LIVE_ENABLED", "false"
    ).lower() == "true"

    wallets_live_enabled: bool = os.getenv(
        "CUSTOMER_WALLETS_LIVE_ENABLED", "false"
    ).lower() == "true"

    frontend_origins: tuple[str, ...] = tuple(
        item.strip()
        for item in os.getenv(
            "FRONTEND_ORIGINS",
            "http://localhost:5174"
        ).split(",")
        if item.strip()
    )


settings = Settings()
