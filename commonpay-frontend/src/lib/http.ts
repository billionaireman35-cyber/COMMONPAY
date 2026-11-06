import { authHeader, expireSession } from "./auth";
const BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? "").replace(/\/$/, "");

export async function request<T>(path: string, init?: RequestInit, prefix = "/api/v1"): Promise<T> {
  if (!BASE) throw new Error("VITE_API_URL is not set");
  let res: Response;
  try {
    res = await fetch(`${BASE}${prefix}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...authHeader(),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new Error("Cannot reach the server. Is the backend running?");
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (res.status === 422) detail = "Some fields were not accepted. Check them and try again.";
    } catch {
      /* keep default message */
    }
    if (res.status === 401) expireSession();
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const naira = (minor: number) =>
  new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN" }).format(minor / 100);

export const newKey = () => `p-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

export const errText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");
