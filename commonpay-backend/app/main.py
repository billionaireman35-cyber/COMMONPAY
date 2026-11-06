from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1 import (
    health,
    payments,
    webhooks,
    intelligence,
    developers,
    reconciliation,
    locks,
    payouts,
)

app = FastAPI(
    title="CommonPay API",
    description=(
        "AI-powered Financial Command Centre and "
        "API-first financial infrastructure."
    ),
    version="0.1.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-CommonPay-API-Key", "X-Paystack-Signature",
                   "Flutterwave-Signature", "Verif-Hash", "Idempotency-Key"],
)

app.include_router(health.router)
app.include_router(payments.router, prefix=settings.api_prefix)
app.include_router(webhooks.router, prefix=settings.api_prefix)
app.include_router(intelligence.router, prefix=settings.api_prefix)
app.include_router(developers.router, prefix=settings.api_prefix)
app.include_router(reconciliation.router, prefix=settings.api_prefix)
app.include_router(locks.router, prefix=settings.api_prefix)
app.include_router(payouts.router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    return {
        "name": "CommonPay",
        "description": "Your money. Your control. One command centre.",
        "version": "0.1.0",
    }
