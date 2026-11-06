from datetime import datetime, timedelta, timezone

WAT = timezone(timedelta(hours=1))  # Nigeria time
CONFIRMED = {"MATCHED"}
FAILED = {"FAILED"}
PENDING = {"AWAITING_CONFIRMATION", "AWAITING_SETTLEMENT", "PENDING_SUBMISSION"}


def today_wat():
    return datetime.now(WAT).date()


def day_bounds(start, end_exclusive):
    s = datetime(start.year, start.month, start.day, tzinfo=WAT).timestamp()
    e = datetime(end_exclusive.year, end_exclusive.month, end_exclusive.day, tzinfo=WAT).timestamp()
    return s, e


def build_close(store, start, end_exclusive):
    """Read-only sales summary for [start, end_exclusive), per currency, in minor units."""
    s, e = day_bounds(start, end_exclusive)
    rows = store._all(
        "SELECT p.id, p.amount_minor, p.currency, r.verdict AS verdict "
        "FROM payments p LEFT JOIN recon_results r ON r.payment_id = p.id "
        "WHERE p.created_at >= :s AND p.created_at < :e", s=s, e=e)
    totals = {}
    for r in rows:
        t = totals.setdefault(r["currency"], {
            "confirmed_minor": 0, "pending_minor": 0, "failed_minor": 0,
            "flagged_minor": 0, "payments": 0})
        v = r["verdict"]
        if v in CONFIRMED:
            key = "confirmed_minor"
        elif v in FAILED:
            key = "failed_minor"
        elif v is None or v in PENDING:
            key = "pending_minor"
        else:
            key = "flagged_minor"
        t[key] += r["amount_minor"]
        t["payments"] += 1
    return {
        "from": start.isoformat(),
        "to": (end_exclusive - timedelta(days=1)).isoformat(),
        "payments": len(rows),
        "totals": totals,
    }
