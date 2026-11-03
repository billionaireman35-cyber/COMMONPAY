import hmac

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_api_key(
    x_commonpay_api_key: str | None = Header(default=None),
):
    if not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured.",
        )

    if not x_commonpay_api_key or not hmac.compare_digest(
        x_commonpay_api_key,
        settings.api_key,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API credentials.",
        )

    return True
