import pytest

from app.ai.guardrails import (
    propose_action,
    assert_ai_cannot_execute_money_movement,
)


def test_money_movement_requires_confirmation():
    proposal = propose_action("send_money", "Send 100 NGN")
    assert proposal.requires_customer_confirmation
    assert proposal.executable is False
    assert assert_ai_cannot_execute_money_movement(proposal)


def test_unknown_action_rejected():
    with pytest.raises(ValueError):
        propose_action("delete_database", "Delete everything")
