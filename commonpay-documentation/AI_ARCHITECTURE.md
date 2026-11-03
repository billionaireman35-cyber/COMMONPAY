# AI Architecture

## Principle
AI provides intelligence; deterministic financial services provide authority.

## Intended capabilities
- Financial question answering.
- Transaction summaries.
- Spending and income analysis.
- FX and fee explanations.
- Business financial insights.
- Payment workflow preparation.
- Natural-language transaction search.

## Guardrails
- AI cannot directly move money.
- AI cannot authorise its own proposals.
- AI cannot alter balances or ledger entries.
- AI cannot bypass limits or permissions.
- Financial actions require explicit customer confirmation.
- Backend validates every tool request.
- Tool execution is audited.
- Sensitive data is permission-scoped.
- Prompt injection and data leakage protections are mandatory.

## Current implementation
Model-independent service boundary and non-executable action proposals.
No model provider is selected or connected.
