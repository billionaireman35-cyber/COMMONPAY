import hmac
import os
import secrets
import time

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.core import auth as A
from app.core.auth import get_auth_store, require_user
from mirror.mailer import MailError, send_email

router = APIRouter(prefix="/auth", tags=["Auth"])

CODE_TTL = 600
SESSION_TTL = 12 * 3600
FRESH = 900


class EmailIn(BaseModel):
    email: EmailStr


class VerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")
    device_name: str = Field(default="", max_length=100)


class PinsIn(BaseModel):
    login_pin: str = Field(pattern=r"^\d{6}$")
    txn_pin: str = Field(pattern=r"^\d{4}$")


class LoginIn(BaseModel):
    device_token: str = Field(min_length=20, max_length=200)
    pin: str = Field(pattern=r"^\d{6}$")


def _weak(p):
    return len(set(p)) == 1 or p in "0123456789" or p in "9876543210"


@router.post("/request-code")
def request_code(body: EmailIn, store=Depends(get_auth_store)):
    A.secret()
    email = str(body.email).strip().lower()
    now = time.time()
    if store.codes_since(email, now - 900) >= 3:
        raise HTTPException(status_code=429, detail="Too many codes requested. Please wait 15 minutes.")
    if store.codes_since_all(now - 86400) >= int(os.environ.get("AUTH_DAILY_CODE_CAP", "200")):
        raise HTTPException(status_code=503, detail="Sign-in emails are paused for today. Try again tomorrow.")
    code = f"{secrets.randbelow(10 ** 6):06d}"
    store.add_code(email, A.code_hash(email, code), CODE_TTL, now)
    try:
        send_email(email, "Your CommonPay code",
                   f"Your CommonPay verification code is {code}. It expires in 10 minutes. "
                   "If you did not ask for it, ignore this email.")
    except MailError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"sent": True}


@router.post("/verify-code")
def verify_code(body: VerifyIn, store=Depends(get_auth_store)):
    email = str(body.email).strip().lower()
    now = time.time()
    store.purge(now)
    bad = HTTPException(status_code=400, detail="That code is wrong or has expired.")
    rec = store.active_code(email, now)
    if rec is None:
        raise bad
    if not hmac.compare_digest(rec["code_hash"], A.code_hash(email, body.code)):
        if store.code_attempt(rec["id"]) >= 5:
            store.code_use(rec["id"])
        raise bad
    store.code_use(rec["id"])
    user = store.get_or_create_user(email)
    store.record_success(user["id"], "login")
    store.record_success(user["id"], "txn")
    device, session = A.new_token(), A.new_token()
    store.add_device(user["id"], A.token_hash(device), body.device_name or "device")
    store.add_session(user["id"], A.token_hash(session), SESSION_TTL, verified_at=now, now=now)
    return {"device_token": device, "session_token": session, "expires_in": SESSION_TTL,
            "has_pin": bool(user["login_pin_hash"])}


@router.post("/set-pins")
def set_pins(body: PinsIn, user=Depends(require_user), store=Depends(get_auth_store)):
    verified = user.get("verified_at")
    if not verified or time.time() - verified > FRESH:
        raise HTTPException(status_code=403, detail="Please confirm your email again before setting PINs.")
    if _weak(body.login_pin) or _weak(body.txn_pin):
        raise HTTPException(status_code=422, detail="Choose a PIN that is not repeated digits or a simple sequence.")
    if body.txn_pin in (body.login_pin[:4], body.login_pin[-4:]):
        raise HTTPException(status_code=422, detail="The transaction PIN must be different from your login PIN.")
    store.set_pins(user["id"], A.hash_pin(body.login_pin), A.hash_pin(body.txn_pin))
    return {"ok": True}


@router.post("/login")
def login(body: LoginIn, store=Depends(get_auth_store)):
    A.secret()
    now = time.time()
    dev = store.device_by_hash(A.token_hash(body.device_token))
    if dev is None:
        raise HTTPException(status_code=401, detail="device-unknown: This phone is not recognised. Sign in with your email.")
    u = store.get_user(dev["user_id"])
    if not u["login_pin_hash"]:
        raise HTTPException(status_code=401, detail="no-pin: Finish setting up your PINs with your email.")
    if u["login_locked_until"] > now:
        raise HTTPException(status_code=423, detail="locked: Too many wrong tries. Try again in "
                            + A.wait_text(u["login_locked_until"] - now) + ", or use Forgot PIN.")
    if not A.check_pin(body.pin, u["login_pin_hash"]):
        left = max(0, 5 - store.record_failure(u["id"], "login", 5, 900))
        raise HTTPException(status_code=401, detail="wrong-pin: Wrong PIN. " + (
            f"{left} tries left." if left else "Login is locked for a while."))
    store.record_success(u["id"], "login")
    store.touch_device(dev["id"], now)
    session = A.new_token()
    store.add_session(u["id"], A.token_hash(session), SESSION_TTL, now=now)
    return {"session_token": session, "expires_in": SESSION_TTL}


@router.get("/me")
def me(user=Depends(require_user)):
    return {"email": user["email"], "has_txn_pin": bool(user["txn_pin_hash"])}


@router.post("/logout")
def logout(authorization: str | None = Header(default=None), user=Depends(require_user),
           store=Depends(get_auth_store)):
    store.delete_session(A.token_hash(authorization[7:].strip()))
    return {"ok": True}
