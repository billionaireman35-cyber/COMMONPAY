from dataclasses import dataclass


FINANCIAL_ACTIONS = {
    "send_money",
    "withdraw",
    "convert_currency",
    "pay_beneficiary",
    "schedule_payment",
}


@dataclass(frozen=True)
class AIActionProposal:
    action: str
    summary: str
    requires_customer_confirmation: bool
    executable: bool = False


def propose_action(action: str, summary: str) -> AIActionProposal:
    if action not in FINANCIAL_ACTIONS:
        raise ValueError("Unsupported financial action.")

    return AIActionProposal(
        action=action,
        summary=summary,
        requires_customer_confirmation=True,
        executable=False,
    )


def assert_ai_cannot_execute_money_movement(action: AIActionProposal):
    if action.executable:
        raise PermissionError(
            "AI cannot directly execute financial transactions."
        )
    return True
