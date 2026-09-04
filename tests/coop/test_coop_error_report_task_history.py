"""Tests for Coop.get_error_report_task_history.

The server response is mocked, so these tests do not need a running Coop.
"""

from unittest.mock import Mock, patch

import pytest

from edsl.coop.coop import Coop

TASK_HISTORY_URI = "api/v0/remote-inference/job/job-uuid/error-report/task-history"

ENVELOPE = {
    "schema_version": "1.0",
    "job_uuid": "job-uuid",
    "results_uuid": "results-uuid",
    "error_report_uuid": "report-uuid",
    "has_task_history": True,
    "task_history": {
        "interviews": [
            {
                "type": "InterviewReference",
                "id": 0,
                "model": {"model": "gpt-4o", "inference_service": "openai"},
                "exceptions": {
                    "how_feeling": [
                        {
                            "exception": {
                                "type": "RuntimeError",
                                "message": "boom",
                                "module": "builtins",
                                "traceback": "tb",
                            },
                            "invigilator": None,
                            "time": "2026-08-12T00:00:00+00:00",
                            "additional_data": {},
                        }
                    ]
                },
            }
        ],
        "include_traceback": True,
    },
}

EMPTY_ENVELOPE = {
    "schema_version": "1.0",
    "job_uuid": "job-uuid",
    "results_uuid": None,
    "error_report_uuid": "report-uuid",
    "has_task_history": False,
    "task_history": {"interviews": [], "include_traceback": False},
}


def mocked_coop(content: dict):
    """Return a Coop whose next server request resolves to ``content``."""
    coop = Coop(api_key="b")
    response = Mock()
    response.json.return_value = content
    return coop, response


def test_get_error_report_task_history_returns_envelope():
    coop, response = mocked_coop(ENVELOPE)

    with patch.object(
        coop, "_send_server_request", return_value=response
    ) as send, patch.object(coop, "_resolve_server_response"):
        content = coop.get_error_report_task_history("job-uuid")

    send.assert_called_once_with(uri=TASK_HISTORY_URI, method="GET")
    assert content == ENVELOPE


def test_get_error_report_task_history_accepts_uuid_object():
    from uuid import UUID

    job_uuid = UUID("00000000-0000-4000-8000-000000000000")
    coop, response = mocked_coop(ENVELOPE)

    with patch.object(
        coop, "_send_server_request", return_value=response
    ) as send, patch.object(coop, "_resolve_server_response"):
        coop.get_error_report_task_history(job_uuid)

    assert str(job_uuid) in send.call_args.kwargs["uri"]


def test_get_error_report_task_history_as_object():
    coop, response = mocked_coop(ENVELOPE)

    with patch.object(
        coop, "_send_server_request", return_value=response
    ), patch.object(coop, "_resolve_server_response"):
        task_history = coop.get_error_report_task_history("job-uuid", as_object=True)

    from edsl.tasks import TaskHistory

    assert isinstance(task_history, TaskHistory)
    assert task_history.has_exceptions is True
    assert task_history.total_interviews[0].exceptions.num_exceptions() == 1


def test_get_error_report_task_history_as_object_when_empty():
    """A report stored without a task history yields an empty TaskHistory."""
    coop, response = mocked_coop(EMPTY_ENVELOPE)

    with patch.object(
        coop, "_send_server_request", return_value=response
    ), patch.object(coop, "_resolve_server_response"):
        task_history = coop.get_error_report_task_history("job-uuid", as_object=True)

    assert task_history.total_interviews == []
    assert task_history.has_exceptions is False


def test_get_error_report_task_history_propagates_server_errors():
    """Ownership and missing-report errors are raised by _resolve_server_response."""
    from edsl.coop.exceptions import CoopServerResponseError

    coop, response = mocked_coop(ENVELOPE)

    with patch.object(
        coop, "_send_server_request", return_value=response
    ), patch.object(
        coop,
        "_resolve_server_response",
        side_effect=CoopServerResponseError("Not found"),
    ):
        with pytest.raises(CoopServerResponseError):
            coop.get_error_report_task_history("job-uuid")
