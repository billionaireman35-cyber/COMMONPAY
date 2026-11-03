import hashlib
import hmac
from types import SimpleNamespace

from app.services import webhook_security


def test_paystack_signature_logic(monkeypatch):
    monkeypatch.setattr(
        webhook_security,
        "settings",
        SimpleNamespace(paystack_secret_key="test-secret"),
    )

    body = b'{"event":"charge.success"}'

    signature = hmac.new(
        b"test-secret",
        body,
        hashlib.sha512,
    ).hexdigest()

    assert webhook_security.verify_paystack_signature(
        body, signature
    )

    assert not webhook_security.verify_paystack_signature(
        body, "incorrect"
    )


def test_paystack_signature_rejects_missing_signature(monkeypatch):
    monkeypatch.setattr(
        webhook_security,
        "settings",
        SimpleNamespace(paystack_secret_key="test-secret"),
    )

    assert not webhook_security.verify_paystack_signature(
        b'{"event":"charge.success"}',
        None,
    )


def test_paystack_signature_rejects_missing_secret(monkeypatch):
    monkeypatch.setattr(
        webhook_security,
        "settings",
        SimpleNamespace(paystack_secret_key=""),
    )

    assert not webhook_security.verify_paystack_signature(
        b'{"event":"charge.success"}',
        "some-signature",
    )
