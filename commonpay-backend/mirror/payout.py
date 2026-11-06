import csv, hashlib, re, time
from decimal import Decimal, InvalidOperation
from mirror.payout_store import PayoutStore  # noqa: F401 (re-export)
from mirror.router import ProviderDown


class AccountNotFound(Exception):
    pass


class InsufficientFunds(Exception):
    pass


# ---------- rails (payout side) ----------
class PayoutRail:
    """Adapter contract. transfer() may raise ProviderDown ONLY when the provider
    definitely did not process the request. Timeouts / 5xx after sending are
    ambiguous: let them propagate as ordinary exceptions."""
    name = "base"

    def resolve_name(self, account_number, bank_code):
        raise NotImplementedError

    def transfer(self, key, amount_minor, currency, account_number, bank_code, name):
        raise NotImplementedError

    def status(self, key):  # "success" | "failed" | "pending" | "not_found"
        raise NotImplementedError


class MockRail(PayoutRail):
    def __init__(self, name, names=None, down=False, ambiguous=False):
        self.name, self.names = name, dict(names or {})
        self.down, self.ambiguous = down, ambiguous
        self.sent, self.calls = {}, 0

    def resolve_name(self, account_number, bank_code):
        if self.down:
            raise ProviderDown(self.name)
        if account_number not in self.names:
            raise AccountNotFound(account_number)
        return self.names[account_number]

    def transfer(self, key, amount_minor, currency, account_number, bank_code, name):
        self.calls += 1
        if self.down:
            raise ProviderDown(self.name)
        self.sent[key] = "success"
        if self.ambiguous:
            raise TimeoutError("response lost after provider accepted")
        return f"{self.name.upper()}-{key}"

    def status(self, key):
        return self.sent.get(key, "not_found")


# ---------- funding (the A / B switch) ----------
class FundingSource:
    def ensure(self, ref, total_minor, currency):
        raise NotImplementedError


class MockFunding(FundingSource):
    def __init__(self, balance_minor=None):
        self.balance = balance_minor

    def ensure(self, ref, total_minor, currency):
        if self.balance is not None and total_minor > self.balance:
            raise InsufficientFunds(f"need {total_minor}, have {self.balance}")
        return "MOCK-FUND-" + ref


class PrefundedFunding(FundingSource):
    """Model A: business-owned provider balances. balance_fn() returns available minor units."""
    def __init__(self, balance_fn):
        self.balance_fn = balance_fn

    def ensure(self, ref, total_minor, currency):
        bal = self.balance_fn()
        if total_minor > bal:
            raise InsufficientFunds(f"need {total_minor}, have {bal}")
        return "PREFUNDED-" + ref


class PartnerFunding(FundingSource):
    """Model B: licensed partner holds funds (mirror.partner.PartnerAdapter)."""
    def __init__(self, partner, trader_id):
        self.partner, self.trader_id = partner, trader_id

    def ensure(self, ref, total_minor, currency):
        return self.partner.hold(self.trader_id, total_minor, currency, ref)


# ---------- helpers ----------
def _tokens(s):
    return set(re.sub(r"[^A-Z ]", " ", (s or "").upper()).split())


def names_match(expected, resolved):
    x, y = _tokens(expected), _tokens(resolved)
    if not x or not y:
        return False
    return (x <= y or y <= x) and len(x & y) >= min(2, len(x), len(y))


def _check(r, seen):
    acct = str(r.get("account_number", "")).strip()
    bank = str(r.get("bank_code", "")).strip()
    try:
        d = Decimal(str(r.get("amount"))) * 100
        amt = int(d) if d == d.to_integral_value() else 0
    except (InvalidOperation, ValueError, TypeError, OverflowError):
        amt = 0
    err = ""
    if not re.fullmatch(r"\d{10}", acct):
        err = "bad account number"
    elif not bank:
        err = "missing bank code"
    elif amt <= 0:
        err = "bad amount"
    elif (acct, bank) in seen:
        err = "duplicate account in batch"
    seen.add((acct, bank))
    return acct[:20], bank[:16], amt, err


# ---------- engine ----------
class PayoutEngine:
    def __init__(self, store, rails, funding, stale_sending=120):
        self.store, self.rails, self.funding = store, list(rails), funding
        self.by_name = {r.name: r for r in self.rails}
        self.stale = stale_sending

    def load(self, batch_key, rows, currency="NGN"):
        b, created = self.store.create_batch(batch_key, currency)
        if not created:
            return b  # same batch_key = same batch, never re-added
        seen = set()
        for n, r in enumerate(rows, 1):
            acct, bank, amt, err = _check(r, seen)
            self.store.add_item(b["id"], f"{batch_key}:{n}", n, acct, bank,
                                (r.get("name") or "").strip(), amt,
                                "rejected" if err else "pending", err)
        return b

    def load_csv(self, batch_key, path, currency="NGN"):
        with open(path, newline="", encoding="utf-8-sig") as f:
            return self.load(batch_key, list(csv.DictReader(f)), currency)

    def _resolve(self, it):
        for rail in self.rails:
            try:
                return rail.resolve_name(it["account_number"], it["bank_code"])
            except AccountNotFound:
                raise
            except Exception:
                continue
        return None

    def verify_names(self, batch_key):
        b = self.store.get_batch(batch_key)
        for it in self.store.items(b["id"]):
            if it["status"] != "pending" or it["resolved_name"]:
                continue
            try:
                resolved = self._resolve(it)
            except AccountNotFound:
                self.store.move(it["id"], "pending", "rejected", detail="account not found")
                continue
            if resolved is None:
                continue  # all rails unavailable: stay pending, retry next run
            if names_match(it["expected_name"], resolved):
                self.store.set_fields(it["id"], resolved_name=resolved)
            else:
                self.store.move(it["id"], "pending", "rejected", resolved_name=resolved,
                                detail="name mismatch")

    def _recover(self, b):
        now = time.time()
        for it in self.store.items(b["id"]):
            if it["status"] == "sending" and now - it["updated_at"] >= self.stale:
                self.store.move(it["id"], "sending", "unknown", detail="interrupted mid-send")

    def _order(self, preferred):
        first = [r for r in self.rails if r.name == preferred]
        return first + [r for r in self.rails if r.name != preferred]

    def _send(self, it, currency, preferred):
        if not self.store.move(it["id"], "pending", "sending"):
            return  # claimed by another run
        last = None
        for rail in self._order(preferred):
            self.store.set_fields(it["id"], provider=rail.name)  # recorded BEFORE the call
            try:
                ref = rail.transfer(it["idem_key"], it["amount_minor"], currency,
                                    it["account_number"], it["bank_code"], it["resolved_name"])
            except ProviderDown as e:
                self.store.add_attempt(rail.name, False)
                last = e
                continue
            except Exception as e:
                self.store.add_attempt(rail.name, False)
                self.store.move(it["id"], "sending", "unknown", detail=type(e).__name__)
                return  # ambiguous: never fail over, never retry
            self.store.add_attempt(rail.name, True)
            self.store.move(it["id"], "sending", "submitted", provider=rail.name, provider_ref=ref)
            return
        self.store.move(it["id"], "sending", "pending", provider=None, detail=f"all rails down: {last}")

    def run(self, batch_key, preferred=None):
        b = self.store.get_batch(batch_key)
        self._recover(b)
        self.verify_names(batch_key)
        ready = [i for i in self.store.items(b["id"]) if i["status"] == "pending" and i["resolved_name"]]
        if ready:
            h = hashlib.sha1("|".join(i["idem_key"] for i in ready).encode()).hexdigest()[:10]
            self.funding.ensure(f"{batch_key}:{h}", sum(i["amount_minor"] for i in ready), b["currency"])
            for it in ready:
                self._send(it, b["currency"], preferred)
        return self.summary(batch_key)

    def refresh(self, batch_key):
        """Re-query providers for submitted/unknown items. Never re-sends."""
        b = self.store.get_batch(batch_key)
        for it in self.store.items(b["id"]):
            rail = self.by_name.get(it["provider"])
            if it["status"] not in ("submitted", "unknown") or rail is None:
                continue
            try:
                st = rail.status(it["idem_key"])
            except Exception:
                continue
            if st == "success":
                self.store.move(it["id"], it["status"], "confirmed")
            elif st == "failed":
                self.store.move(it["id"], it["status"], "failed", detail="rejected by provider")
            elif st == "pending" and it["status"] == "unknown":
                self.store.move(it["id"], "unknown", "submitted")
            # not_found: stays unknown for a human; never auto-retried
        return self.summary(batch_key)

    def summary(self, batch_key):
        b = self.store.get_batch(batch_key)
        out = {}
        for it in self.store.items(b["id"]):
            s = out.setdefault(it["status"], {"count": 0, "minor": 0})
            s["count"] += 1
            s["minor"] += it["amount_minor"]
        return out

    def report(self, batch_key):
        b = self.store.get_batch(batch_key)
        return [dict(row=i["row_no"], expected_name=i["expected_name"], resolved_name=i["resolved_name"],
                     account=i["account_number"], bank=i["bank_code"],
                     amount=f"{i['amount_minor'] // 100}.{i['amount_minor'] % 100:02d}",
                     status=i["status"], provider=i["provider"], ref=i["provider_ref"], detail=i["detail"])
                for i in self.store.items(b["id"])]

    def write_report(self, batch_key, path):
        rows = self.report(batch_key)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["row"])
            w.writeheader()
            w.writerows(rows)
