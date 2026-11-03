from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


CURRENCY_PRECISION = {
    "NGN": 2,
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "USDC": 6,
    "USDT": 6,
}


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self):
        if not isinstance(self.currency, str):
            raise ValueError("Currency must be a string.")

        currency = self.currency.strip().upper()

        if currency not in CURRENCY_PRECISION:
            raise ValueError(f"Unsupported currency: {currency}")

        try:
            amount = Decimal(str(self.amount))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("Invalid monetary amount.") from None

        if not amount.is_finite():
            raise ValueError("Amount must be finite.")

        precision = CURRENCY_PRECISION[currency]

        try:
            normalized = amount.quantize(
                Decimal(1).scaleb(-precision)
            )
        except InvalidOperation:
            raise ValueError("Monetary amount is outside supported limits.") from None

        if normalized != amount:
            raise ValueError("Amount exceeds currency precision.")

        object.__setattr__(self, "amount", normalized)
        object.__setattr__(self, "currency", currency)

    def __add__(self, other):
        if not isinstance(other, Money):
            return NotImplemented

        if self.currency != other.currency:
            raise ValueError("Currency mismatch.")

        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other):
        if not isinstance(other, Money):
            return NotImplemented

        if self.currency != other.currency:
            raise ValueError("Currency mismatch.")

        return Money(self.amount - other.amount, self.currency)

    def is_positive(self) -> bool:
        return self.amount > Decimal("0")

    def is_zero(self) -> bool:
        return self.amount == Decimal("0")

    def __str__(self):
        return f"{self.amount:.{CURRENCY_PRECISION[self.currency]}f} {self.currency}"
