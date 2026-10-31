"""Tests for the approval_mode argument of Coop's Prolific study methods.

The server response is mocked, so these tests do not need a running Coop.
"""

from unittest.mock import Mock, patch

import pytest

from edsl.coop.coop import Coop

STUDY = {
    "study_id": "study-id",
    "status": "UNPUBLISHED",
    "total_available_places": 10,
    "estimated_completion_time": 10,
    "reward": 200,
    "approval_mode": "manual",
}

CREATE_ARGS = {
    "human_survey_uuid": "survey-uuid",
    "name": "Share your recent online shopping experience",
    "description": "A short survey. About 10 minutes.",
    "num_participants": 10,
    "estimated_completion_time_minutes": 10,
    "participant_payment_cents": 200,
}


def mocked_coop():
    """Return a Coop and a response that resolves to STUDY."""
    coop = Coop(api_key="b")
    response = Mock()
    response.json.return_value = STUDY
    return coop, response


def create(**kwargs):
    coop, response = mocked_coop()
    with patch.object(
        coop, "_send_server_request", return_value=response
    ) as send, patch.object(coop, "_resolve_server_response"):
        study = coop.create_prolific_study(**CREATE_ARGS, **kwargs)
    return send.call_args.kwargs["payload"], study


def update(**kwargs):
    coop, response = mocked_coop()
    with patch.object(
        coop, "_send_server_request", return_value=response
    ) as send, patch.object(coop, "_resolve_server_response"):
        study = coop.update_prolific_study("survey-uuid", "study-id", **kwargs)
    # The first request reads the study; the last one is the update
    return send.call_args.kwargs["payload"], study


def test_create_omits_approval_mode_by_default():
    payload, _ = create()
    assert "approval_mode" not in payload


@pytest.mark.parametrize("mode", ["automatic", "manual"])
def test_create_sends_approval_mode_when_given(mode):
    payload, _ = create(approval_mode=mode)
    assert payload["approval_mode"] == mode


def test_create_returns_approval_mode():
    _, study = create()
    assert study["approval_mode"] == "manual"


def test_update_omits_approval_mode_by_default():
    payload, _ = update(name="New name")
    assert payload == {"name": "New name"}


def test_update_sends_approval_mode_when_given():
    payload, study = update(approval_mode="automatic")
    assert payload == {"approval_mode": "automatic"}
    assert study["approval_mode"] == "manual"


def test_get_returns_approval_mode():
    coop, response = mocked_coop()
    with patch.object(
        coop, "_send_server_request", return_value=response
    ), patch.object(coop, "_resolve_server_response"):
        study = coop.get_prolific_study("survey-uuid", "study-id")
    assert study["approval_mode"] == "manual"
