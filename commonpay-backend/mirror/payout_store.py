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
