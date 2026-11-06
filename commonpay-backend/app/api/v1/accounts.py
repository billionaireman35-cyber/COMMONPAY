from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.payouts import get_engine
from app.core.auth import get_auth_store, require_user
from mirror.payout import AccountNotFound

router = APIRouter(prefix="/accounts", tags=["Accounts"], dependencies=[Depends(require_user)])

MAX_ACCOUNTS = 20


class AccountIn(BaseModel):
    account_number: str = Field(pattern=r"^\d{10}$")
    bank_code: str = Field(min_length=1, max_length=16)
    bank_name: str = Field(default="", max_length=100)


def _out(r):
    return {"id": r["id"], "account_number": r["account_number"], "bank_code": r["bank_code"],
            "bank_name": r["bank_name"] or "", "account_name": r["account_name"]}


@router.get("")
def list_accounts(user=Depends(require_user), store=Depends(get_auth_store)):
    return {"accounts": [_out(r) for r in store.list_accounts(user["uid"])]}


@router.post("")
def add_account(body: AccountIn, engine=Depends(get_engine), user=Depends(require_user),
                store=Depends(get_auth_store)):
    uid = user["uid"]
    existing = store.find_account(uid, body.account_number, body.bank_code)
    if existing:
        return {"account": _out(existing)}
    if store.count_accounts(uid) >= MAX_ACCOUNTS:
        raise HTTPException(status_code=409, detail=f"You can save up to {MAX_ACCOUNTS} accounts. Remove one first.")
    try:
        name = engine._resolve({"account_number": body.account_number, "bank_code": body.bank_code})
    except AccountNotFound:
        raise HTTPException(status_code=404, detail="Account not found. Check the number and bank.")
    if not name:
        raise HTTPException(status_code=503, detail="Could not reach the bank lookup. Try again.")
    row = store.add_account(uid, body.account_number, body.bank_code, body.bank_name, name)
    return {"account": _out(row)}


# POST, not DELETE: the server's CORS rules only allow GET and POST.
@router.post("/{account_id}/remove")
def remove_account(account_id: int, user=Depends(require_user), store=Depends(get_auth_store)):
    if not store.remove_account(user["uid"], account_id):
        raise HTTPException(status_code=404, detail="Account not found.")
    return {"ok": True}
