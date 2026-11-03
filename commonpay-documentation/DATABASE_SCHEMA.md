# Database Schema Blueprint

No database is connected or created in this implementation pass.

Planned domains:

## Identity
users, profiles, sessions, devices, businesses, business_members, roles.

## Compliance
kyc_verifications, identity_documents, sanctions_checks, risk_assessments,
transaction_limits, compliance_cases.

## Accounts
accounts, account_types, currencies, bank_accounts, virtual_accounts,
wallet_accounts, balance_projections.

## Ledger
ledger_accounts, ledger_transactions, ledger_entries, balance_reservations,
accounting_periods.

## Payments
payment_intents, transactions, deposits, withdrawals, transfers,
beneficiaries, payment_requests, scheduled_payments.

## Providers
payment_providers, provider_accounts, provider_transactions,
webhook_events, settlement_records, reconciliation_records.

## FX and treasury
fx_quotes, exchange_transactions, exchange_rates, liquidity_positions.

## Developer infrastructure
merchants, api_keys, webhook_endpoints, webhook_deliveries,
api_usage_records, idempotency_records.

## AI
ai_conversations, ai_messages, ai_tool_executions,
ai_recommendations, ai_audit_logs.

## Operations
notifications, audit_logs, security_events, system_events.

All financial records require ownership controls, idempotency, immutable
posting rules, audit context and appropriate retention.
