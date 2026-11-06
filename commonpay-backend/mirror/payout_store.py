import time
from sqlalchemy import BigInteger, Column, Float, Integer, String, Table, Text
from mirror.store import Store, metadata

Table("payout_batches", metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("batch_key", String(255), nullable=False, unique=True),
      Column("currency", String(8), nullable=False),
      Column("created_at", Float, nullable=False))

Table("payout_items", metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("batch_id", Integer, nullable=False),
      Column("idem_key", String(300), nullable=False, unique=True),
      Column("row_no", Integer, nullable=False),
      Column("account_number", String(20), nullable=False),
      Column("bank_code", String(16), nullable=False),
      Column("expected_name", String(255)),
      Column("resolved_name", String(255)),
      Column("amount_minor", BigInteger, nullable=False),
      Column("status", String(16), nullable=False),
      Column("provider", String(32)),
      Column("provider_ref", String(255)),
      Column("detail", Text),
      Column("created_at", Float, nullable=False),
      Column("updated_at", Float, nullable=False))

Table("payout_fingerprints", metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("fingerprint", String(64), nullable=False, index=True),
      Column("batch_key", String(255), nullable=False, unique=True),
      Column("created_at", Float, nullable=False))

Table("batch_owners", metadata,
      Column("batch_key", String(255), primary_key=True),
      Column("user_uid", String(40), nullable=False, index=True),
      Column("created_at", Float, nullable=False))

# Strict state machine. confirmed/failed/rejected are terminal.
# unknown is only ever resolved by asking the provider, never by re-sending.
ALLOWED = {
    "pending": {"sending", "rejected"},
    "sending": {"pending", "submitted", "unknown"},
    "submitted": {"confirmed", "failed", "unknown"},
    "unknown": {"confirmed", "failed", "submitted"},
    "confirmed": set(), "failed": set(), "rejected": set(),
}
_FIELDS = {"provider", "provider_ref", "detail", "resolved_name"}


class PayoutStore(Store):
    def create_batch(self, key, currency):
        n = self._exec(
            "INSERT INTO payout_batches(batch_key,currency,created_at) VALUES(:k,:c,:t) "
            "ON CONFLICT (batch_key) DO NOTHING", k=key, c=currency, t=time.time())
        return self.get_batch(key), n == 1

    def get_batch(self, key):
        return self._one("SELECT * FROM payout_batches WHERE batch_key=:k", k=key)

    def add_item(self, batch_id, idem_key, row_no, acct, bank, name, amount_minor, status, detail=""):
        now = time.time()
        self._exec(
            "INSERT INTO payout_items(batch_id,idem_key,row_no,account_number,bank_code,expected_name,"
            "amount_minor,status,detail,created_at,updated_at) "
            "VALUES(:b,:k,:r,:a,:bk,:n,:m,:s,:d,:t,:t) ON CONFLICT (idem_key) DO NOTHING",
            b=batch_id, k=idem_key, r=row_no, a=acct, bk=bank, n=name, m=amount_minor, s=status, d=detail, t=now)

    def items(self, batch_id):
        return self._all("SELECT * FROM payout_items WHERE batch_id=:b ORDER BY row_no", b=batch_id)

    def get_item(self, item_id):
        return self._one("SELECT * FROM payout_items WHERE id=:i", i=item_id)

    def set_fields(self, item_id, **f):
        cols = {k: v for k, v in f.items() if k in _FIELDS}
        if not cols:
            return
        sets = ",".join(f"{k}=:{k}" for k in cols)
        self._exec(f"UPDATE payout_items SET {sets},updated_at=:t WHERE id=:i", t=time.time(), i=item_id, **cols)

    def move(self, item_id, frm, to, **f):
        """Atomic compare-and-set transition. Returns False if the item is no longer in `frm`."""
        if to not in ALLOWED[frm]:
            raise ValueError(f"illegal payout transition {frm} -> {to}")
        cols = {k: v for k, v in f.items() if k in _FIELDS}
        sets = "".join(f",{k}=:{k}" for k in cols)
        return self._exec(
            f"UPDATE payout_items SET status=:to,updated_at=:t{sets} WHERE id=:i AND status=:frm",
            to=to, t=time.time(), i=item_id, frm=frm, **cols) == 1

    def add_fingerprint(self, fp, batch_key):
        self._exec("INSERT INTO payout_fingerprints(fingerprint,batch_key,created_at) "
                   "VALUES(:f,:b,:t) ON CONFLICT DO NOTHING", f=fp, b=batch_key, t=time.time())

    def fingerprint_of(self, batch_key):
        r = self._one("SELECT fingerprint FROM payout_fingerprints WHERE batch_key=:b", b=batch_key)
        return r["fingerprint"] if r else None

    def sent_batches_with(self, fp, exclude_key):
        """Other batches with this exact list where money may have moved."""
        rows = self._all(
            "SELECT f.batch_key FROM payout_fingerprints f "
            "JOIN payout_batches b ON b.batch_key=f.batch_key "
            "JOIN payout_items i ON i.batch_id=b.id "
            "WHERE f.fingerprint=:f AND f.batch_key<>:k "
            "AND i.status IN ('sending','submitted','confirmed','unknown') "
            "GROUP BY f.batch_key", f=fp, k=exclude_key)
        return [r["batch_key"] for r in rows]

    def set_owner(self, batch_key, user_uid):
        self._exec("INSERT INTO batch_owners(batch_key,user_uid,created_at) VALUES(:b,:u,:t) "
                   "ON CONFLICT DO NOTHING", b=batch_key, u=user_uid, t=time.time())

    def owner_of(self, batch_key):
        r = self._one("SELECT user_uid FROM batch_owners WHERE batch_key=:b", b=batch_key)
        return r["user_uid"] if r else None

    def sent_batches_for_owner(self, fp, exclude_key, user_uid):
        """This user's other batches with the exact same list where money may have moved."""
        rows = self._all(
            "SELECT f.batch_key FROM payout_fingerprints f "
            "JOIN batch_owners o ON o.batch_key=f.batch_key AND o.user_uid=:u "
            "JOIN payout_batches b ON b.batch_key=f.batch_key "
            "JOIN payout_items i ON i.batch_id=b.id "
            "WHERE f.fingerprint=:f AND f.batch_key<>:k "
            "AND i.status IN ('sending','submitted','confirmed','unknown') "
            "GROUP BY f.batch_key", f=fp, k=exclude_key, u=user_uid)
        return [r["batch_key"] for r in rows]
