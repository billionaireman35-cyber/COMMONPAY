const BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? "").replace(/\/$/, "");
const DEVICE = "cp.device";
const SESSION = "cp.session";

const read = (s: Storage, k: string) => {
  try { return s.getItem(k) ?? ""; } catch { return ""; }
};
const write = (s: Storage, k: string, v: string) => {
  try { if (v) s.setItem(k, v); else s.removeItem(k); } catch { /* storage unavailable */ }
};

export const getDevice = () => read(localStorage, DEVICE);
export const setDevice = (v: string) => write(localStorage, DEVICE, v);
export const getSession = () => read(sessionStorage, SESSION);
export const setSession = (v: string) => write(sessionStorage, SESSION, v);

export const authHeader = (): Record<string, string> => {
  const t = getSession();
  return t ? { Authorization: `Bearer ${t}` } : {};
};

export function expireSession() {
  setSession("");
  window.dispatchEvent(new Event("cp-session-expired"));
}

export class AuthError extends Error {
  code: string;
  status: number;
  constructor(detail: string, status: number) {
    const m = /^([a-z-]+):\s*(.*)$/.exec(detail);
    super(m ? m[2] : detail);
    this.code = m ? m[1] : "";
    this.status = status;
  }
}

async function call<T>(path: string, method: "GET" | "POST", body?: unknown, useSession = false): Promise<T> {
  if (!BASE) throw new Error("VITE_API_URL is not set");
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/v1/auth${path}`, {
      method,
      headers: { "Content-Type": "application/json", ...(useSession ? authHeader() : {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error("Cannot reach the server. Is the backend running?");
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const b = await res.json();
      if (typeof b.detail === "string") detail = b.detail;
      else if (res.status === 422) detail = "Check what you entered and try again.";
    } catch {
      /* keep default message */
    }
    throw new AuthError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

export const authApi = {
  requestCode: (email: string) => call<{ sent: boolean }>("/request-code", "POST", { email }),
  verifyCode: (email: string, code: string) =>
    call<{ device_token: string; session_token: string; has_pin: boolean }>(
      "/verify-code", "POST", { email, code, device_name: navigator.userAgent.slice(0, 80) }),
  setPins: (login_pin: string, txn_pin: string) =>
    call<{ ok: boolean }>("/set-pins", "POST", { login_pin, txn_pin }, true),
  login: (pin: string) =>
    call<{ session_token: string }>("/login", "POST", { device_token: getDevice(), pin }),
  me: () => call<{ email: string; has_txn_pin: boolean }>("/me", "GET", undefined, true),
  logout: () => call<{ ok: boolean }>("/logout", "POST", undefined, true),
};

// The app shell registers a prompt; api.run() calls it to get the 4-digit transaction PIN.
let prompt: (() => Promise<string>) | null = null;
export const registerPinPrompt = (p: (() => Promise<string>) | null) => { prompt = p; };
export const askTxnPin = (): Promise<string> =>
  prompt ? prompt() : Promise.reject(new Error("Please sign in first."));
