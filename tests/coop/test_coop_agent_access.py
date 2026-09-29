"""Tests for Coop.get_human_survey_agent_access and patch_human_survey_agent_access.

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


def test_patch_agent_access_sends_the_partial_config():
    coop, response = mocked_coop({**STORED, "enabled": False})

    with patch.object(
        coop, "_send_server_request", return_value=response
    ) as send, patch.object(coop, "_resolve_server_response"):
        access = coop.patch_human_survey_agent_access(
            "survey-uuid", {"enabled": False, "question_settings": {"age": None}}
        )

    send.assert_called_once_with(
        uri=AGENT_ACCESS_URI,
        method="PATCH",
        payload={"patch": {"enabled": False, "question_settings": {"age": None}}},
    )
    assert access["enabled"] is False
