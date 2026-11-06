import os, sys

from mirror.payout_runtime import build_engine
from mirror.payout_store import PayoutStore
from mirror.rail_paystack import PaystackPayoutRail

if len(sys.argv) != 5:
    sys.exit("usage: smoke_paystack.py ACCOUNT BANK_CODE 'YOUR NAME' BATCH_ID")
acct, bank, name, batch = sys.argv[1:]
key = os.environ.get("PAYSTACK_SECRET_KEY", "")
if not key:
    sys.exit("set PAYSTACK_SECRET_KEY first")

rail = PaystackPayoutRail(secret=key)
print("Paystack says this account belongs to:", rail.resolve_name(acct, bank))
print("Your Paystack balance (kobo):", rail.balance_minor("NGN"))
if input("Type SEND to pay NGN 100.00 to that account: ").strip() != "SEND":
    sys.exit("cancelled, nothing sent")

store = PayoutStore(os.path.expanduser("~/commonpay_smoke.db"))
env = {"PAYOUTS_LIVE_ENABLED": "true", "PAYOUTS_MAX_TOTAL_MINOR": "10000"}
eng = build_engine(store, env, secret=key)
eng.load("smoke-" + batch, [{"name": name, "account_number": acct, "bank_code": bank, "amount": "100.00"}])
print("run:", eng.run("smoke-" + batch))
print("refresh:", eng.refresh("smoke-" + batch))
for row in eng.report("smoke-" + batch):
    print(row)
