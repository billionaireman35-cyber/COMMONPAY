from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "CommonPay",
        "database": "not_connected",
        "live_payments": False,
    }
