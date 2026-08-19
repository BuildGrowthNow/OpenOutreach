from unittest.mock import MagicMock


def _make_deal(connect_attempts=0):
    deal = MagicMock()
    deal._id = "deal-001"
    deal.connect_attempts = connect_attempts
    deal.user_id = "user-001"
    return deal


def test_failed_send_increments_attempts():
    from openoutreach.whatsapp.tasks.send_message import _handle_send_failure
    deal = _make_deal(connect_attempts=0)
    _handle_send_failure(deal, banned=False)
    assert deal.connect_attempts == 1
    deal.save.assert_called_once()


def test_max_attempts_transitions_to_failed():
    from openoutreach.whatsapp.tasks.send_message import (
        _handle_send_failure,
        MAX_WA_MESSAGE_ATTEMPTS,
    )
    from openoutreach.mongodb.models import Deal
    deal = _make_deal(connect_attempts=MAX_WA_MESSAGE_ATTEMPTS - 1)
    _handle_send_failure(deal, banned=False)
    assert deal.state == Deal.DealState.FAILED
    assert deal.connect_attempts == MAX_WA_MESSAGE_ATTEMPTS


def test_ban_does_not_increment_attempts():
    from openoutreach.whatsapp.tasks.send_message import _handle_send_failure
    deal = _make_deal(connect_attempts=0)
    _handle_send_failure(deal, banned=True)
    assert deal.connect_attempts == 0
