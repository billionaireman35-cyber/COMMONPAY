import os
import time
from datetime import timedelta

from sqlalchemy import BigInteger, Column, Float, Integer, String, Table, UniqueConstraint

from mirror.daily_close import build_close
from mirror.partner import get_partner
from mirror.store import metadata

Table("trader_locks", metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("trader_id", String(64), nullable=False),
      Column("lock_day", String(10), nullable=False),
      Column("amount_minor", BigInteger, nullable=False),
      Column("currency", String(8), nullable=False),
      Column("release_on", String(10), nullable=False),
      Column("status", String(16), nullable=False, server_default="locked"),
      Column("partner", String(32), nullable=False),
      Column("partner_ref", String(255)),
      Column("simulated", Integer, nullable=False, server_default="1"),
      Column("created_at", Float, nullable=False),
      Column("released_at", Float),
      UniqueConstraint("trader_id", "lock_day"))


def locks_live_enabled():
    return os.environ.get("TRADER_LOCKS_LIVE_ENABLED", "false").strip().lower() == "true"


class LockError(ValueError):
    pass


class LockService:
    """Records lock instructions. A licensed partner holds the money, never us."""

    def __init__(self, store, partner=None):
        self.store = store
        self._partner = partner
        metadata.create_all(store.engine)

    def _partner_or_default(self):
        return self._partner or get_partner(locks_live_enabled())

    def _get(self, trader_id, lock_day):
        return self.store._one(
            "SELECT * FROM trader_locks WHERE trader_id=:t AND lock_day=:d", t=trader_id, d=lock_day)

    def create_lock(self, trader_id, day, release_on, amount_minor=None,
                    percent_bps=None, currency="NGN"):
        if (amount_minor is None) == (percent_bps is None):
            raise LockError("Give either amount_minor or percent_bps, not both")
        if percent_bps is not None and not 0 < percent_bps <= 10000:
            raise LockError("percent_bps must be between 1 and 10000")
        if release_on <= day:
            raise LockError("release_on must be after the day being locked")
        key_day = day.isoformat()
        existing = self._get(trader_id, key_day)
        if existing is not None:
            return existing, False
        partner = self._partner_or_default()
        close = build_close(self.store, day, day + timedelta(days=1))
        confirmed = close["totals"].get(currency, {}).get("confirmed_minor", 0)
        amount = amount_minor if amount_minor is not None else confirmed * percent_bps // 10000
        if amount <= 0:
            raise LockError("Nothing to lock: no confirmed sales for that day")
        if amount > confirmed:
            raise LockError("Cannot lock more than the day's confirmed sales")
        ref = partner.hold(trader_id, amount, currency, f"{trader_id}:{key_day}")
        n = self.store._exec(
            "INSERT INTO trader_locks(trader_id,lock_day,amount_minor,currency,release_on,"
            "status,partner,partner_ref,simulated,created_at) "
            "VALUES(:t,:d,:a,:c,:r,'locked',:p,:ref,:sim,:now) ON CONFLICT DO NOTHING",
            t=trader_id, d=key_day, a=amount, c=currency, r=release_on.isoformat(),
            p=partner.name, ref=ref, sim=1 if partner.name == "mock" else 0, now=time.time())
        return self._get(trader_id, key_day), n == 1

    def list_locks(self, trader_id):
        return self.store._all(
            "SELECT * FROM trader_locks WHERE trader_id=:t ORDER BY id DESC", t=trader_id)

    def release_due(self, today):
        rows = self.store._all(
            "SELECT * FROM trader_locks WHERE status='locked' AND release_on <= :d",
            d=today.isoformat())
        if not rows:
            return []
        partner = self._partner_or_default()
        released = []
        for r in rows:
            partner.release(r["partner_ref"])
            self.store._exec(
                "UPDATE trader_locks SET status='released', released_at=:t "
                "WHERE id=:i AND status='locked'", t=time.time(), i=r["id"])
            released.append(r["id"])
        return released
