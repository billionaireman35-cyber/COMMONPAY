import { useEffect, useState } from "react";
import { Landmark, Trash2 } from "lucide-react";
import { lookup, type Bank } from "../payouts/api";
import { errText, request } from "../../lib/http";

type Acct = { id: number; account_number: string; bank_code: string; bank_name: string; account_name: string };

const input = {
  width: "100%", padding: "11px 12px", fontSize: 15, borderRadius: 10, boxSizing: "border-box" as const,
  border: "1px solid rgba(128,128,128,.4)", background: "transparent", color: "inherit",
};

export default function Accounts() {
  const [list, setList] = useState<Acct[]>([]);
  const [banks, setBanks] = useState<Bank[]>([]);
  const [bank, setBank] = useState("");
  const [number, setNumber] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [removing, setRemoving] = useState<number | null>(null);

  const load = () =>
    request<{ accounts: Acct[] }>("/accounts").then((r) => setList(r.accounts)).catch((e) => setError(errText(e)));

  useEffect(() => {
    load();
    lookup.banks().then((r) => setBanks(r.banks)).catch(() => {});
  }, []);

  useEffect(() => {
    setName("");
    if (!/^\d{10}$/.test(number) || !bank) return;
    let live = true;
    setError("");
    lookup.resolve(number, bank)
      .then((r) => { if (live) setName(r.account_name); })
      .catch((e) => { if (live) setError(errText(e)); });
    return () => { live = false; };
  }, [number, bank]);

  async function save() {
    setBusy(true);
    setError("");
    try {
      const b = banks.find((x) => x.code === bank);
      await request("/accounts", {
        method: "POST",
        body: JSON.stringify({ account_number: number, bank_code: bank, bank_name: b?.name ?? "" }),
      });
      setNumber(""); setBank(""); setName("");
      await load();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    setBusy(true);
    setError("");
    try {
      await request(`/accounts/${id}/remove`, { method: "POST" });
      setRemoving(null);
      await load();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section className="welcome-row">
        <div>
          <div className="eyebrow">ACCOUNTS</div>
          <h1 style={{ fontSize: 26 }}>Your saved accounts.</h1>
          <p>Bank accounts you pay often. The bank confirms each name. Remove any time.</p>
        </div>
      </section>

      <section className="panel" style={{ padding: 16, display: "grid", gap: 10, marginBottom: 16 }}>
        <strong>Add an account</strong>
        <select style={input} value={bank} onChange={(e) => setBank(e.target.value)}>
          <option value="">Choose a bank</option>
          {banks.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}
        </select>
        <input style={input} inputMode="numeric" placeholder="10-digit account number" value={number}
          onChange={(e) => setNumber(e.target.value.replace(/\D/g, "").slice(0, 10))} />
        {name && <div className="po-ok" style={{ fontSize: 15 }}><strong>{name}</strong></div>}
        {error && <div className="po-error">{error}</div>}
        <button className="primary-button" disabled={busy || !name} onClick={save}>
          {busy ? "Saving…" : "Save account"}
        </button>
      </section>

      <section className="panel" style={{ padding: 16, display: "grid", gap: 10 }}>
        <strong>{list.length ? `Saved (${list.length})` : "Nothing saved yet"}</strong>
        {list.map((a) => (
          <div key={a.id} style={{ display: "flex", gap: 12, alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ display: "flex", gap: 10, alignItems: "center", minWidth: 0 }}>
              <Landmark size={18} />
              <span style={{ minWidth: 0 }}>
                <strong style={{ display: "block", fontSize: 15 }}>{a.account_name}</strong>
                <small style={{ opacity: 0.7 }}>{a.bank_name || a.bank_code} · {a.account_number}</small>
              </span>
            </span>
            {removing === a.id ? (
              <span>
                <button className="secondary-button" onClick={() => setRemoving(null)}>Cancel</button>{" "}
                <button className="primary-button" disabled={busy} onClick={() => remove(a.id)}>Remove</button>
              </span>
            ) : (
              <button className="icon-button" aria-label="Remove account" onClick={() => setRemoving(a.id)}>
                <Trash2 size={17} />
              </button>
            )}
          </div>
        ))}
      </section>
    </>
  );
}
