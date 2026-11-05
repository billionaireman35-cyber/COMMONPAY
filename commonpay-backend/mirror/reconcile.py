import time
from collections import Counter

SUCCESS = {"charge.success", "transfer.success", "success"}

def _judge(store, p, age, grace, stale_after, tol):
    if p["status"] == "failed":
        return "FAILED", ""
    ref = p["provider_ref"]
    if not ref:
        if p["status"] == "unknown":
            return "UNKNOWN_OUTCOME", "ambiguous provider error; look up at provider before retrying"
        return ("STUCK_UNSUBMITTED", "") if age > grace else ("PENDING_SUBMISSION", "")
    ok = [e for e in store.events_for(p["provider"], ref) if e["event_type"] in SUCCESS]
    st = store.settlement_for(p["provider"], ref)
    if ok and ok[0]["amount_minor"] is not None and ok[0]["amount_minor"] != p["amount_minor"]:
        return "AMOUNT_MISMATCH", f"expected {p['amount_minor']} got {ok[0]['amount_minor']}"
    if st:
        if abs(st["amount_minor"] - p["amount_minor"]) > tol:
            return "SETTLEMENT_MISMATCH", f"expected {p['amount_minor']} settled {st['amount_minor']}"
        store.set_status(p["id"], "settled")
        return "MATCHED", ""
    if ok:
        return ("SETTLEMENT_OVERDUE", "") if age > stale_after else ("AWAITING_SETTLEMENT", "")
    return ("STALE_NO_CONFIRMATION", "") if age > stale_after else ("AWAITING_CONFIRMATION", "")

def reconcile(store, now=None, grace=900, stale_after=3 * 86400, fee_tolerance_minor=0):
    now = now or time.time()
    out, seen = [], set()
    for p in store.list_payments():
        v, d = _judge(store, p, now - p["created_at"], grace, stale_after, fee_tolerance_minor)
        if p["provider_ref"]:
            seen.add((p["provider"], p["provider_ref"]))
        out.append(dict(payment_id=p["id"], provider=p["provider"], provider_ref=p["provider_ref"], verdict=v, detail=d))
    orphans = set()
    for e in store.all_events():
        k = (e["provider"], e["provider_ref"])
        if k not in seen and ("E",) + k not in orphans:
            orphans.add(("E",) + k)
            out.append(dict(payment_id=None, provider=k[0], provider_ref=k[1], verdict="ORPHAN_EVENT", detail=e["event_type"]))
    for s in store.all_settlements():
        k = (s["provider"], s["provider_ref"])
        if k not in seen:
            out.append(dict(payment_id=None, provider=k[0], provider_ref=k[1], verdict="ORPHAN_SETTLEMENT", detail=str(s["amount_minor"])))
    store.save_results(out)
    return out

def summary(results):
    return dict(Counter(r["verdict"] for r in results))
