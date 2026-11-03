from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from app.domain.money import Money
from app.core.exceptions import InvalidPayment, InvalidStateTransition


class PaymentStatus(str, Enum):
    CREATED = "CREATED"
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REVERSED = "REVERSED"


ALLOWED_TRANSITIONS = {
    PaymentStatus.CREATED: {
        PaymentStatus.PENDING,
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
    },
    PaymentStatus.PENDING: {
        PaymentStatus.PROCESSING,
        PaymentStatus.COMPLETED,
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
    },
    PaymentStatus.PROCESSING: {
        PaymentStatus.COMPLETED,
        PaymentStatus.FAILED,
    },
    PaymentStatus.COMPLETED: {
        PaymentStatus.REVERSED,
    },
    PaymentStatus.FAILED: set(),
    PaymentStatus.CANCELLED: set(),
    PaymentStatus.REVERSED: set(),
}


@dataclass(frozen=True)
class PaymentIntent:
    reference: str
    amount: Money
    customer_email: str
    provider: str
    description: str
    status: PaymentStatus = PaymentStatus.CREATED
    idempotency_key: str | None = None

    def __post_init__(self):
        if not self.reference or not self.reference.strip():
            raise InvalidPayment("Payment reference is required.")

        if not isinstance(self.amount, Money):
            raise InvalidPayment("A valid Money amount is required.")

        if not self.amount.is_positive():
            raise InvalidPayment("Payment amount must be positive.")

        if not self.customer_email or not self.customer_email.strip():
            raise InvalidPayment("Customer email is required.")

        if not self.provider or not self.provider.strip():
            raise InvalidPayment("Payment provider is required.")

        if not self.description or not self.description.strip():
            raise InvalidPayment("Payment description is required.")

        if not isinstance(self.status, PaymentStatus):
            raise InvalidPayment("Invalid payment status.")

    @classmethod
    def create(
        cls,
        amount: Decimal,
        currency: str,
        customer_email: str,
        provider: str,
        description: str,
        idempotency_key: str | None = None,
    ):
        return cls(
            reference=f"CP-{uuid4().hex}",
            amount=Money(amount, currency),
            customer_email=customer_email.strip(),
            provider=provider.strip().lower(),
            description=description.strip(),
            idempotency_key=idempotency_key,
        )

    def transition(self, new_status: PaymentStatus):
        if not isinstance(new_status, PaymentStatus):
            raise InvalidStateTransition("Invalid target payment status.")

        allowed = ALLOWED_TRANSITIONS[self.status]

        if new_status not in allowed:
            raise InvalidStateTransition(
                f"Cannot transition payment from "
                f"{self.status.value} to {new_status.value}."
            )

        return replace(self, status=new_status)

    @property
    def is_terminal(self) -> bool:
        return not ALLOWED_TRANSITIONS[self.status]
