import { authHeader, expireSession } from "../../lib/auth";
const BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? "").replace(/\/$/, "");
const PREFIX = "/api/v1";

export type Totals = {
  confirmed_minor: number;
  pending_minor: number;
  failed_minor: number;
  flagged_minor: number;
  payments: number;
};

export type Close = {
  from: string;
  to: string;
  payments: number;
  totals: Record<string, Totals>;
};

export type TraderLock = {
  id: number;
  lock_day: string;
  amount_minor: number;
  currency: string;
  release_on: string;
  status: string;
  partner: string;
  simulated: number;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!BASE) throw new Error("VITE_API_URL is not set");
  const res = await fetch(`${BASE}${PREFIX}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeader(),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* keep default message */
    }
    if (res.status === 401) expireSession();
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  daily: () => request<Close>("/trader/close/daily"),
  monthly: () => request<Close>("/trader/close/monthly"),
  locks: () => request<TraderLock[]>("/trader/locks"),
  createLock: (body: { release_on: string; percent_bps: number; currency: string }) =>
    request<{ created: boolean; lock: TraderLock }>("/trader/locks", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
