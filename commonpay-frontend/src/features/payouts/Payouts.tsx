import { useEffect, useState } from "react";
import { Download, Send, ShieldCheck, Upload } from "lucide-react";
import { api, type InRow, type Item } from "./api";

const REQUIRED = ["name", "account_number", "bank_code", "amount"];
const MAX_ROWS = 5000;

const naira = (minor: number) =>
  new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN" }).format(minor / 100);
const minorOf = (amount: string) => Math.round(parseFloat(amount) * 100) || 0;
const newKey = () => `p-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  const t = text.replace(/^\uFEFF/, "");
  const flush = () => {
    row.push(cell);
    cell = "";
    if (row.some((x) => x.trim() !== "")) rows.push(row);
    row = [];
  };
  for (let i = 0; i < t.length; i++) {
    const c = t[i];
    if (quoted) {
      if (c === '"') {
        if (t[i + 1] === '"') { cell += '"'; i++; } else quoted = false;
      } else cell += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") { row.push(cell); cell = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && t[i + 1] === "\n") i++;
      flush();
    } else cell += c;
  }
  flush();
  return rows;
}

function toRows(text: string): { rows: InRow[]; error: string } {
  const grid = parseCsv(text);
  if (grid.length < 2) return { rows: [], error: "The file has no data rows." };
  const head = grid[0].map((h) => h.trim().toLowerCase());
  const idx = REQUIRED.map((k) => head.indexOf(k));
  if (idx.some((i) => i < 0))
    return { rows: [], error: `The first row must be: ${REQUIRED.join(", ")}` };
  if (grid.length - 1 > MAX_ROWS)
    return { rows: [], error: `Too many rows (maximum ${MAX_ROWS} per file).` };
  const rows = grid.slice(1).map((r) => ({
    name: (r[idx[0]] ?? "").trim(),
    account_number: (r[idx[1]] ?? "").trim(),
    bank_code: (r[idx[2]] ?? "").trim(),
    amount: (r[idx[3]] ?? "").replace(/[,₦\s]/g, ""),
  }));
  return { rows, error: "" };
}

const csvCell = (v: unknown) => {
  let s = String(v ?? "");
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s; // stop spreadsheet formula injection
  return `"${s.replace(/"/g, '""')}"`;
};

function downloadReport(items: Item[], key: string) {
  const head = ["row", "expected_name", "resolved_name", "account", "bank", "amount", "status", "provider", "ref", "detail"];
  const lines = [head.join(",")].concat(
    items.map((i) => head.map((h) => csvCell((i as Record<string, unknown>)[h])).join(","))
  );
  const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `payout-report-${key}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function label(i: Item): [string, string] {
  switch (i.status) {
    case "pending": return i.resolved_name ? ["Ready", "ok"] : ["Not verified yet", "warn"];
    case "sending": return ["Sending", "warn"];
    case "submitted": return ["Sent, awaiting confirmation", "warn"];
    case "confirmed": return ["Paid", "ok"];
    case "failed": return ["Failed", "bad"];
    case "unknown": return ["Needs checking", "bad"];
    default: return ["Rejected", "bad"];
  }
}

export default function Payouts() {
  const [rows, setRows] = useState<InRow[]>([]);
  const [fileName, setFileName] = useState("");
  const [batchKey, setBatchKey] = useState("");
  const [items, setItems] = useState<Item[]>([]);
  const [step, setStep] = useState<"pick" | "review" | "sent">("pick");
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const [dup, setDup] = useState("");

  const hasSubmitted = items.some((i) => i.status === "submitted");

  useEffect(() => {
    if (step !== "sent" || !hasSubmitted) return;
    const id = setInterval(async () => {
      try {
        await api.refresh(batchKey);
        setItems((await api.get(batchKey)).items);
      } catch {
        /* try again on the next tick */
      }
    }, 8000);
    return () => clearInterval(id);
  }, [step, hasSubmitted, batchKey]);

  function onFile(f: File | undefined) {
    if (!f) return;
    setError("");
    setItems([]);
    setStep("pick");
    setConfirming(false);
    setDup("");
    const reader = new FileReader();
    reader.onload = () => {
      const r = toRows(String(reader.result ?? ""));
      setRows(r.rows);
      setFileName(f.name);
      setBatchKey(newKey());
      if (r.error) setError(r.error);
    };
    reader.readAsText(f);
  }

  async function verify(allowRepeat = false) {
    setBusy(true);
    setError("");
    setDup("");
    try {
      await api.createBatch(batchKey, rows, allowRepeat);
      setItems((await api.verify(batchKey)).items);
      setStep("review");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Could not verify";
      if (msg.startsWith("duplicate-list:")) setDup(msg.slice("duplicate-list:".length).trim());
      else setError(msg);
    } finally {
      setBusy(false);
    }
  }

  async function send() {
    setBusy(true);
    setError("");
    try {
      await api.run(batchKey);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The send request failed");
    }
    try {
      // Whatever happened, show the true state. Never assume nothing was sent.
      const g = (await api.get(batchKey)).items;
      setItems(g);
      if (g.some((i) => !["pending", "rejected"].includes(i.status))) setStep("sent");
    } catch {
      /* keep the previous view */
    } finally {
      setConfirming(false);
      setBusy(false);
    }
  }

  const ready = items.filter((i) => i.status === "pending" && i.resolved_name);
  const readyMinor = ready.reduce((s, i) => s + minorOf(i.amount), 0);
  const rejected = items.filter((i) => i.status === "rejected").length;
  const unknown = items.filter((i) => i.status === "unknown").length;
  const fileMinor = rows.reduce((s, r) => s + minorOf(r.amount), 0);

  return (
    <>
      <section className="welcome-row">
        <div>
          <div className="eyebrow">BUSINESS / SALARY PAYOUTS</div>
          <h1>Pay many people at once.</h1>
          <p>Upload a list. Every account name is checked before anything is sent.</p>
        </div>
      </section>

      {error && <div className="po-error">{error}</div>}
      {dup && (
        <div className="po-row po-confirm">
          <span><strong>Already sent.</strong> {dup}</span>
          <span>
            <button className="secondary-button" onClick={() => setDup("")}>Cancel</button>{" "}
            <button className="primary-button" disabled={busy} onClick={() => verify(true)}>Upload again anyway</button>
          </span>
        </div>
      )}

      <article className="panel">
        <div className="panel-heading">
          <div>
            <h2>1. Upload your list</h2>
            <p>CSV with the columns: name, account_number, bank_code, amount. Keep account numbers as text so leading zeros survive.</p>
          </div>
        </div>
        <label className="secondary-button po-file">
          <Upload size={16} /> {fileName || "Choose a CSV file"}
          <input type="file" accept=".csv,text/csv" onChange={(e) => onFile(e.target.files?.[0])} />
        </label>
        {rows.length > 0 && step === "pick" && (
          <div className="po-row">
            <span>{rows.length} recipients, {naira(fileMinor)} in total</span>
            <button className="primary-button" disabled={busy} onClick={() => verify()}>
              <ShieldCheck size={17} /> {busy ? "Checking names..." : "Verify names"}
            </button>
          </div>
        )}
      </article>

      {step !== "pick" && (
        <article className="panel">
          <div className="panel-heading">
            <div>
              <h2>{step === "review" ? "2. Check and confirm" : "3. Status"}</h2>
              <p>
                {ready.length} ready ({naira(readyMinor)}), {rejected} rejected
                {unknown > 0 ? `, ${unknown} need checking` : ""}
              </p>
            </div>
            <button className="text-button" onClick={() => downloadReport(items, batchKey)}>
              <Download size={15} /> Report
            </button>
          </div>

          <div className="po-scroll">
            <table className="po-table">
              <thead>
                <tr><th>#</th><th>You entered</th><th>Bank says</th><th>Account</th><th>Amount</th><th>Status</th></tr>
              </thead>
              <tbody>
                {items.map((i) => {
                  const [text, tone] = label(i);
                  return (
                    <tr key={i.row}>
                      <td>{i.row}</td>
                      <td>{i.expected_name}</td>
                      <td>{i.resolved_name ?? "-"}</td>
                      <td>{i.account}</td>
                      <td>{naira(minorOf(i.amount))}</td>
                      <td>
                        <span className={`po-badge po-${tone}`}>{text}</span>
                        {i.detail ? <small className="po-detail"> {i.detail}</small> : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {unknown > 0 && (
            <p className="po-note">
              "Needs checking" items are never sent again automatically. Check your provider dashboard before doing anything else.
            </p>
          )}

          {step === "review" && ready.length > 0 && !confirming && (
            <div className="po-row">
              <span>Rejected rows are skipped. Only the ready rows are paid.</span>
              <button className="primary-button" disabled={busy} onClick={() => setConfirming(true)}>
                <Send size={17} /> Send {naira(readyMinor)} to {ready.length}
              </button>
            </div>
          )}
          {step === "review" && confirming && (
            <div className="po-row po-confirm">
              <span>You are about to send <strong>{naira(readyMinor)}</strong> to <strong>{ready.length}</strong> people. This cannot be undone.</span>
              <span>
                <button className="secondary-button" disabled={busy} onClick={() => setConfirming(false)}>Cancel</button>{" "}
                <button className="primary-button" disabled={busy} onClick={send}>{busy ? "Sending..." : "Confirm and send"}</button>
              </span>
            </div>
          )}
          {step === "review" && ready.length === 0 && (
            <p className="po-note">Nothing is ready to send. Fix the rejected rows and upload the file again.</p>
          )}
        </article>
      )}
    </>
  );
}
