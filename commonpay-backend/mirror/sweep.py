import asyncio
from mirror.reconcile import reconcile, summary, SUCCESS
from mirror.runtime import get_store
from mirror.verify import verify

async def run():
    store = get_store()
    for p in store.list_payments():
        ref = p["provider_ref"]
        if p["status"] != "submitted" or not ref:
            continue
        if any(e["event_type"] in SUCCESS for e in store.events_for(p["provider"], ref)):
            continue
        try:
            status, amt, cur = await verify(p["provider"], ref)
        except Exception as exc:
            print(f"skip {p['provider']}:{ref}: {exc}")
            continue
        if status in ("success", "successful"):
            kind = "charge.success" if cur == p["currency"] else "charge.currency_mismatch"
            store.add_event(p["provider"], ref, kind, amt, cur)
    results = reconcile(store)
    print(summary(results))
    for r in results:
        if r["verdict"] not in ("MATCHED", "AWAITING_CONFIRMATION", "AWAITING_SETTLEMENT", "PENDING_SUBMISSION", "FAILED"):
            print(r["verdict"], r["provider"], r["provider_ref"], r["detail"])

if __name__ == "__main__":
    asyncio.run(run())
