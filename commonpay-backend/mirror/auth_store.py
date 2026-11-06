import time
import uuid

from sqlalchemy import Column, Float, Integer, String, Table, text

from mirror.store import Store, metadata

Table("auth_users", metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("uid", String(32), nullable=False, unique=True),
      Column("email", String(255), nullable=False, unique=True),
      Column("login_pin_hash", String(200)),
      Column("txn_pin_hash", String(200)),
      Column("login_fails", Integer, nullable=False),
      Column("login_locked_until", Float, nullable=False),
      Column("txn_fails", Integer, nullable=False),
      Column("txn_locked_until", Float, nullable=False),
      Column("created_at", Float, nullable=False))

Table("auth_codes", metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("email", String(255), nullable=False, index=True),
      Column("code_hash", String(64), nullable=False),
      Column("expires_at", Float, nullable=False),
      Column("attempts", Integer, nullable=False),
      Column("used", Integer, nullable=False),
      Column("created_at", Float, nullable=False))

Table("auth_devices", metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("user_id", Integer, nullable=False, index=True),
      Column("token_hash", String(64), nullable=False, unique=True),
      Column("name", String(100)),
      Column("created_at", Float, nullable=False),
      Column("last_used_at", Float),
      Column("revoked", Integer, nullable=False))

Table("auth_sessions", metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("user_id", Integer, nullable=False, index=True),
      Column("token_hash", String(64), nullable=False, unique=True),
      Column("created_at", Float, nullable=False),
      Column("expires_at", Float, nullable=False),
      Column("verified_at", Float))


Table("saved_accounts", metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("user_uid", String(40), nullable=False, index=True),
      Column("account_number", String(20), nullable=False),
      Column("bank_code", String(16), nullable=False),
      Column("bank_name", String(100)),
      Column("account_name", String(255), nullable=False),
      Column("created_at", Float, nullable=False))


class AuthStore(Store):
    # --- users ---
    def get_user(self, uid):
        return self._one("SELECT * FROM auth_users WHERE id=:i", i=uid)

    def get_user_by_email(self, email):
        return self._one("SELECT * FROM auth_users WHERE email=:e", e=email)

    def get_or_create_user(self, email):
        self._exec(
            "INSERT INTO auth_users(uid,email,login_fails,login_locked_until,txn_fails,"
            "txn_locked_until,created_at) VALUES(:u,:e,0,0,0,0,:t) ON CONFLICT (email) DO NOTHING",
            u=uuid.uuid4().hex, e=email, t=time.time())
        return self.get_user_by_email(email)

    def set_pins(self, uid, login_hash, txn_hash):
        self._exec(
            "UPDATE auth_users SET login_pin_hash=:l, txn_pin_hash=:x, login_fails=0, "
            "login_locked_until=0, txn_fails=0, txn_locked_until=0 WHERE id=:i",
            l=login_hash, x=txn_hash, i=uid)

    def record_failure(self, uid, kind, limit, base_secs, now=None):
        assert kind in ("login", "txn")
        now = now or time.time()
        self._exec(f"UPDATE auth_users SET {kind}_fails={kind}_fails+1 WHERE id=:i", i=uid)
        fails = self.get_user(uid)[f"{kind}_fails"]
        if fails >= limit:
            secs = min(base_secs * (2 ** min(fails - limit, 20)), 86400)
            self._exec(f"UPDATE auth_users SET {kind}_locked_until=:l WHERE id=:i", l=now + secs, i=uid)
        return fails

    def record_success(self, uid, kind):
        assert kind in ("login", "txn")
        self._exec(f"UPDATE auth_users SET {kind}_fails=0, {kind}_locked_until=0 WHERE id=:i", i=uid)

    # --- email codes ---
    def add_code(self, email, code_hash, ttl, now=None):
        now = now or time.time()
        with self.engine.begin() as c:
            c.execute(text("UPDATE auth_codes SET used=1 WHERE email=:e AND used=0"), {"e": email})
            c.execute(text(
                "INSERT INTO auth_codes(email,code_hash,expires_at,attempts,used,created_at) "
                "VALUES(:e,:h,:x,0,0,:t)"), {"e": email, "h": code_hash, "x": now + ttl, "t": now})

    def codes_since(self, email, since):
        return self._one("SELECT COUNT(*) AS n FROM auth_codes WHERE email=:e AND created_at>=:s",
                         e=email, s=since)["n"]

    def codes_since_all(self, since):
        return self._one("SELECT COUNT(*) AS n FROM auth_codes WHERE created_at>=:s", s=since)["n"]

    def active_code(self, email, now):
        return self._one("SELECT * FROM auth_codes WHERE email=:e AND used=0 AND expires_at>:n "
                         "ORDER BY id DESC LIMIT 1", e=email, n=now)

    def code_attempt(self, cid):
        self._exec("UPDATE auth_codes SET attempts=attempts+1 WHERE id=:i", i=cid)
        return self._one("SELECT attempts FROM auth_codes WHERE id=:i", i=cid)["attempts"]

    def code_use(self, cid):
        self._exec("UPDATE auth_codes SET used=1 WHERE id=:i", i=cid)

    # --- devices and sessions ---
    def add_device(self, uid, token_hash, name):
        self._exec("INSERT INTO auth_devices(user_id,token_hash,name,created_at,last_used_at,revoked) "
                   "VALUES(:u,:h,:n,:t,:t,0)", u=uid, h=token_hash, n=name, t=time.time())

    def device_by_hash(self, token_hash):
        return self._one("SELECT * FROM auth_devices WHERE token_hash=:h AND revoked=0", h=token_hash)

    def touch_device(self, did, now):
        self._exec("UPDATE auth_devices SET last_used_at=:t WHERE id=:i", t=now, i=did)

    def add_session(self, uid, token_hash, ttl, verified_at=None, now=None):
        now = now or time.time()
        self._exec("INSERT INTO auth_sessions(user_id,token_hash,created_at,expires_at,verified_at) "
                   "VALUES(:u,:h,:c,:x,:v)", u=uid, h=token_hash, c=now, x=now + ttl, v=verified_at)

    def session_by_hash(self, token_hash, now):
        return self._one(
            "SELECT s.verified_at AS verified_at, u.* FROM auth_sessions s "
            "JOIN auth_users u ON u.id=s.user_id WHERE s.token_hash=:h AND s.expires_at>:n",
            h=token_hash, n=now)

    def delete_session(self, token_hash):
        self._exec("DELETE FROM auth_sessions WHERE token_hash=:h", h=token_hash)

    def purge(self, now):
        self._exec("DELETE FROM auth_sessions WHERE expires_at<:n", n=now)
        self._exec("DELETE FROM auth_codes WHERE created_at<:n", n=now - 172800)

    # --- saved accounts (name-verified bank accounts a user keeps; never holds money) ---
    def list_accounts(self, user_uid):
        return self._all("SELECT id,account_number,bank_code,bank_name,account_name FROM saved_accounts "
                         "WHERE user_uid=:u ORDER BY id", u=user_uid)

    def count_accounts(self, user_uid):
        return self._one("SELECT COUNT(*) AS n FROM saved_accounts WHERE user_uid=:u", u=user_uid)["n"]

    def find_account(self, user_uid, number, bank):
        return self._one("SELECT id,account_number,bank_code,bank_name,account_name FROM saved_accounts "
                         "WHERE user_uid=:u AND account_number=:a AND bank_code=:b", u=user_uid, a=number, b=bank)

    def add_account(self, user_uid, number, bank, bank_name, account_name):
        self._exec("INSERT INTO saved_accounts(user_uid,account_number,bank_code,bank_name,account_name,created_at) "
                   "VALUES(:u,:a,:b,:n,:m,:t)", u=user_uid, a=number, b=bank, n=bank_name, m=account_name,
                   t=time.time())
        return self.find_account(user_uid, number, bank)

    def remove_account(self, user_uid, account_id):
        return self._exec("DELETE FROM saved_accounts WHERE id=:i AND user_uid=:u", i=account_id, u=user_uid)
