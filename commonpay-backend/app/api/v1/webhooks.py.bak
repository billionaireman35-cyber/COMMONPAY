from fastapi import APIRouter, Header, HTTPException, Request

from app.services.webhook_security import (
    verify_paystack_signature,
    verify_flutterwave_signature,
)

router = APIRouter(prefix="/webhooks", tags=["Provider Webhooks"])


@router.post("/paystack")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str | None = Header(default=None),
):
    raw_body = await request.body()

    if not verify_paystack_signature(raw_body, x_paystack_signature):
        raise HTTPException(status_code=401, detail="Invalid signature.")

    # Intentionally no financial posting here.
    # Production processing requires durable event storage,
    # provider verification, idempotency and reconciliation.
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

    return {"received": True, "processed": False}
