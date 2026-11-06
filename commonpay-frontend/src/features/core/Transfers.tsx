import { useEffect, useState } from "react";
import { Send, ShieldCheck } from "lucide-react";
import { api, lookup, type Bank, type Item } from "../payouts/api";
import { errText, naira, newKey } from "../../lib/http";

const LABEL: Record<string, string> = {
  pending: "Ready", sending: "Sending", submitted: "Sent, awaiting confirmation",
  confirmed: "Paid", failed: "Failed", unknown: "Needs checking", rejected: "Rejected",
};
const TONE: Record<string, string> = { confirmed: "po-ok", pending: "po-ok", failed: "po-bad", unknown: "po-bad", rejected: "po-bad" };

export default function Transfers() {
  const [banks, setBanks] = useState<Bank[]>([]);
  const [bank, setBank] = useState("");
  const [account, setAccount] = useState("");
  const [amount, setAmount] = useState("");
  const [name, setName] = useState("");
  const [key, setKey] = useState("");
  const [item, setItem] = useState<Item | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    lookup.banks().then((r) => setBanks(r.banks)).catch((e) => setError(errText(e)));
  }, []);

  useEffect(() => {
    if (!key || item?.status !== "submitted") return;
    const id = setInterval(async () => {
      try {
        await api.refresh(key);
        setItem((await api.get(key)).items[0] ?? null);
      } catch {
        /* retry on the next tick */
      }
    }, 6000);
    return () => clearInterval(id);
  }, [key, item?.status]);

  const reset = () => { setName(""); setKey(""); setItem(null); setConfirming(false); setError(""); };
  const amountOk = parseFloat(amount) > 0;

  async function check() {
    setBusy(true);
    setError("");
    try {
      const r = await lookup.resolve(account.trim(), bank);
      setName(r.account_name);
      setKey(newKey());
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  async function send() {
    setBusy(true);
    setError("");
    try {
      await api.createBatch(key, [{ name, account_number: account.trim(), bank_code: bank, amount }], true);
      await api.run(key);
    } catch (e) {
      setError(errText(e));
    }
    try {
      setItem((await api.get(key)).items[0] ?? null); // always show the true state
    } catch {
      /* keep the previous view */
    } finally {
      setConfirming(false);
      setBusy(false);
    }
  }

  const minor = Math.round(parseFloat(amount) * 100) || 0;

  return (
    <>
      <section className="welcome-row">
        <div>
          <div className="eyebrow">TRANSFERS</div>
          <h1>Send money to anyone.</h1>
          <p>Enter the account number, check the name the bank shows, then send.</p>
        </div>
      </section>
      {error && <div className="po-error">{error}</div>}
      <article className="panel">
        <div className="fm-grid">
          <label className="fm-field">Bank
            <select value={bank} disabled={!!item} onChange={(e) => { setBank(e.target.value); reset(); }}>
              <option value="">Choose a bank</option>
              {banks.map((b) => <option key={b.code + b.name} value={b.code}>{b.name}</option>)}
            </select>
          </label>
          <label className="fm-field">Account number
            <input inputMode="numeric" maxLength={10} value={account} disabled={!!item}
              onChange={(e) => { setAccount(e.target.value.replace(/\D/g, "")); reset(); }} />
          </label>
          <label className="fm-field">Amount (NGN)
            <input inputMode="decimal" value={amount} disabled={!!item}
              onChange={(e) => { setAmount(e.target.value); setConfirming(false); }} />
          </label>
        </div>
        {!name && (
          <div className="po-row">
            <span />
            <button className="primary-button" disabled={busy || !bank || account.length !== 10 || !amountOk} onClick={check}>
              <ShieldCheck size={17} /> {busy ? "Checking..." : "Check account name"}
            </button>
          </div>
        )}
        {name && !item && !confirming && (
          <div className="po-row">
            <span>The bank says this account belongs to <strong>{name}</strong>.</span>
            <button className="primary-button" disabled={busy || !amountOk} onClick={() => setConfirming(true)}>
              <Send size={17} /> Send {naira(minor)}
            </button>
          </div>
        )}
        {name && !item && confirming && (
          <div className="po-row po-confirm">
            <span>Send <strong>{naira(minor)}</strong> to <strong>{name}</strong>? This cannot be undone.</span>
            <span>
              <button className="secondary-button" disabled={busy} onClick={() => setConfirming(false)}>Cancel</button>{" "}
              <button className="primary-button" disabled={busy} onClick={send}>{busy ? "Sending..." : "Confirm and send"}</button>
            </span>
          </div>
        )}
        {item && (
          <div className="po-row">
            <span>
              <span className={`po-badge ${TONE[item.status] ?? "po-warn"}`}>{LABEL[item.status] ?? item.status}</span>
              {item.detail ? <small className="po-detail"> {item.detail}</small> : null}
            </span>
            <button className="secondary-button" onClick={() => { setBank(""); setAccount(""); setAmount(""); reset(); }}>New transfer</button>
          </div>
        )}
        {item?.status === "unknown" && (
          <p className="po-note">Do not send again. Check your provider dashboard first.</p>
        )}
      </article>
    </>
  );
}
