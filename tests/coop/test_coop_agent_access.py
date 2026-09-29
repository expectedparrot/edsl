"""Tests for Coop.get_human_survey_agent_access and update_human_survey_agent_access.

The server response is mocked, so these tests do not need a running Coop.
"""

from unittest.mock import Mock, patch

from edsl.coop.coop import Coop

AGENT_ACCESS_URI = "api/v0/human-surveys/survey-uuid/agent-access"

STORED = {
    "configured": True,
    "enabled": True,
    "participation_mode": "autonomous",
    "instructions": "Answer as a 42-year-old teacher.",
    "question_settings": {"age": {"instructions": "A rough age is fine."}},
}


def mocked_coop(content: dict):
    """Return a Coop whose next server request resolves to ``content``."""
    coop = Coop(api_key="b")
    response = Mock()
    response.json.return_value = content
    return coop, response


def test_get_agent_access_returns_the_stored_config():
    coop, response = mocked_coop(STORED)

    with patch.object(
        coop, "_send_server_request", return_value=response
    ) as send, patch.object(coop, "_resolve_server_response"):
        access = coop.get_human_survey_agent_access("survey-uuid")

    send.assert_called_once_with(uri=AGENT_ACCESS_URI, method="GET")
    assert access == STORED


def test_update_agent_access_sends_the_whole_config():
    coop, response = mocked_coop(STORED)

    with patch.object(
        coop, "_send_server_request", return_value=response
    ) as send, patch.object(coop, "_resolve_server_response"):
        access = coop.update_human_survey_agent_access(
            "survey-uuid",
            enabled=True,
            participation_mode="autonomous",
            instructions="Answer as a 42-year-old teacher.",
            question_settings={"age": {"instructions": "A rough age is fine."}},
        )

    send.assert_called_once_with(
        uri=AGENT_ACCESS_URI,
        method="PUT",
        payload={
            "enabled": True,
            "participation_mode": "autonomous",
            "instructions": "Answer as a 42-year-old teacher.",
            "question_settings": {"age": {"instructions": "A rough age is fine."}},
        },
    )
    assert access == STORED


def test_update_agent_access_fills_in_defaults_for_fields_left_out():
    # The whole config is replaced, so every field is sent, with its default.
    coop, response = mocked_coop({**STORED, "participation_mode": "human_assisted"})

    with patch.object(
        coop, "_send_server_request", return_value=response
    ) as send, patch.object(coop, "_resolve_server_response"):
        coop.update_human_survey_agent_access("survey-uuid", enabled=True)

    assert send.call_args.kwargs["payload"] == {
        "enabled": True,
        "participation_mode": "human_assisted",
        "instructions": None,
        "question_settings": {},
    }
