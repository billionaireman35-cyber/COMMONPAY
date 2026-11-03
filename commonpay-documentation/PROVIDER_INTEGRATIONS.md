# Provider Integrations

## Preferred initial providers
- Flutterwave
- Paystack

## Architecture
CommonPay -> Payment Orchestration -> Provider Adapter -> External Provider.

Provider adapters must remain replaceable.

## Current implementation
- Flutterwave hosted checkout adapter.
- Paystack transaction initialization adapter.
- Paystack webhook signature verification.
- Flutterwave webhook signature verification for documented signature forms.

## Important production requirements
- Verify every payment with the provider API.
- Match expected reference, amount, currency and status.
- Persist webhook events durably.
- Enforce idempotency.
- Reconcile provider settlement reports.
- Handle provider timeouts and duplicate events.
- Never credit a customer solely from an unverified webhook.
- Never assume every product or currency is enabled on a merchant account.

## References
Flutterwave:
https://developer.flutterwave.com/docs/webhooks
https://developer.flutterwave.com/docs/transaction-verification
https://developer.flutterwave.com/docs/authentication

Paystack:
https://paystack.com/docs/api/transaction/
https://paystack.com/docs/payments/webhooks/

## Regulatory boundary
Provider licences do not transfer to CommonPay.
Actual fund flows and service permissions must be approved.
