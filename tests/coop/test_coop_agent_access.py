"""Tests for Coop.get_human_survey_agent_access and patch_human_survey_agent_access.

The server response is mocked, so these tests do not need a running Coop.
"""

from unittest.mock import Mock, patch

import pytest

from edsl.coop.coop import Coop
from edsl.coop.coop_agent_access import validate_agent_access_patch
from edsl.coop.exceptions import AgentAccessValidationError
from edsl.questions import QuestionFreeText
from edsl.surveys import Survey

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


def test_patch_agent_access_is_validated_before_it_is_sent():
    coop, response = mocked_coop(STORED)

    with patch.object(
        coop, "_send_server_request", return_value=response
    ) as send, patch.object(coop, "_resolve_server_response"):
        with pytest.raises(AgentAccessValidationError):
            coop.patch_human_survey_agent_access(
                "survey-uuid", {"participation_mode": "role_play"}
            )

    send.assert_not_called()


# -- validate_agent_access_patch -----------------------------------------------------

SURVEY = Survey(
    [
        QuestionFreeText(question_name="age", question_text="How old are you?"),
        QuestionFreeText(question_name="job", question_text="What is your job?"),
    ]
)


@pytest.mark.parametrize(
    "partial_config",
    [
        {},
        {"enabled": True},
        {"participation_mode": "autonomous", "instructions": "Answer as a teacher."},
        {"instructions": None},  # clears them
        {"question_settings": {"age": {"instructions": "A rough age is fine."}}},
        {"question_settings": {"age": None}},  # removes that question's settings
        {"question_settings": {"age": {"instructions": None}}},
    ],
)
def test_a_valid_patch_passes(partial_config):
    validate_agent_access_patch(partial_config)


@pytest.mark.parametrize(
    "partial_config",
    [
        ["enabled"],  # not an object
        {"configured": True},  # read-only, not part of the config
        {"participation_mode": "role_play"},  # not a mode
        {"enabled": None},  # can't be null
        {"participation_mode": None},  # can't be null
        {"question_settings": None},  # can't be null
        {"instructions": ""},  # empty
        {"instructions": "x" * 4001},  # too long
        {"question_settings": {"age": {"instructions": "x" * 2001}}},  # too long
        {"question_settings": {"age": {"handoff": "required"}}},  # not a setting
    ],
)
def test_an_invalid_patch_is_rejected(partial_config):
    with pytest.raises(AgentAccessValidationError):
        validate_agent_access_patch(partial_config)


def test_with_a_survey_question_names_must_be_in_it():
    validate_agent_access_patch(
        {"question_settings": {"age": {"instructions": "A rough age is fine."}}},
        SURVEY,
    )
    with pytest.raises(AgentAccessValidationError, match="agee"):
        validate_agent_access_patch(
            {"question_settings": {"agee": {"instructions": "A rough age is fine."}}},
            SURVEY,
        )


def test_with_a_survey_any_name_can_still_be_cleared():
    # So a setting stored under a misspelled name can be removed.
    validate_agent_access_patch({"question_settings": {"agee": None}}, SURVEY)
