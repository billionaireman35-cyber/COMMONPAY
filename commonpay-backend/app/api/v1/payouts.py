import hashlib
import re
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import check_txn_pin, get_auth_store, require_user
from mirror.payout import AccountNotFound, InsufficientFunds

router = APIRouter(
    prefix="/payouts",
    tags=["Payouts"],
    dependencies=[Depends(require_user)],
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
    allow_repeat: bool = False


def _fingerprint(rows):
    parts = []
    for r in rows:
        try:
            amt = format(r.amount.quantize(Decimal("0.01")), "f")
        except Exception:
            amt = str(r.amount)
        parts.append(f"{r.account_number.strip()}|{r.bank_code.strip()}|{amt}")
    parts.sort()
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _mine(engine, key, user):
    """The batch, only if it belongs to this user. Anyone else's looks like 'not found'."""
    b = engine.store.get_batch(key)
    if b is None or engine.store.owner_of(key) != user["uid"]:
        raise HTTPException(status_code=404, detail="batch not found")
    return b


# Plain defs: FastAPI runs them in a threadpool, so blocking DB/provider calls
# do not stall the event loop.
@router.post("/batches")
def create_batch(body: BatchIn, engine=Depends(get_engine), user=Depends(require_user)):
    store = engine.store
    uid = user["uid"]
    fp = _fingerprint(body.rows)
    existing = store.get_batch(body.batch_key)
    if existing is not None:
        if store.owner_of(body.batch_key) != uid:
            raise HTTPException(status_code=409, detail="batch_key already used")
        old = store.fingerprint_of(body.batch_key)
        if (old is not None and old != fp) or (
                old is None and len(store.items(existing["id"])) != len(body.rows)):
            raise HTTPException(status_code=409, detail="batch_key already used with different rows")
    elif not body.allow_repeat:
        dupes = store.sent_batches_for_owner(fp, body.batch_key, uid)
        if dupes:
            raise HTTPException(
                status_code=409,
                detail=f"duplicate-list: This exact list (same accounts and amounts) was already sent "
                       f"in batch {dupes[0]}. Uploading it again would pay everyone twice.")
    engine.load(body.batch_key, [r.model_dump() for r in body.rows], body.currency)
    store.set_owner(body.batch_key, uid)
    store.add_fingerprint(fp, body.batch_key)
    return {"batch_key": body.batch_key, "created": existing is None,
            "summary": engine.summary(body.batch_key)}


@router.post("/batches/{key}/run")
def run_batch(key: str, preferred: str | None = None,
              x_transaction_pin: str | None = Header(default=None),
              engine=Depends(get_engine), user=Depends(require_user), auth=Depends(get_auth_store)):
    _mine(engine, key, user)
    check_txn_pin(auth, user, x_transaction_pin)
    try:
        return {"summary": engine.run(key, preferred)}
    except InsufficientFunds as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/batches/{key}/refresh")
def refresh_batch(key: str, engine=Depends(get_engine), user=Depends(require_user)):
    _mine(engine, key, user)
    return {"summary": engine.refresh(key)}


@router.get("/batches/{key}")
def get_batch(key: str, engine=Depends(get_engine), user=Depends(require_user)):
    b = _mine(engine, key, user)
    return {"batch_key": key, "currency": b["currency"],
            "summary": engine.summary(key), "items": engine.report(key)}


@router.post("/batches/{key}/verify")
def verify_batch(key: str, engine=Depends(get_engine), user=Depends(require_user)):
    _mine(engine, key, user)
    engine.verify_names(key)  # resolves names only; never sends
    return {"summary": engine.summary(key), "items": engine.report(key)}


@router.get("/banks")
def banks(engine=Depends(get_engine)):
    for rail in engine.rails:
        if hasattr(rail, "banks"):
            try:
                return {"banks": rail.banks()}
            except Exception:
                continue
    return {"banks": []}


@router.get("/resolve")
def resolve(account_number: str, bank_code: str, engine=Depends(get_engine)):
    if not re.fullmatch(r"\d{10}", account_number) or not bank_code:
        raise HTTPException(status_code=422, detail="Enter a 10-digit account number and choose a bank.")
    try:
        name = engine._resolve({"account_number": account_number, "bank_code": bank_code})
    except AccountNotFound:
        raise HTTPException(status_code=404, detail="Account not found.")
    if name is None:
        raise HTTPException(status_code=503, detail="Could not reach the bank lookup. Try again.")
    return {"account_name": name}
