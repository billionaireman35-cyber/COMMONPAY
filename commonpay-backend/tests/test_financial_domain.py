from decimal import Decimal
import pytest

from app.domain.money import Money
from app.domain.ledger import JournalEntry, Posting, EntrySide
from app.core.exceptions import FinancialInvariantViolation


def test_money_uses_decimal():
    money = Money(Decimal("100.25"), "NGN")
    assert money.amount == Decimal("100.25")


def test_money_rejects_excess_precision():
    with pytest.raises(ValueError):
        Money(Decimal("1.234"), "NGN")


def test_balanced_journal():
    entry = JournalEntry.create(
        "Test deposit",
        [
            Posting("cash", EntrySide.DEBIT, Money("100", "NGN")),
            Posting("customer_liability", EntrySide.CREDIT, Money("100", "NGN")),
        ],
    )
    assert entry.validate()


def test_unbalanced_journal_rejected():
    with pytest.raises(FinancialInvariantViolation):
        JournalEntry.create(
            "Invalid journal",
            [
                Posting("cash", EntrySide.DEBIT, Money("100", "NGN")),
                Posting("liability", EntrySide.CREDIT, Money("90", "NGN")),
            ],
        )


def test_currency_mismatch_rejected():
    with pytest.raises(ValueError):
        Money("10", "NGN") + Money("10", "USD")
