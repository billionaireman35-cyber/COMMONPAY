# API Specification

Prefix: /api/v1

## Public health
GET /health

## Authenticated routes
POST /payments/checkout
GET /developers/capabilities
POST /intelligence/ask
POST /intelligence/propose-action

## Provider webhooks
POST /webhooks/paystack
POST /webhooks/flutterwave

## Authentication
Current scaffold uses a single environment-configured API key.
This is not the final merchant authentication system.

## Production requirements
- Merchant-specific credentials.
- Hashed API key storage.
- Key rotation and revocation.
- Scoped permissions.
- Rate limits and quotas.
- Idempotency keys.
- Request signing where appropriate.
- Webhook signing and retries.
- Versioning and deprecation policy.
- Developer sandbox and production separation.
- Usage analytics and billing.
