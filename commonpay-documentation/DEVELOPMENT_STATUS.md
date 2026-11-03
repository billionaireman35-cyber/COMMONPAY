# CommonPay Implementation Status

Initial coordinated foundation created.

Implemented:
- FastAPI application.
- Financial domain primitives.
- Decimal money type.
- In-memory balanced journal validation.
- Flutterwave hosted checkout adapter.
- Paystack transaction initialization adapter.
- Webhook signature verification.
- Payment orchestration boundary.
- Developer capability endpoint.
- AI workflow guardrails.
- React dashboard shell.
- Product and architecture documentation.
- Non-database tests.

Not yet production-ready:
- Durable database persistence.
- Real ledger posting.
- Customer wallet operations.
- Provider transaction verification workflow.
- Durable idempotency and webhook processing.
- Merchant API key lifecycle.
- Full authentication and MFA.
- Connected AI model.
- KYC/AML integrations.
- Regulatory approval.

Live payments and customer wallets remain disabled by default.
