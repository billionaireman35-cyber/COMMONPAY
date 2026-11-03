from decimal import Decimal

import pytest

from app.domain.money import Money
from app.domain.payments import PaymentIntent, PaymentStatus
from app.domain.ledger import JournalEntry, Posting, EntrySide
from app.domain.idempotency import (
    IdempotencyKey,
    payment_request_fingerprint,
)
from app.core.exceptions import (
    FinancialInvariantViolation,
    InvalidPayment,
    InvalidStateTransition,
)


def create_payment():
    return PaymentIntent.create(
        amount=Decimal("100.00"),
        currency="NGN",
        customer_email="customer@example.com",
        provider="paystack",
        description="Test payment",
    )


def test_payment_starts_in_created_state():
    payment = create_payment()
    assert payment.status == PaymentStatus.CREATED


def test_payment_can_transition_to_pending():
    payment = create_payment()
    updated = payment.transition(PaymentStatus.PENDING)

    assert updated.status == PaymentStatus.PENDING
    assert payment.status == PaymentStatus.CREATED


def test_payment_can_complete_from_pending():
    payment = create_payment()
    payment = payment.transition(PaymentStatus.PENDING)
    payment = payment.transition(PaymentStatus.COMPLETED)

    assert payment.status == PaymentStatus.COMPLETED


def test_completed_payment_can_be_reversed():
    payment = create_payment()
    payment = payment.transition(PaymentStatus.PENDING)
    payment = payment.transition(PaymentStatus.COMPLETED)
    payment = payment.transition(PaymentStatus.REVERSED)

    assert payment.status == PaymentStatus.REVERSED


def test_completed_payment_cannot_return_to_pending():
    payment = create_payment()
    payment = payment.transition(PaymentStatus.PENDING)
    payment = payment.transition(PaymentStatus.COMPLETED)

    with pytest.raises(InvalidStateTransition):
        payment.transition(PaymentStatus.PENDING)


def test_failed_payment_is_terminal():
    payment = create_payment()
    payment = payment.transition(PaymentStatus.FAILED)

    assert payment.is_terminal

    with pytest.raises(InvalidStateTransition):
        payment.transition(PaymentStatus.PENDING)


def test_zero_payment_is_rejected():
    with pytest.raises(InvalidPayment):
        PaymentIntent.create(
            Decimal("0"),
            "NGN",
            "customer@example.com",
            "paystack",
            "Test payment",
        )


def test_currency_is_normalized():
    assert Money("10.00", "ngn").currency == "NGN"


def test_stable_idempotency_fingerprint():
    first = payment_request_fingerprint(
        Decimal("100.00"),
        "NGN",
        "CUSTOMER@example.com",
        "PAYSTACK",
        "Test payment",
    )

    second = payment_request_fingerprint(
        Decimal("100.00"),
        "ngn",
        "customer@example.com",
        "paystack",
        "Test payment",
    )

    assert first == second


def test_different_payment_requests_have_different_fingerprints():
    first = payment_request_fingerprint(
        Decimal("100"),
        "NGN",
        "customer@example.com",
        "paystack",
        "Test payment",
    )

    second = payment_request_fingerprint(
        Decimal("200"),
        "NGN",
        "customer@example.com",
        "paystack",
        "Test payment",
    )

    assert first != second


def test_idempotency_key_validation():
    assert IdempotencyKey("request-123").value == "request-123"

    with pytest.raises(ValueError):
        IdempotencyKey("short")


def test_journal_rejects_same_account_on_both_sides():
    with pytest.raises(FinancialInvariantViolation):
        JournalEntry.create(
            "Invalid journal",
            [
                Posting(
                    "cash",
                    EntrySide.DEBIT,
                    Money("100", "NGN"),
                ),
                Posting(
                    "cash",
                    EntrySide.CREDIT,
                    Money("100", "NGN"),
                ),
            ],
        )


def test_journal_requires_both_sides_per_currency():
    with pytest.raises(FinancialInvariantViolation):
        JournalEntry.create(
            "Invalid journal",
            [
                Posting(
                    "cash",
                    EntrySide.DEBIT,
                    Money("100", "NGN"),
                ),
                Posting(
                    "other_account",
                    EntrySide.CREDIT,
                    Money("100", "USD"),
                ),
            ],
        )


def test_journal_rejects_zero_posting():
    with pytest.raises(FinancialInvariantViolation):
        Posting(
            "cash",
            EntrySide.DEBIT,
            Money("0", "NGN"),
        )
