from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from app.domain.money import Money
from app.core.exceptions import FinancialInvariantViolation


class EntrySide(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


@dataclass(frozen=True)
class Posting:
    account_id: str
    side: EntrySide
    money: Money

    def __post_init__(self):
        if not isinstance(self.account_id, str) or not self.account_id.strip():
            raise FinancialInvariantViolation(
                "Every posting requires a valid account."
            )

        if not isinstance(self.side, EntrySide):
            raise FinancialInvariantViolation(
                "Posting must have a valid debit or credit side."
            )

        if not isinstance(self.money, Money):
            raise FinancialInvariantViolation(
                "Posting requires a valid Money amount."
            )

        if self.money.amount <= Decimal("0"):
            raise FinancialInvariantViolation(
                "Posting amounts must be positive."
            )


@dataclass(frozen=True)
class JournalEntry:
    reference: str
    description: str
    postings: tuple[Posting, ...]

    @classmethod
    def create(cls, description: str, postings: list[Posting]):
        entry = cls(
            reference=str(uuid4()),
            description=description,
            postings=tuple(postings),
        )
        entry.validate()
        return entry

    def validate(self):
        if not self.reference:
            raise FinancialInvariantViolation(
                "Journal reference is required."
            )

        if not self.description or not self.description.strip():
            raise FinancialInvariantViolation(
                "Journal description is required."
            )

        if len(self.postings) < 2:
            raise FinancialInvariantViolation(
                "A journal requires at least two postings."
            )

        if len({p.account_id for p in self.postings}) < 2:
            raise FinancialInvariantViolation(
                "A journal must involve at least two distinct accounts."
            )

        totals = {}

        for posting in self.postings:
            if not isinstance(posting, Posting):
                raise FinancialInvariantViolation(
                    "Journal contains an invalid posting."
                )

            currency = posting.money.currency

            totals.setdefault(
                currency,
                {
                    "debit": Decimal("0"),
                    "credit": Decimal("0"),
                },
            )

            key = posting.side.value.lower()
            totals[currency][key] += posting.money.amount

        for currency, values in totals.items():
            if values["debit"] <= 0 or values["credit"] <= 0:
                raise FinancialInvariantViolation(
                    f"Journal requires debits and credits for {currency}."
                )

            if values["debit"] != values["credit"]:
                raise FinancialInvariantViolation(
                    f"Unbalanced journal for {currency}."
                )

        return True
