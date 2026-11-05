import asyncio, os, time
from mirror.reconcile import reconcile, summary, SUCCESS
from mirror.runtime import get_store
from mirror.verify import verify

QUIET = {"MATCHED", "AWAITING_CONFIRMATION", "AWAITING_SETTLEMENT", "PENDING_SUBMISSION", "FAILED"}

async def run():
    store = get_store()
    cutoff = time.time() - float(os.getenv("MIRROR_VERIFY_WINDOW_DAYS", "7")) * 86400
    for p in store.list_payments():
        ref = p["provider_ref"]
        if p["status"] != "submitted" or not ref or p["created_at"] < cutoff:
            continue
        if any(e["event_type"] in SUCCESS for e in store.events_for(p["provider"], ref)):
            continue
        try:
            status, amt, cur = await verify(p["provider"], ref)
        except Exception as exc:
            print(f"skip {p['provider']}:{ref}: {type(exc).__name__}")
            continue
        if status in ("success", "successful"):
            kind = "charge.success" if cur == p["currency"] else "charge.currency_mismatch"
            store.add_event(p["provider"], ref, kind, amt, cur)
    results = reconcile(store)
    flagged = [r for r in results if r["verdict"] not in QUIET]
    for r in flagged:
        print(r["verdict"], r["provider"], r["provider_ref"], r["detail"])
    return {"summary": summary(results), "flagged": len(flagged)}

if __name__ == "__main__":
    print(asyncio.run(run()))
