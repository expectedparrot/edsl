"""Streaming results must retain each participant's historical question."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from edsl import Agent, Model, QuestionMultipleChoice, Results, Scenario, Survey
from edsl.coop import Coop
from edsl.jobs.remote_inference import JobsRemoteInferenceHandler
from edsl.runner.presentation import capture_presentation


@pytest.mark.parametrize("captured", [True, False])
def test_streamed_results_preserve_presentation_and_legacy_fallback(
    monkeypatch, captured
):
    question = QuestionMultipleChoice(
        question_name="slot", question_text="Choose a slot", question_options=["A", "B"]
    )
    survey = Survey([question])
    state = {"version": 1, "bindings": []}
    pages = []
    presentations = []
    for index, options in enumerate((["A", "B"], ["B"])):
        shown = question.to_dict() | {
            "question_text": f"Participant {index}: choose an available slot",
            "question_options": options,
        }
        presentation = capture_presentation(
            shown, source="prompt", read_versions=((f"read-{index}", index),)
        )
        presentations.append(presentation)
        answer = {"question_name": "slot", "answer": options[0], "validated": True}
        if captured:
            answer["question_presentation"] = presentation
        pages.append(
            {
                "interviews": [
                    {
                        "agent": Agent(name=f"person-{index}").to_dict(),
                        "scenario": Scenario().to_dict(),
                        "model": Model("test").to_dict(),
                        "iteration": index,
                        "answers": [answer],
                    }
                ]
            }
        )

    monkeypatch.setattr(
        Coop,
        "remote_inference_results_manifest",
        lambda *args: {
            "total_interviews": 2,
            "page_count": 2,
            "page_size": 1,
            "shared_state": state,
        },
    )
    monkeypatch.setattr(
        Coop,
        "remote_inference_results_page",
        lambda self, jid, page, page_size: pages[page],
    )
    handler = JobsRemoteInferenceHandler(survey.by(Model("test")), api_key="test-only")
    monkeypatch.setattr(handler, "_log_results_metadata", Mock())
    logger = Mock(jobs_info=SimpleNamespace(results_url=None, results_uuid=None))
    info = SimpleNamespace(job_uuid="test-job", logger=logger)
    original_survey = deepcopy(survey.to_dict())
    results = handler._fetch_results_streamed(info, "completed", {})
    assert results.shared_state == state
    assert [row.answer["slot"] for row in results] == ["A", "B"]
    for index, row in enumerate(results):
        attrs = row.data["question_to_attributes"]["slot"]
        if captured:
            assert (
                attrs["question_options"]
                == presentations[index]["attributes"]["question_options"]
            )
            assert (
                attrs["question_text"]
                == presentations[index]["attributes"]["question_text"]
            )
            assert attrs["presentation"]["shared_state_reads"] == [
                {"read_id": f"read-{index}", "version": index}
            ]
        else:
            assert attrs["question_options"] == ["A", "B"]
            assert "presentation" not in attrs
    assert survey.to_dict() == original_survey
    restored = Results.from_dict(results.to_dict())
    assert [row.data["question_to_attributes"] for row in restored] == [
        row.data["question_to_attributes"] for row in results
    ]
    if captured:
        # Neither rows nor the source response should share mutable metadata.
        results[1].data["question_to_attributes"]["slot"]["question_options"].append(
            "C"
        )
        assert presentations[1]["attributes"]["question_options"] == ["B"]
        assert results[0].data["question_to_attributes"]["slot"][
            "question_options"
        ] == ["A", "B"]
