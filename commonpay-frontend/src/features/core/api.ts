import { request } from "../../lib/http";

export type Flag = {
  payment_id: number | null;
  provider: string | null;
  provider_ref: string | null;
  verdict: string;
  detail: string | null;
  checked_at: number;
};

export type Report = {
  last_checked_at: string | null;
  payments_total: number;
  summary: Record<string, number>;
  flagged_count: number;
  flagged: Flag[];
};

export type Capabilities = {
  platform: string;
  api_version: string;
  capabilities: string[];
  providers: string[];
  sandbox: boolean;
  live_money_movement: boolean;
};

export type CheckoutBody = {
  amount: string;
  currency: string;
  customer_email: string;
  provider: string;
  description: string;
  callback_url: string;
};

export const core = {
  report: () => request<Report>("/reconciliation"),
  capabilities: () => request<Capabilities>("/developers/capabilities"),
  health: () => request<Record<string, unknown>>("/health", undefined, ""),
  checkout: (body: CheckoutBody, idem: string) =>
    request<Record<string, unknown>>("/payments/checkout", {
      method: "POST",
      headers: { "Idempotency-Key": idem },
      body: JSON.stringify(body),
    }),
  ask: (question: string) =>
    request<unknown>("/intelligence/ask", { method: "POST", body: JSON.stringify({ question }) }),
};
