from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from app.core.exceptions import ProviderUnavailable


@dataclass(frozen=True)
class CheckoutResult:
    provider: str
    reference: str
    checkout_url: str
    provider_reference: str | None = None


@dataclass(frozen=True)
class ProviderVerificationResult:
    provider: str
    reference: str
    provider_reference: str | None
    status: str
    amount: Decimal
    currency: str
    raw_status: str | None = None


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    async def initialize_payment(
        self,
        reference: str,
        amount: Decimal,
        currency: str,
        customer_email: str,
        description: str,
        callback_url: str,
    ) -> CheckoutResult:
        raise NotImplementedError

    async def verify_transaction(
        self,
        reference: str,
        provider_reference: str | None = None,
    ) -> ProviderVerificationResult:
        """
        Provider-specific adapters must implement independent verification.

        This safe default deliberately prevents unsupported verification
        from being treated as successful.
        """
        raise ProviderUnavailable(
            f"{self.name} transaction verification is not implemented."
        )
