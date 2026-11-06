import { useEffect, useState, type CSSProperties, type FormEvent, type ReactNode } from "react";
import {
  AuthError, authApi, getDevice, getSession, registerPinPrompt, setDevice, setSession,
} from "../../lib/auth";

type Screen = "boot" | "email" | "code" | "setpins" | "pin" | "app";
type PinRequest = { resolve: (pin: string) => void; reject: (e: Error) => void };

const digits = (v: string, n: number) => v.replace(/\D/g, "").slice(0, n);
const wrap: CSSProperties = { minHeight: "100vh", display: "grid", placeItems: "center", padding: 16 };
const card: CSSProperties = { width: "100%", maxWidth: 380, padding: 24, display: "grid", gap: 12 };
const field: CSSProperties = {
  width: "100%", padding: "12px 14px", fontSize: 18, borderRadius: 10, boxSizing: "border-box",
  border: "1px solid rgba(128,128,128,.4)", background: "transparent", color: "inherit",
};
const pinField: CSSProperties = { ...field, letterSpacing: 8, textAlign: "center", fontSize: 22 };
const muted: CSSProperties = { opacity: 0.7, margin: 0, fontSize: 14 };

function Shell({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <div style={wrap}>
      <div className="panel" style={card}>
        <h2 style={{ margin: 0 }}>{title}</h2>
        {note && <p style={muted}>{note}</p>}
        {children}
      </div>
    </div>
  );
}

export default function AuthGate({ children }: { children: ReactNode }) {
  const [screen, setScreen] = useState<Screen>("boot");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [pin, setPin] = useState("");
  const [loginPin, setLoginPin] = useState("");
  const [loginPin2, setLoginPin2] = useState("");
  const [txnPin, setTxnPin] = useState("");
  const [forgot, setForgot] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [req, setReq] = useState<PinRequest | null>(null);
  const [txnEntry, setTxnEntry] = useState("");

  useEffect(() => {
    let live = true;
    (async () => {
      if (getSession()) {
        try {
          await authApi.me();
          if (live) setScreen("app");
          return;
        } catch {
          /* fall through to the PIN screen */
        }
      }
      if (live) setScreen(getDevice() ? "pin" : "email");
    })();
    const onExpired = () => { setPin(""); setScreen(getDevice() ? "pin" : "email"); };
    window.addEventListener("cp-session-expired", onExpired);
    return () => { live = false; window.removeEventListener("cp-session-expired", onExpired); };
  }, []);

  useEffect(() => {
    registerPinPrompt(() => new Promise<string>((resolve, reject) => {
      setTxnEntry("");
      setReq({ resolve, reject });
    }));
    return () => registerPinPrompt(null);
  }, []);

  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      if (e instanceof AuthError && (e.code === "device-unknown" || e.code === "no-pin")) {
        if (e.code === "device-unknown") setDevice("");
        setPin("");
        setScreen("email");
      }
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const cleanEmail = () => email.trim().toLowerCase();
  const submit = (fn: () => void) => (e: FormEvent) => { e.preventDefault(); fn(); };

  const sendCode = () => act(async () => {
    await authApi.requestCode(cleanEmail());
    setCode("");
    setScreen("code");
  });

  const confirmCode = () => act(async () => {
    const r = await authApi.verifyCode(cleanEmail(), code);
    setDevice(r.device_token);
    setSession(r.session_token);
    setScreen(!r.has_pin || forgot ? "setpins" : "app");
  });

  const savePins = () => act(async () => {
    if (!/^\d{6}$/.test(loginPin)) throw new Error("Your login PIN must be 6 digits.");
    if (loginPin !== loginPin2) throw new Error("The two login PINs do not match.");
    if (!/^\d{4}$/.test(txnPin)) throw new Error("Your transaction PIN must be 4 digits.");
    await authApi.setPins(loginPin, txnPin);
    setForgot(false);
    setLoginPin(""); setLoginPin2(""); setTxnPin("");
    setScreen("app");
  });

  const doLogin = (value: string) => {
    if (busy) return;
    void act(async () => {
      try {
        const r = await authApi.login(value);
        setSession(r.session_token);
        setPin("");
        setScreen("app");
      } catch (e) {
        setPin("");
        throw e;
      }
    });
  };

  async function lock() {
    try { await authApi.logout(); } catch { /* already expired */ }
    setSession("");
    setPin("");
    setScreen(getDevice() ? "pin" : "email");
  }

  const err = error ? <div className="po-error">{error}</div> : null;

  if (screen === "boot") return <Shell title="CommonPay"><p style={muted}>Loading…</p></Shell>;

  if (screen === "email") {
    return (
      <Shell title={forgot ? "Reset your PIN" : "Welcome to CommonPay"}
        note="Enter your email. We will send you a 6-digit code to confirm it is you.">
        <form onSubmit={submit(sendCode)} style={{ display: "grid", gap: 12 }}>
          <input style={field} type="email" autoComplete="email" placeholder="you@example.com"
            value={email} onChange={(e) => setEmail(e.target.value)} />
          {err}
          <button className="primary-button" type="submit" disabled={busy || !email.includes("@")}>
            {busy ? "Sending…" : "Send code"}
          </button>
          {getDevice() && (
            <button className="text-button" type="button" onClick={() => { setForgot(false); setError(""); setScreen("pin"); }}>
              Back to PIN
            </button>
          )}
        </form>
      </Shell>
    );
  }

  if (screen === "code") {
    return (
      <Shell title="Enter the code" note={`We sent a 6-digit code to ${cleanEmail()}. It expires in 10 minutes.`}>
        <form onSubmit={submit(confirmCode)} style={{ display: "grid", gap: 12 }}>
          <input style={pinField} inputMode="numeric" autoComplete="one-time-code" placeholder="000000"
            value={code} onChange={(e) => setCode(digits(e.target.value, 6))} />
          {err}
          <button className="primary-button" type="submit" disabled={busy || code.length !== 6}>
            {busy ? "Checking…" : "Confirm"}
          </button>
          <button className="text-button" type="button" onClick={() => { setError(""); setScreen("email"); }}>
            Use a different email
          </button>
        </form>
      </Shell>
    );
  }

  if (screen === "setpins") {
    return (
      <Shell title="Set your PINs"
        note="Your login PIN opens the app. Your transaction PIN is asked before any money is sent. Keep them different.">
        <form onSubmit={submit(savePins)} style={{ display: "grid", gap: 12 }}>
          <input style={pinField} type="password" inputMode="numeric" autoComplete="new-password"
            placeholder="Login PIN (6 digits)" value={loginPin}
            onChange={(e) => setLoginPin(digits(e.target.value, 6))} />
          <input style={pinField} type="password" inputMode="numeric" autoComplete="new-password"
            placeholder="Repeat login PIN" value={loginPin2}
            onChange={(e) => setLoginPin2(digits(e.target.value, 6))} />
          <input style={pinField} type="password" inputMode="numeric" autoComplete="new-password"
            placeholder="Transaction PIN (4 digits)" value={txnPin}
            onChange={(e) => setTxnPin(digits(e.target.value, 4))} />
          {err}
          <button className="primary-button" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Save PINs"}
          </button>
        </form>
      </Shell>
    );
  }

  if (screen === "pin") {
    return (
      <Shell title="Enter your PIN">
        <form onSubmit={submit(() => doLogin(pin))} style={{ display: "grid", gap: 12 }}>
          <input style={pinField} type="password" inputMode="numeric" autoComplete="current-password"
            placeholder="••••••" autoFocus value={pin}
            onChange={(e) => { const v = digits(e.target.value, 6); setPin(v); if (v.length === 6) doLogin(v); }} />
          {err}
          <button className="primary-button" type="submit" disabled={busy || pin.length !== 6}>
            {busy ? "Checking…" : "Unlock"}
          </button>
          <button className="text-button" type="button"
            onClick={() => { setForgot(true); setError(""); setScreen("email"); }}>
            Forgot PIN?
          </button>
        </form>
      </Shell>
    );
  }

  return (
    <>
      {children}
      <button className="secondary-button" onClick={lock}
        style={{ position: "fixed", right: 12, bottom: 12, zIndex: 50 }}>
        Lock
      </button>
      {req && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.6)", zIndex: 100,
          display: "grid", placeItems: "center", padding: 16 }}>
          <div className="panel" style={card}>
            <h2 style={{ margin: 0 }}>Transaction PIN</h2>
            <p style={muted}>Enter your 4-digit transaction PIN to send this money.</p>
            <form style={{ display: "grid", gap: 12 }} onSubmit={(e) => {
              e.preventDefault();
              if (/^\d{4}$/.test(txnEntry)) { req.resolve(txnEntry); setReq(null); }
            }}>
              <input style={pinField} type="password" inputMode="numeric" autoFocus placeholder="••••"
                value={txnEntry} onChange={(e) => setTxnEntry(digits(e.target.value, 4))} />
              <button className="primary-button" type="submit" disabled={txnEntry.length !== 4}>Send money</button>
              <button className="secondary-button" type="button"
                onClick={() => { req.reject(new Error("PIN entry cancelled.")); setReq(null); }}>
                Cancel
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
