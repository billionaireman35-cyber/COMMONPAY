from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.schemas import CheckoutRequest
from app.core.security import require_api_key
from app.services.payment_orchestrator import create_checkout

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
    dependencies=[Depends(require_api_key)],
)


@router.post("/checkout")
async def checkout(request: CheckoutRequest):
    try:
        return await create_checkout(
            amount=request.amount,
            currency=request.currency,
            email=str(request.customer_email),
            provider_name=request.provider,
            description=request.description,
            callback_url=request.callback_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        # Do not expose provider credentials or raw upstream responses.
        raise HTTPException(
            status_code=502,
            detail=f"Payment provider operation failed: {type(exc).__name__}",
        )
