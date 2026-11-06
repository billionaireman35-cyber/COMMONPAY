from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import require_api_key
from mirror.daily_close import build_close, today_wat
from mirror.locks import LockError, LockService
from mirror.partner import PartnerNotConfiguredError
from mirror.runtime import get_store

router = APIRouter(
    prefix="/trader",
    tags=["Trader"],
    dependencies=[Depends(require_api_key)],
)


class LockRequest(BaseModel):
    trader_id: str = "default"
    day: Optional[date] = None
    release_on: date
    amount_minor: Optional[int] = None
    percent_bps: Optional[int] = None
    currency: str = "NGN"


@router.get("/close/daily")
def daily_close(day: Optional[date] = None):
    d = day or today_wat()
    return build_close(get_store(), d, date.fromordinal(d.toordinal() + 1))


@router.get("/close/monthly")
def monthly_close(month: Optional[str] = None):
    try:
        if month:
            y, m = (int(x) for x in month.split("-"))
            first = date(y, m, 1)
        else:
            t = today_wat()
            first = date(t.year, t.month, 1)
    except ValueError:
        raise HTTPException(status_code=422, detail="month must look like 2026-11")
    nxt = date(first.year + (first.month // 12), first.month % 12 + 1, 1)
    return build_close(get_store(), first, nxt)


@router.post("/locks")
def create_lock(body: LockRequest):
    svc = LockService(get_store())
    try:
        row, created = svc.create_lock(
            body.trader_id, body.day or today_wat(), body.release_on,
            body.amount_minor, body.percent_bps, body.currency)
    except LockError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PartnerNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"created": created, "lock": dict(row)}


@router.get("/locks")
def list_locks(trader_id: str = "default"):
    return [dict(r) for r in LockService(get_store()).list_locks(trader_id)]


@router.post("/locks/release-due")
def release_due():
    try:
        ids = LockService(get_store()).release_due(today_wat())
    except PartnerNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"released_ids": ids}
