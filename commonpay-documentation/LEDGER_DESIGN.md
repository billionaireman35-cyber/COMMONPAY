# Ledger Design

## Accounting principles
- Double-entry accounting.
- Immutable posted journal entries.
- Debit total equals credit total for each currency.
- Decimal arithmetic only.
- No floating-point money calculations.
- Corrections use reversals and compensating entries.
- Every posting has an account, currency, reference and audit context.

## Balance model
Customer balance projections are derived from posted ledger activity.
A displayed balance must never be the sole financial source of truth.

## Balance categories
- Ledger balance
- Available balance
- Pending balance
- Reserved balance

## Transaction lifecycle
CREATED -> PENDING -> PROCESSING -> COMPLETED

Failure, cancellation and reversal are explicit states with controlled
transition rules.

## Before production
Implement durable ledger persistence, atomic posting, concurrency controls,
idempotency, account ownership checks, period controls, reconciliation,
holds, releases, settlement and reversals.

The current domain module validates journal balance in memory only.
It is not a production ledger or a customer wallet.
