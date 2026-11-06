import { useRef, useState } from "react";
import { core } from "./api";
import { errText, newKey } from "../../lib/http";

export default function Checkout() {
  const [email, setEmail] = useState("");
  const [amount, setAmount] = useState("");
  const [desc, setDesc] = useState("");
  const [provider, setProvider] = useState("paystack");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const idem = useRef(newKey());

  const edit = (set: (v: string) => void) => (v: string) => {
    idem.current = newKey(); // a changed form is a new payment; an unchanged retry reuses the key
    set(v);
  };
  const valid = /\S+@\S+\.\S+/.test(email) && parseFloat(amount) > 0 && desc.trim().length >= 2;

  async function submit() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await core.checkout(
        { amount, currency: "NGN", customer_email: email, provider, description: desc, callback_url: window.location.origin },
        idem.current));
      idem.current = newKey();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  const url = result
    ? [result.checkout_url, result.authorization_url].find((v): v is string => typeof v === "string")
    : undefined;

  return (
    <>
      <section className="welcome-row">
        <div>
          <div className="eyebrow">PAYMENTS</div>
          <h1>Collect a payment.</h1>
          <p>Create a checkout link and send it to your customer.</p>
        </div>
      </section>
      {error && <div className="po-error">{error}</div>}
      <article className="panel">
        <div className="fm-grid">
          <label className="fm-field">Customer email
            <input type="email" value={email} onChange={(e) => edit(setEmail)(e.target.value)} />
          </label>
          <label className="fm-field">Amount (NGN)
            <input inputMode="decimal" value={amount} onChange={(e) => edit(setAmount)(e.target.value)} />
          </label>
          <label className="fm-field">What is it for
            <input value={desc} onChange={(e) => edit(setDesc)(e.target.value)} />
          </label>
          <label className="fm-field">Provider
            <select value={provider} onChange={(e) => edit(setProvider)(e.target.value)}>
              <option value="paystack">Paystack</option>
              <option value="flutterwave">Flutterwave</option>
            </select>
          </label>
        </div>
        <div className="po-row">
          <span />
          <button className="primary-button" disabled={busy || !valid} onClick={submit}>
            {busy ? "Creating..." : "Create checkout link"}
          </button>
        </div>
        {result && (
          <div className="fm-result">
            {url ? <>Checkout link: <a href={url} target="_blank" rel="noreferrer">{url}</a></> : <pre>{JSON.stringify(result, null, 2)}</pre>}
          </div>
        )}
      </article>
    </>
  );
}
