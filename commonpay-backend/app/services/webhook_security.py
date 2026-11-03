import hashlib
import hmac

from app.core.config import settings


def verify_paystack_signature(raw_body: bytes, signature: str | None) -> bool:
    secret = settings.paystack_secret_key

    if not secret or not signature:
        return False

    expected = hmac.new(
        secret.encode(),
        raw_body,
        hashlib.sha512,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def verify_flutterwave_signature(
    raw_body: bytes,
    signature: str | None,
) -> bool:
    secret = settings.flutterwave_webhook_hash

    if not secret or not signature:
        return False

    # Flutterwave v4 HMAC-SHA256 signature.
    expected = hmac.new(
        secret.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if hmac.compare_digest(expected, signature):
        return True

    # Flutterwave v3 verif-hash shared-secret header.
    return hmac.compare_digest(secret, signature)
