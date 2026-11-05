from fastapi import APIRouter, Header, HTTPException, Request

from app.services.webhook_security import (
    verify_paystack_signature,
    verify_flutterwave_signature,
)
from mirror.runtime import get_store
from mirror.webhook_ingest import ingest

router = APIRouter(prefix="/webhooks", tags=["Provider Webhooks"])


def _record(provider: str, raw_body: bytes) -> None:
    try:
        ingest(get_store(), provider, raw_body)
    except Exception:
        # Storage failed: 5xx makes the provider retry delivery.
        raise HTTPException(status_code=503, detail="Event storage unavailable.")


@router.post("/paystack")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str | None = Header(default=None),
):
    raw_body = await request.body()

    if not verify_paystack_signature(raw_body, x_paystack_signature):
        raise HTTPException(status_code=401, detail="Invalid signature.")

    _record("paystack", raw_body)
    # Recorded as a signal only. Confirmation requires provider verification
    # and reconciliation (python -m mirror.sweep).
    return {"received": True, "processed": False}


@router.post("/flutterwave")
async def flutterwave_webhook(
    request: Request,
    flutterwave_signature: str | None = Header(default=None),
    verif_hash: str | None = Header(default=None),
):
    raw_body = await request.body()
    signature = flutterwave_signature or verif_hash

    if not verify_flutterwave_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature.")

    _record("flutterwave", raw_body)
    return {"received": True, "processed": False}
