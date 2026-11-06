import hmac
import time

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_api_key(
    x_commonpay_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    # A signed-in user's session is accepted here too, so the app never needs the shared key.
    if authorization and authorization.lower().startswith("bearer "):
        from app.core.auth import get_auth_store, token_hash
        s = get_auth_store().session_by_hash(token_hash(authorization[7:].strip()), time.time())
        if s is not None:
            return True
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="session-expired: Please sign in again.")

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
