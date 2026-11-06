import { useEffect, useState } from "react";
import { ArrowDownLeft, ArrowUpRight, Wallet } from "lucide-react";
import { api, type Close } from "../close/api";
import { errText, naira } from "../../lib/http";

export default function BusinessSummary() {
  const [close, setClose] = useState<Close | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.daily().then(setClose).catch((e) => setError(errText(e)));
  }, []);

  const t = close?.totals["NGN"];
  const show = (minor: number) => (t ? naira(minor) : error ? "-" : "...");
  const note = error || `${t?.payments ?? 0} payments today`;

  return (
    <section className="summary-grid">
      <article className="summary-card">
        <div className="card-heading"><span>Sales today</span><Wallet size={18} /></div>
        <div className="empty-value">{show((t?.confirmed_minor ?? 0) + (t?.pending_minor ?? 0))}</div>
        <p>{note}</p>
      </article>
      <article className="summary-card">
        <div className="card-heading"><span>Confirmed</span><ArrowDownLeft size={18} /></div>
        <div className="empty-value">{show(t?.confirmed_minor ?? 0)}</div>
        <p>Verified by your provider</p>
      </article>
      <article className="summary-card">
        <div className="card-heading"><span>Still pending</span><ArrowUpRight size={18} /></div>
        <div className="empty-value">{show(t?.pending_minor ?? 0)}</div>
        <p>Awaiting confirmation</p>
      </article>
    </section>
  );
}
