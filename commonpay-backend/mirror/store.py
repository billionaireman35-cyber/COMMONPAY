import os, sqlite3, tempfile, time

SCHEMA = """
CREATE TABLE IF NOT EXISTS payments(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 idempotency_key TEXT NOT NULL UNIQUE,
 provider TEXT NOT NULL, provider_ref TEXT, checkout_url TEXT,
 amount_minor INTEGER NOT NULL, currency TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'initiated',
 created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS provider_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 provider TEXT NOT NULL, provider_ref TEXT NOT NULL, event_type TEXT NOT NULL,
 amount_minor INTEGER, currency TEXT, received_at REAL NOT NULL,
 UNIQUE(provider, provider_ref, event_type));
CREATE TABLE IF NOT EXISTS settlements(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 provider TEXT NOT NULL, provider_ref TEXT NOT NULL,
 amount_minor INTEGER NOT NULL, currency TEXT NOT NULL, settled_at REAL NOT NULL,
 UNIQUE(provider, provider_ref));
CREATE TABLE IF NOT EXISTS recon_results(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 payment_id INTEGER, provider TEXT, provider_ref TEXT,
 verdict TEXT NOT NULL, detail TEXT, checked_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS provider_attempts(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 provider TEXT NOT NULL, ok INTEGER NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS wallet_accounts(
 customer_id TEXT PRIMARY KEY, provider TEXT NOT NULL, account_ref TEXT NOT NULL,
 reported_balance_minor INTEGER, reported_at REAL);
"""

class Store:
    def __init__(self, path=None):
        path = path or os.environ.get("COMMONPAY_MIRROR_DB", "commonpay_mirror.db")
        if os.environ.get("PYTEST_CURRENT_TEST") and path != ":memory:":
            tmp = os.path.realpath(tempfile.gettempdir())
            if not os.path.realpath(path).startswith(tmp):
                raise RuntimeError("Tests may only use a temp database")
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def _one(self, sql, a=()): return self.conn.execute(sql, a).fetchone()
    def _all(self, sql, a=()): return self.conn.execute(sql, a).fetchall()

    def create_payment(self, key, provider, amount_minor, currency):
        now = time.time()
        try:
            cur = self.conn.execute(
                "INSERT INTO payments(idempotency_key,provider,amount_minor,currency,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (key, provider, amount_minor, currency, now, now))
            self.conn.commit()
            return self.get_payment(cur.lastrowid), True
        except sqlite3.IntegrityError:
            return self._one("SELECT * FROM payments WHERE idempotency_key=?", (key,)), False

    def get_payment(self, pid): return self._one("SELECT * FROM payments WHERE id=?", (pid,))
    def list_payments(self): return self._all("SELECT * FROM payments ORDER BY id")

    def set_submitted(self, pid, provider, ref):
        self.conn.execute("UPDATE payments SET provider=?,provider_ref=?,status='submitted',updated_at=? WHERE id=?",
                          (provider, ref, time.time(), pid)); self.conn.commit()

    def set_status(self, pid, status):
        self.conn.execute("UPDATE payments SET status=?,updated_at=? WHERE id=?",
                          (status, time.time(), pid)); self.conn.commit()

    def add_event(self, provider, ref, event_type, amount_minor=None, currency=None):
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO provider_events(provider,provider_ref,event_type,amount_minor,currency,received_at) VALUES(?,?,?,?,?,?)",
            (provider, ref, event_type, amount_minor, currency, time.time()))
        self.conn.commit(); return cur.rowcount == 1

    def add_settlement(self, provider, ref, amount_minor, currency, settled_at=None):
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO settlements(provider,provider_ref,amount_minor,currency,settled_at) VALUES(?,?,?,?,?)",
            (provider, ref, amount_minor, currency, settled_at or time.time()))
        self.conn.commit(); return cur.rowcount == 1

    def events_for(self, provider, ref):
        return self._all("SELECT * FROM provider_events WHERE provider=? AND provider_ref=?", (provider, ref))
    def settlement_for(self, provider, ref):
        return self._one("SELECT * FROM settlements WHERE provider=? AND provider_ref=?", (provider, ref))
    def all_events(self): return self._all("SELECT * FROM provider_events")
    def all_settlements(self): return self._all("SELECT * FROM settlements")

    def add_attempt(self, provider, ok):
        self.conn.execute("INSERT INTO provider_attempts(provider,ok,at) VALUES(?,?,?)",
                          (provider, 1 if ok else 0, time.time())); self.conn.commit()
    def recent_attempts(self, provider, n):
        return self._all("SELECT ok FROM provider_attempts WHERE provider=? ORDER BY id DESC LIMIT ?", (provider, n))

    def save_results(self, results):
        now = time.time()
        self.conn.executemany(
            "INSERT INTO recon_results(payment_id,provider,provider_ref,verdict,detail,checked_at) VALUES(?,?,?,?,?,?)",
            [(r["payment_id"], r["provider"], r["provider_ref"], r["verdict"], r["detail"], now) for r in results])
        self.conn.commit()

    def get_by_key(self, key):
        return self._one("SELECT * FROM payments WHERE idempotency_key=?", (key,))

    def set_checkout_url(self, pid, url):
        self.conn.execute("UPDATE payments SET checkout_url=?,updated_at=? WHERE id=?",
                          (url, time.time(), pid)); self.conn.commit()
