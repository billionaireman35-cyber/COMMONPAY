import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from mirror.runtime import get_store

router = APIRouter(tags=["Health"])
logger = logging.getLogger(__name__)


@router.get("/health")
def health():
    try:
        with get_store().engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        logger.warning("Database health check failed.")
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "service": "CommonPay",
                "database": "disconnected",
                "live_payments": False,
            },
        )

    return {
        "status": "ok",
        "service": "CommonPay",
        "database": "connected",
        "live_payments": False,
    }
