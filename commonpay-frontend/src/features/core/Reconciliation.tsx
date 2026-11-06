import { useCallback, useEffect, useState } from "react";
import { core, type Report } from "./api";
import { errText } from "../../lib/http";

const GOOD = new Set(["MATCHED"]);
const QUIET = new Set(["AWAITING_CONFIRMATION", "AWAITING_SETTLEMENT", "PENDING_SUBMISSION", "FAILED"]);

export default function Reconciliation() {
  const [r, setR] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      setR(await core.report());
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <>
      <section className="welcome-row">
        <div>
          <div className="eyebrow">BUSINESS / RECONCILIATION</div>
          <h1>Did the money actually arrive?</h1>
          <p>Every payment checked against what your provider confirmed and settled.</p>
        </div>
        <button className="secondary-button" disabled={busy} onClick={load}>{busy ? "Loading..." : "Refresh"}</button>
      </section>
      {error && <div className="po-error">{error}</div>}
      {r && (
        <>
          <article className="panel">
            <div className="panel-heading">
              <div>
                <h2>{r.payments_total} payments, {r.flagged_count} need attention</h2>
                <p>{r.last_checked_at ? `Last checked ${new Date(r.last_checked_at).toLocaleString()}` : "No check has run yet"}</p>
              </div>
            </div>
            <div>
              {Object.entries(r.summary).map(([k, n]) => (
                <span key={k} className={`po-badge ${GOOD.has(k) ? "po-ok" : QUIET.has(k) ? "po-warn" : "po-bad"}`} style={{ marginRight: 6, marginBottom: 6 }}>
                  {k.replace(/_/g, " ").toLowerCase()}: {n}
                </span>
              ))}
            </div>
          </article>
          {r.flagged.length > 0 && (
            <article className="panel">
              <div className="panel-heading"><div><h2>Needs attention</h2></div></div>
              <div className="po-scroll">
                <table className="po-table">
                  <thead><tr><th>Issue</th><th>Provider</th><th>Reference</th><th>Detail</th></tr></thead>
                  <tbody>
                    {r.flagged.map((f, i) => (
                      <tr key={i}>
                        <td><span className="po-badge po-bad">{f.verdict.replace(/_/g, " ").toLowerCase()}</span></td>
                        <td>{f.provider ?? "-"}</td>
                        <td>{f.provider_ref ?? "-"}</td>
                        <td>{f.detail ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          )}
        </>
      )}
    </>
  );
}
