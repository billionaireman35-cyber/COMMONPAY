from fastapi import APIRouter, Depends

from app.core.security import require_api_key

router = APIRouter(
    prefix="/developers",
    tags=["Developer Infrastructure"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/capabilities")
async def capabilities():
    return {
        "platform": "CommonPay",
        "api_version": "v1",
        "capabilities": [
            "payment_checkout",
            "payment_verification_planned",
            "webhooks",
            "financial_reporting_planned",
            "business_integrations",
        ],
        "providers": ["flutterwave", "paystack"],
        "sandbox": True,
        "live_money_movement": False,
    }
