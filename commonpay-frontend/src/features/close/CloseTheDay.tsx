import { useCallback, useEffect, useState } from "react";
import { Lock, ShieldCheck } from "lucide-react";
import { api, type Close, type TraderLock, type Totals } from "./api";

const CURRENCY = "NGN";
const EMPTY: Totals = {
  confirmed_minor: 0, pending_minor: 0, failed_minor: 0, flagged_minor: 0, payments: 0,
};
const PERCENTS = [10, 25, 50, 100];
const DAYS = [7, 30, 90];

const naira = (minor: number) =>
  new Intl.NumberFormat("en-NG", {
    style: "currency", currency: CURRENCY, maximumFractionDigits: 0,
  }).format(minor / 100);

const inDays = (n: number) =>
  new Date(Date.now() + n * 86400000).toISOString().slice(0, 10);

export default function CloseTheDay() {
  const [view, setView] = useState<"day" | "month">("day");
  const [close, setClose] = useState<Close | null>(null);
  const [locks, setLocks] = useState<TraderLock[]>([]);
  const [pct, setPct] = useState(25);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [c, l] = await Promise.all([
        view === "day" ? api.daily() : api.monthly(),
        api.locks(),
      ]);
      setClose(c);
      setLocks(l);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }, [view]);

  useEffect(() => { void load(); }, [load]);

  const t = close?.totals[CURRENCY] ?? EMPTY;
  const lockAmount = Math.floor((t.confirmed_minor * pct) / 100);
  const canLock = view === "day" && lockAmount > 0 && !busy;

  async function lockNow() {
    setBusy(true);
    setError("");
    setNote("");
    try {
      const r = await api.createLock({
        release_on: inDays(days), percent_bps: pct * 100, currency: CURRENCY,
      });
      setNote(
        r.created
          ? `${naira(r.lock.amount_minor)} locked until ${r.lock.release_on}.`
          : `Today is already locked: ${naira(r.lock.amount_minor)} until ${r.lock.release_on}.`
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not lock");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="cd-wrap">
      <div className="eyebrow">CLOSE THE DAY</div>
      <h1 className="cd-title">{view === "day" ? "Today's sales" : "This month's sales"}</h1>

      <div className="cd-toggle">
        <button className={view === "day" ? "on" : ""} onClick={() => setView("day")}>Today</button>
        <button className={view === "month" ? "on" : ""} onClick={() => setView("month")}>This month</button>
      </div>

      <div className="cd-test">
        <ShieldCheck size={16} />
        <span>Test mode: no real money is moved yet.</span>
      </div>

      {error && <div className="cd-error">{error}</div>}

      <article className="cd-hero">
        <span>Confirmed in your bank</span>
        <strong>{loading ? "…" : naira(t.confirmed_minor)}</strong>
        <small>{t.payments} sale{t.payments === 1 ? "" : "s"} recorded</small>
      </article>

      <div className="cd-row">
        <div><span>Still waiting</span><strong>{naira(t.pending_minor)}</strong></div>
        <div><span>Failed</span><strong>{naira(t.failed_minor)}</strong></div>
        <div><span>Needs checking</span><strong>{naira(t.flagged_minor)}</strong></div>
      </div>

      {view === "day" && (
        <article className="cd-lock">
          <h2>Lock your profit</h2>
          <p>Choose how much of today's confirmed sales to set aside, and for how long.</p>
          <div className="cd-chips">
            {PERCENTS.map((p) => (
              <button key={p} className={pct === p ? "on" : ""} onClick={() => setPct(p)}>{p}%</button>
            ))}
          </div>
          <div className="cd-chips">
            {DAYS.map((d) => (
              <button key={d} className={days === d ? "on" : ""} onClick={() => setDays(d)}>{d} days</button>
            ))}
          </div>
          <button className="cd-go" disabled={!canLock} onClick={lockNow}>
            <Lock size={17} />
            {busy ? "Locking…" : `Lock ${naira(lockAmount)}`}
          </button>
          {note && <div className="cd-note">{note}</div>}
        </article>
      )}

      {locks.length > 0 && (
        <article className="cd-list">
          <h2>Your locks</h2>
          {locks.map((l) => (
            <div key={l.id} className="cd-item">
              <div>
                <strong>{naira(l.amount_minor)}</strong>
                <small>from {l.lock_day} · opens {l.release_on}</small>
              </div>
              <span className={`cd-tag ${l.status}`}>{l.status}</span>
            </div>
          ))}
        </article>
      )}
    </div>
  );
}
