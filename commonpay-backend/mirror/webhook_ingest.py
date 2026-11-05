import json
from decimal import Decimal

def _minor(x):
    return None if x is None else int((Decimal(str(x)) * 100).to_integral_value())

def ingest(store, provider, raw_body):
    """Store a signature-verified webhook as a signal. True if new, False if duplicate/unusable."""
    try:
        body = json.loads(raw_body)
    except (ValueError, TypeError):
        return False
    if not isinstance(body, dict):
        return False
    d = body.get("data") or {}
    if provider == "paystack":
        ref, amt = d.get("reference"), d.get("amount")
        event = f"webhook.{body.get('event', 'unknown')}"
    elif provider == "flutterwave":
        ref, amt = d.get("tx_ref"), _minor(d.get("amount"))
        event = f"webhook.{body.get('event', 'unknown')}.{d.get('status', '')}".rstrip(".")
    else:
        return False
    if not ref:
        return False
    return store.add_event(provider, ref, event, amt, d.get("currency"))
