"""Tests for Coop.pause_human_survey and Coop.resume_human_survey.

The server response is mocked, so these tests do not need a running Coop.
"""

from unittest.mock import Mock, patch

import pytest

from edsl.coop.coop import Coop
from edsl.coop.exceptions import CoopServerResponseError

ACTIVE_URI = "api/v0/human-surveys/survey-uuid/active"


def server_response(status_code: int, content: dict) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.headers = {}
    response.text = str(content)
    response.json.return_value = content
    return response


@pytest.mark.parametrize(
    "method, is_active",
    [("pause_human_survey", False), ("resume_human_survey", True)],
)
def test_sends_the_state_and_returns_the_counts(method, is_active):
    coop = Coop(api_key="b")
    response = server_response(
        200,
        {
            "uuid": "survey-uuid",
            "is_active": is_active,
            "n_complete": 4,
            "n_in_progress": 2,
        },
    )

    with patch.object(coop, "_send_server_request", return_value=response) as send:
        result = getattr(coop, method)("survey-uuid")

    send.assert_called_once_with(
        uri=ACTIVE_URI, method="PATCH", payload={"is_active": is_active}
    )
    assert result == {
        "uuid": "survey-uuid",
        "is_active": is_active,
        "n_complete": 4,
        "n_in_progress": 2,
    }


@pytest.mark.parametrize("status_code", [403, 404])
def test_a_refused_pause_raises(status_code):
    coop = Coop(api_key="b")
    response = server_response(status_code, {"detail": "Not allowed"})

    with patch.object(coop, "_send_server_request", return_value=response):
        with pytest.raises(CoopServerResponseError):
            coop.pause_human_survey("survey-uuid")


def test_get_human_survey_reports_whether_it_is_active():
    coop = Coop(api_key="b")
    response = server_response(200, {"uuid": "survey-uuid", "is_active": False})

    with patch.object(coop, "_send_server_request", return_value=response):
        assert coop.get_human_survey("survey-uuid")["is_active"] is False
