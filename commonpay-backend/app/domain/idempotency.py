import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class IdempotencyKey:
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str):
            raise ValueError("Idempotency key must be a string.")

        value = self.value.strip()

        if not 8 <= len(value) <= 255:
            raise ValueError(
                "Idempotency key must contain between 8 and 255 characters."
            )

        object.__setattr__(self, "value", value)


def payment_request_fingerprint(
    amount: Decimal,
    currency: str,
    customer_email: str,
    provider: str,
    description: str,
) -> str:
    """
    Produce a deterministic fingerprint for a payment request.

    Persistent idempotency enforcement and concurrency protection
    will be implemented using database constraints in a later phase.
    """

    normalized_amount = Decimal(str(amount))

    if not normalized_amount.is_finite():
        raise ValueError("Amount must be finite.")

    payload = {
        "amount": format(normalized_amount, "f"),
        "currency": currency.strip().upper(),
        "customer_email": customer_email.strip().lower(),
        "provider": provider.strip().lower(),
        "description": description.strip(),
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
