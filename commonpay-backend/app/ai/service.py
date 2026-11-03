from app.ai.guardrails import propose_action


class FinancialIntelligence:
    """
    Model-provider-independent AI boundary.

    No model is selected or called by default.
    Financial tools must be explicitly registered and authorised.
    """

    async def propose_workflow(self, action: str, summary: str):
        return propose_action(action, summary)

    async def answer(self, question: str):
        return {
            "status": "not_configured",
            "message": (
                "The CommonPay Intelligence Engine is scaffolded. "
                "Configure an approved AI provider before enabling responses."
            ),
            "question_received": bool(question.strip()),
        }


intelligence = FinancialIntelligence()
