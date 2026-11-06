const BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? "").replace(/\/$/, "");
const KEY = (import.meta.env.VITE_COMMONPAY_API_KEY as string | undefined) ?? "";
const PREFIX = "/api/v1/payouts";

export type InRow = { name: string; account_number: string; bank_code: string; amount: string };

export type Item = {
  row: number;
  expected_name: string;
  resolved_name: string | null;
  account: string;
  bank: string;
  amount: string;
  status: string;
  provider: string | null;
  ref: string | null;
  detail: string | null;
};

type Detail = { items: Item[] };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!BASE) throw new Error("VITE_API_URL is not set");
  const res = await fetch(`${BASE}${PREFIX}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-CommonPay-API-Key": KEY,
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (res.status === 422) detail = "The upload was not accepted. Check the columns and amounts.";
    } catch {
      /* keep default message */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  createBatch: (batch_key: string, rows: InRow[], allow_repeat = false) =>
    post<{ created: boolean }>("/batches", { batch_key, currency: "NGN", rows, allow_repeat }),
  verify: (key: string) => post<Detail>(`/batches/${key}/verify`),
  run: (key: string) => post<unknown>(`/batches/${key}/run`),
  refresh: (key: string) => post<unknown>(`/batches/${key}/refresh`),
  get: (key: string) => request<Detail>(`/batches/${key}`),
};

export type Bank = { name: string; code: string };

export const lookup = {
  banks: () => request<{ banks: Bank[] }>("/banks"),
  resolve: (account_number: string, bank_code: string) =>
    request<{ account_name: string }>(
      `/resolve?account_number=${encodeURIComponent(account_number)}&bank_code=${encodeURIComponent(bank_code)}`
    ),
};
