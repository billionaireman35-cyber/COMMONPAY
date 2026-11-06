from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import require_api_key
from mirror.payout import InsufficientFunds

router = APIRouter(
    prefix="/payouts",
    tags=["Payouts"],
    dependencies=[Depends(require_api_key)],
)


def get_engine():
    from mirror.payout_runtime import get_live_engine
    eng = get_live_engine()
    if eng is None:
        raise HTTPException(status_code=503, detail="Payouts are not enabled.")
    return eng


class RowIn(BaseModel):
    name: str = Field(default="", max_length=255)
    account_number: str = Field(max_length=20)
    bank_code: str = Field(max_length=16)
    amount: Decimal


class BatchIn(BaseModel):
    batch_key: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._-]+$")
    currency: str = Field(default="NGN", max_length=8)
    rows: list[RowIn] = Field(min_length=1, max_length=5000)


def _batch(engine, key):
    b = engine.store.get_batch(key)
    if b is None:
        raise HTTPException(status_code=404, detail="batch not found")
    return b


# Plain defs: FastAPI runs them in a threadpool, so blocking DB/provider calls
# do not stall the event loop.
@router.post("/batches")
def create_batch(body: BatchIn, engine=Depends(get_engine)):
    existing = engine.store.get_batch(body.batch_key)
    if existing is not None and len(engine.store.items(existing["id"])) != len(body.rows):
        raise HTTPException(status_code=409, detail="batch_key already used with different rows")
    engine.load(body.batch_key, [r.model_dump() for r in body.rows], body.currency)
    return {"batch_key": body.batch_key, "created": existing is None,
            "summary": engine.summary(body.batch_key)}


@router.post("/batches/{key}/run")
def run_batch(key: str, preferred: str | None = None, engine=Depends(get_engine)):
    _batch(engine, key)
    try:
        return {"summary": engine.run(key, preferred)}
    except InsufficientFunds as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/batches/{key}/refresh")
def refresh_batch(key: str, engine=Depends(get_engine)):
    _batch(engine, key)
    return {"summary": engine.refresh(key)}


@router.get("/batches/{key}")
def get_batch(key: str, engine=Depends(get_engine)):
    b = _batch(engine, key)
    return {"batch_key": key, "currency": b["currency"],
            "summary": engine.summary(key), "items": engine.report(key)}


@router.post("/batches/{key}/verify")
def verify_batch(key: str, engine=Depends(get_engine)):
    _batch(engine, key)
    engine.verify_names(key)  # resolves names only; never sends
    return {"summary": engine.summary(key), "items": engine.report(key)}
