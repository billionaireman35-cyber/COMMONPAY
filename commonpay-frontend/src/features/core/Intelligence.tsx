import { useState } from "react";
import { core } from "./api";
import { errText } from "../../lib/http";

function text(r: unknown): string {
  if (typeof r === "string") return r;
  if (r && typeof r === "object") {
    const o = r as Record<string, unknown>;
    for (const k of ["answer", "response", "text", "message"]) {
      if (typeof o[k] === "string") return o[k] as string;
    }
  }
  return JSON.stringify(r, null, 2);
}

export default function Intelligence() {
  const [q, setQ] = useState("");
  const [chat, setChat] = useState<{ q: string; a: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function ask() {
    const question = q.trim();
    if (!question) return;
    setBusy(true);
    setError("");
    try {
      const a = text(await core.ask(question));
      setChat((c) => [{ q: question, a }, ...c]);
      setQ("");
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
          <div className="eyebrow">COMMONPAY INTELLIGENCE</div>
          <h1>Ask about your money.</h1>
          <p>Explanations only. The assistant cannot move money.</p>
        </div>
      </section>
      {error && <div className="po-error">{error}</div>}
      <article className="panel">
        <label className="fm-field">Your question
          <textarea rows={3} maxLength={4000} value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        <div className="po-row">
          <span />
          <button className="primary-button" disabled={busy || !q.trim()} onClick={ask}>{busy ? "Thinking..." : "Ask"}</button>
        </div>
        <div className="fm-chat">
          {chat.map((c, i) => (
            <div key={i}><div className="fm-q">{c.q}</div><div className="fm-a">{c.a}</div></div>
          ))}
        </div>
      </article>
    </>
  );
}
