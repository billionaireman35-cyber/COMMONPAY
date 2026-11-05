from datetime import datetime, timezone

from mirror.reconcile import summary

QUIET = {"MATCHED", "AWAITING_CONFIRMATION", "AWAITING_SETTLEMENT", "PENDING_SUBMISSION", "FAILED"}


def build_report(store, limit=100):
    """Read-only view of the latest reconciliation snapshot (never writes)."""
    rows = [dict(r) for r in store._all(
        "SELECT payment_id, provider, provider_ref, verdict, detail, checked_at FROM recon_results ORDER BY id")]
    flagged = [r for r in rows if r["verdict"] not in QUIET]
    checked = max((r["checked_at"] for r in rows), default=None)
    last = datetime.fromtimestamp(checked, tz=timezone.utc).isoformat() if checked else None
    return {
        "last_checked_at": last,
        "payments_total": store._one("SELECT COUNT(*) AS n FROM payments")["n"],
        "summary": summary(rows),
        "flagged_count": len(flagged),
        "flagged": flagged[:limit],
    }
