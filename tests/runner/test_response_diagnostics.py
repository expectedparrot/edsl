import copy
import json

import pytest

from edsl import Model, QuestionFreeText, QuestionNumerical, Results
from edsl.language_models.response_metadata import response_metadata
from edsl.language_models.raw_response_handler import RawResponseHandler
from edsl.language_models.exceptions import OutputTokenLimitError
from edsl.runner.runner import Runner
from edsl.runner.service import JobService


def completion(text=None, reason="length"):
    return {
        "choices": [
            {
                "finish_reason": reason,
                "message": {
                    "content": text,
                    "reasoning_content": "synthetic reasoning",
                },
            }
        ],
        "usage": {
            "prompt_tokens": 20,
            "completion_tokens": 1000,
            "total_tokens": 1020,
            "completion_tokens_details": {"reasoning_tokens": 990},
        },
    }


@pytest.mark.parametrize(
    "raw",
    [
        completion(),
        {
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "output": [{"type": "reasoning", "summary": []}],
        },
        {
            "stop_reason": "max_tokens",
            "content": [{"type": "thinking", "thinking": "reasoning"}],
        },
        {
            "candidates": [
                {
                    "finish_reason": "MAX_TOKENS",
                    "content": {"parts": [{"thought": True, "text": "reasoning"}]},
                }
            ]
        },
        {"stopReason": "max_tokens", "output": {"message": {"content": []}}},
    ],
)
def test_reasoning_only_token_exhaustion_is_classified(raw):
    metadata = response_metadata(raw)
    assert metadata["truncated"] is True
    assert metadata["visible_answer_present"] is False
    handler = RawResponseHandler(["choices", 0, "message", "content"], ["usage"])
    with pytest.raises(OutputTokenLimitError) as error:
        handler.parse_response(raw, is_free_text=True)
    assert error.value.response_json == raw


def test_truncated_parseable_answer_and_completion_usage():
    raw = completion("0.5")
    handler = RawResponseHandler(["choices", 0, "message", "content"], ["usage"])
    assert handler.parse_response(raw).answer == 0.5
    metadata = response_metadata(raw)
    assert metadata["truncated"] is True
    assert metadata["visible_answer_present"] is True
    assert metadata["reasoning_tokens"] == 990
    assert metadata["visible_output_tokens"] == 10
    assert metadata["completion_tokens"] == 1000
    assert not response_metadata(completion("0.5", "stop"))["truncated"]


def run_response(monkeypatch, raw, *, question=None, cache=False):
    model = Model("test")
    calls = []

    async def execute(**kwargs):
        calls.append(kwargs)
        if isinstance(raw, Exception):
            raise raw
        return copy.deepcopy(raw)

    monkeypatch.setattr(model, "async_execute_model_call", execute)
    monkeypatch.setattr(JobService, "get_model_for_task", lambda *args: model)
    question = question or QuestionNumerical(
        question_name="q", question_text="Return 0.5"
    )
    results = Runner().submit(question.by(model), cache=cache).results()
    return results, calls


def test_exhaustion_keeps_evidence_without_identical_retry(monkeypatch, tmp_path):
    raw = completion()
    results, calls = run_response(
        monkeypatch,
        raw,
        question=QuestionFreeText(question_name="q", question_text="Hi"),
    )
    assert len(calls) == 1
    row = results[0]
    assert row.answer["q"] is None
    assert row["raw_model_response"]["q_raw_model_response"] == raw
    assert row["prompt"]["q_user_prompt"].text
    assert row["cache_keys"]["q"]
    assert row["validated_dict"]["q_validated"] is False
    metadata = row["raw_model_response"]["q_response_metadata"]
    assert metadata["failure"]["code"] == "OUTPUT_TOKEN_LIMIT"
    assert metadata["failure"]["stage"] == "model_response"
    assert metadata["failure"]["retry_count"] == 0
    assert metadata["provider_calls_attempted"] == 1
    summary = results.completion_summary()
    assert summary["planned_interview_rows"] == 1
    assert summary["answers_produced"] == 0
    assert summary["answers_validated"] == 0
    assert summary["failed_interviews"] == 1
    assert summary["placeholder_rows"] == 0
    assert summary["truncated_responses"] == 1
    restored = Results.from_dict(json.loads(json.dumps(results.to_dict())))
    assert restored[0]["raw_model_response"] == row["raw_model_response"]
    assert restored.completion_summary() == summary
    streamed_rows = list(results.to_jsonl_rows())
    streamed = Results.from_jsonl(streamed_rows)
    assert streamed[0]["raw_model_response"] == row["raw_model_response"]
    assert streamed[0]["prompt"] == row["prompt"]
    assert streamed.completion_summary() == summary
    path = tmp_path / "exhausted.ep"
    results.git.save(path)
    loaded = Results.git.load(path)
    assert loaded[0]["raw_model_response"] == row["raw_model_response"]
    assert loaded.completion_summary() == summary


def test_parseable_truncation_remains_usable(monkeypatch):
    results, calls = run_response(monkeypatch, completion("0.5"))
    assert len(calls) == 1
    assert results[0].answer["q"] == 0.5
    summary = results.completion_summary()
    assert summary["answers_produced"] == summary["answers_validated"] == 1
    assert summary["truncated_responses"] == 1
    assert summary["failed_interviews"] == 0


def test_provider_error_keeps_prompts_and_retry_count(monkeypatch):
    results, calls = run_response(
        monkeypatch, RuntimeError("503 synthetic provider outage")
    )
    assert len(calls) == 3
    row = results[0]
    metadata = row["raw_model_response"]["q_response_metadata"]
    assert metadata["failure"]["code"] == "SERVER_ERROR"
    assert metadata["failure"]["retry_count"] == 2
    assert metadata["provider_calls_attempted"] == 3
    assert row["prompt"]["q_user_prompt"].text
    assert results.completion_summary()["failed_interviews"] == 1


def test_cached_exhaustion_does_not_count_a_new_provider_call(monkeypatch):
    from edsl import Cache

    cache = Cache()
    first, calls = run_response(monkeypatch, completion(), cache=cache)
    assert len(calls) == 1
    second, calls = run_response(monkeypatch, completion(), cache=cache)
    assert calls == []
    assert second.completion_summary()["provider_calls_attempted"] == 0
    assert (
        second[0]["raw_model_response"]["q_response_metadata"]["failure"]["code"]
        == "OUTPUT_TOKEN_LIMIT"
    )


def test_old_placeholder_is_not_reported_as_success():
    from edsl import Agent, Scenario, Survey
    from edsl.results import Result

    row = Result(
        agent=Agent(),
        scenario=Scenario(),
        model=Model("test"),
        iteration=0,
        answer={"q": None},
    )
    results = Results(
        survey=Survey([QuestionFreeText(question_name="q", question_text="Hi")]),
        data=[row],
    )
    summary = results.completion_summary()
    assert summary["row_count"] == 1
    assert summary["answers_produced"] == summary["answers_validated"] == 0
    assert summary["placeholder_rows"] == summary["unsuccessful_interviews"] == 1
    assert summary["provider_calls_attempted"] is None
    assert summary["questions_with_unknown_call_count"] == 1


def test_google_token_counts_do_not_drop_thinking():
    raw = {
        "candidates": [
            {"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "0.5"}]}}
        ],
        "usageMetadata": {
            "promptTokenCount": 20,
            "candidatesTokenCount": 10,
            "thoughtsTokenCount": 990,
            "totalTokenCount": 1020,
        },
    }
    metadata = response_metadata(raw)
    assert metadata["completion_tokens"] == 1000
    assert metadata["visible_output_tokens"] == 10
    assert metadata["reasoning_tokens"] == 990


def test_failed_attempt_history_survives_a_later_provider_error():
    from edsl.runner.storage import InMemoryStorage

    service = JobService(InMemoryStorage())
    job = QuestionNumerical(question_name="q", question_text="Hi").by(Model("test"))
    job_id, _, _ = service.submit_job(job)
    interview_id = service.jobs.get_definition(job_id).interview_ids[0]
    task_id = service.interviews.get_definition(job_id, interview_id).task_ids[0]
    raw = completion("not a number", "stop")
    service.on_task_failed(
        job_id,
        interview_id,
        task_id,
        "validation_error",
        "bad answer",
        raw_model_response=raw,
        user_prompt="Hi",
        response_metadata={"provider_calls_attempted": 1},
    )
    service.on_task_failed(
        job_id,
        interview_id,
        task_id,
        "server_error",
        "503",
        force_permanent=True,
        response_metadata={"provider_calls_attempted": 1},
    )
    row = service.build_edsl_result(job_id, interview_id)
    metadata = row["raw_model_response"]["q_response_metadata"]
    assert metadata["attempt_history"][0]["raw_model_response"] == raw
    assert metadata["attempt_history"][0]["user_prompt"] == "Hi"
    assert metadata["failure"]["retry_count"] == 1
    assert metadata["provider_calls_attempted"] == 2
