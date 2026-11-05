import os, tempfile, time

from sqlalchemy import (BigInteger, Column, Float, Index, Integer, MetaData, String,
                        Table, Text, UniqueConstraint, create_engine, text)
from sqlalchemy.pool import StaticPool

metadata = MetaData()

Table("payments", metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("idempotency_key", String(255), nullable=False, unique=True),
      Column("provider", String(32), nullable=False),
      Column("provider_ref", String(255)),
      Column("checkout_url", Text),
      Column("amount_minor", BigInteger, nullable=False),
      Column("currency", String(8), nullable=False),
      Column("status", String(32), nullable=False, server_default="initiated"),
      Column("created_at", Float, nullable=False),
      Column("updated_at", Float, nullable=False))

Table("provider_events", metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("provider", String(32), nullable=False),
      Column("provider_ref", String(255), nullable=False),
      Column("event_type", String(128), nullable=False),
      Column("amount_minor", BigInteger),
      Column("currency", String(8)),
      Column("received_at", Float, nullable=False),
      UniqueConstraint("provider", "provider_ref", "event_type"))

Table("settlements", metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("provider", String(32), nullable=False),
      Column("provider_ref", String(255), nullable=False),
      Column("amount_minor", BigInteger, nullable=False),
      Column("currency", String(8), nullable=False),
      Column("settled_at", Float, nullable=False),
      UniqueConstraint("provider", "provider_ref"))

Table("recon_results", metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("payment_id", Integer),
      Column("provider", String(32)),
      Column("provider_ref", String(255)),
      Column("verdict", String(64), nullable=False),
      Column("detail", Text),
      Column("checked_at", Float, nullable=False))

Table("provider_attempts", metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("provider", String(32), nullable=False),
      Column("ok", Integer, nullable=False),
      Column("at", Float, nullable=False),
      Index("ix_attempts_provider_id", "provider", "id"))

Table("wallet_accounts", metadata,
      Column("customer_id", String(255), primary_key=True),
      Column("provider", String(32), nullable=False),
      Column("account_ref", String(255), nullable=False),
      Column("reported_balance_minor", BigInteger),
      Column("reported_at", Float))


def _resolve_url(path=None):
    if path in (None, ""):
        url = os.environ.get("DATABASE_URL")
        if url:
            if url.startswith("postgres://"):
                url = "postgresql://" + url[len("postgres://"):]
            if url.startswith("postgresql://"):
                url = "postgresql+psycopg2://" + url[len("postgresql://"):]
            return url
        path = os.environ.get("COMMONPAY_MIRROR_DB", "commonpay_mirror.db")
    if "://" in path:
        return path
    return "sqlite://" if path == ":memory:" else f"sqlite:///{path}"


def _guard_tests(url):
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        return
    if url == "sqlite://":
        return
    if url.startswith("sqlite:///"):
        p = os.path.realpath(url[len("sqlite:///"):])
        if p.startswith(os.path.realpath(tempfile.gettempdir())):
            return
    raise RuntimeError("Tests may only use an in-memory or temp-dir SQLite database")


class Store:
    def __init__(self, path=None):
        url = _resolve_url(path)
        if path in (None, "") and os.environ.get("APP_ENV") == "production" and url.startswith("sqlite"):
            raise RuntimeError("DATABASE_URL is required in production (SQLite would lose records).")
        _guard_tests(url)
        kw = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kw["connect_args"] = {"check_same_thread": False}
            if url == "sqlite://":
                kw["poolclass"] = StaticPool
        self.engine = create_engine(url, **kw)
        metadata.create_all(self.engine)

    # --- plumbing ---
    def _one(self, sql, **a):
        with self.engine.connect() as c:
            return c.execute(text(sql), a).mappings().fetchone()

    def _all(self, sql, **a):
        with self.engine.connect() as c:
            return c.execute(text(sql), a).mappings().fetchall()

    def _exec(self, sql, **a):
        with self.engine.begin() as c:
            return c.execute(text(sql), a).rowcount

    # --- payments ---
    def create_payment(self, key, provider, amount_minor, currency):
        now = time.time()
        n = self._exec(
            "INSERT INTO payments(idempotency_key,provider,amount_minor,currency,status,created_at,updated_at) "
            "VALUES(:k,:p,:a,:c,'initiated',:t,:t) ON CONFLICT (idempotency_key) DO NOTHING",
            k=key, p=provider, a=amount_minor, c=currency, t=now)
        return self.get_by_key(key), n == 1

    def get_payment(self, pid): return self._one("SELECT * FROM payments WHERE id=:i", i=pid)
    def get_by_key(self, key): return self._one("SELECT * FROM payments WHERE idempotency_key=:k", k=key)
    def list_payments(self): return self._all("SELECT * FROM payments ORDER BY id")

    def set_submitted(self, pid, provider, ref):
        self._exec("UPDATE payments SET provider=:p,provider_ref=:r,status='submitted',updated_at=:t WHERE id=:i",
                   p=provider, r=ref, t=time.time(), i=pid)

    def set_status(self, pid, status):
        self._exec("UPDATE payments SET status=:s,updated_at=:t WHERE id=:i", s=status, t=time.time(), i=pid)

    def set_checkout_url(self, pid, url):
        self._exec("UPDATE payments SET checkout_url=:u,updated_at=:t WHERE id=:i", u=url, t=time.time(), i=pid)

    # --- provider signals ---
    def add_event(self, provider, ref, event_type, amount_minor=None, currency=None):
        return self._exec(
            "INSERT INTO provider_events(provider,provider_ref,event_type,amount_minor,currency,received_at) "
            "VALUES(:p,:r,:e,:a,:c,:t) ON CONFLICT DO NOTHING",
            p=provider, r=ref, e=event_type, a=amount_minor, c=currency, t=time.time()) == 1

    def add_settlement(self, provider, ref, amount_minor, currency, settled_at=None):
        return self._exec(
            "INSERT INTO settlements(provider,provider_ref,amount_minor,currency,settled_at) "
            "VALUES(:p,:r,:a,:c,:t) ON CONFLICT DO NOTHING",
            p=provider, r=ref, a=amount_minor, c=currency, t=settled_at or time.time()) == 1

    def events_for(self, provider, ref):
        return self._all("SELECT * FROM provider_events WHERE provider=:p AND provider_ref=:r", p=provider, r=ref)

    def settlement_for(self, provider, ref):
        return self._one("SELECT * FROM settlements WHERE provider=:p AND provider_ref=:r", p=provider, r=ref)

    def all_events(self): return self._all("SELECT * FROM provider_events")
    def all_settlements(self): return self._all("SELECT * FROM settlements")

    # --- routing health ---
    def add_attempt(self, provider, ok):
        self._exec("INSERT INTO provider_attempts(provider,ok,at) VALUES(:p,:o,:t)",
                   p=provider, o=1 if ok else 0, t=time.time())

    def recent_attempts(self, provider, n):
        return self._all("SELECT ok FROM provider_attempts WHERE provider=:p ORDER BY id DESC LIMIT :n",
                         p=provider, n=n)

    # --- reconciliation snapshot (latest run only, so the table never grows) ---
    def save_results(self, results):
        now = time.time()
        with self.engine.begin() as c:
            c.execute(text("DELETE FROM recon_results"))
            if results:
                c.execute(text(
                    "INSERT INTO recon_results(payment_id,provider,provider_ref,verdict,detail,checked_at) "
                    "VALUES(:payment_id,:provider,:provider_ref,:verdict,:detail,:t)"),
                    [dict(r, t=now) for r in results])

    # --- wallet references (PSP-held accounts only) ---
    def add_wallet(self, customer_id, provider, ref):
        self._exec("INSERT INTO wallet_accounts(customer_id,provider,account_ref) VALUES(:c,:p,:r) ON CONFLICT DO NOTHING",
                   c=customer_id, p=provider, r=ref)

    def set_wallet_balance(self, customer_id, balance_minor):
        self._exec("UPDATE wallet_accounts SET reported_balance_minor=:b,reported_at=:t WHERE customer_id=:c",
                   b=balance_minor, t=time.time(), c=customer_id)

    def get_wallet(self, customer_id):
        return self._one("SELECT * FROM wallet_accounts WHERE customer_id=:c", c=customer_id)
