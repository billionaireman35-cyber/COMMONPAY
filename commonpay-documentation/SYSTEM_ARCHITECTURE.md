# System Architecture

## Initial architecture
A modular monolith with clear domain boundaries.

## Backend
FastAPI, Python, Pydantic, SQLAlchemy, PostgreSQL, Redis and background workers.

## Frontend
React, TypeScript, Vite and responsive web/PWA architecture.

## Core domains
1. Identity and access
2. Financial accounts
3. Ledger and accounting
4. Payment orchestration
5. Provider integrations
6. FX and treasury
7. Developer APIs
8. AI intelligence
9. Compliance and risk
10. Notifications and audit

## Provider boundary
CommonPay owns the financial domain and provider-independent orchestration.
Flutterwave and Paystack are external payment service adapters.

## Long-term direction
Support independently licensed CommonPay wallets and customer accounts
without replacing the entire application architecture.
