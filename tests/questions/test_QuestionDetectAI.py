import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from edsl import (
    Agent,
    DetectAI,
    Model,
    QuestionBase,
    QuestionDetectAI,
    Scenario,
    Survey,
)
from edsl.questions import Question, QuestionCompute, QuestionFreeText
from edsl.results import Results


@pytest.fixture
def pangram(monkeypatch):
    payload = {
        "stage": "STAGE_SUCCESS",
        "fraction_ai": 0.9,
        "fraction_human": 0.1,
        "fraction_ai_assisted": 0.0,
        "windows": [{"text": "Sample text", "label": "AI-Generated"}],
        "future_field": {"nested": [True, None, 42]},
    }
    client = Mock()
    client.predict.return_value = payload
    factory = Mock(return_value=client)
    monkeypatch.setitem(sys.modules, "pangram", SimpleNamespace(Pangram=factory))
    monkeypatch.setenv("PANGRAM_API_KEY", "test-key")
    return factory, client, payload


def test_registration_and_serialization(pangram):
    q = DetectAI(
        "detection", question_text="{{ passage }}", timeout=42, poll_interval=0.2
    )
    assert DetectAI is QuestionDetectAI
    assert isinstance(
        Question("detect_ai", question_name="detection", question_text="hello"),
        QuestionDetectAI,
    )
    serialized = q.to_dict()
    assert "test-key" not in str(serialized)
    restored = QuestionBase.from_dict(serialized)
    assert restored == q
    assert restored.timeout == 42
    assert restored.poll_interval == 0.2
    assert q.parameters == {"passage"}
    assert q.render({"passage": "Test passage"}).question_text == "Test passage"
    pangram[0].assert_not_called()


@pytest.mark.parametrize("suffix", [".json", ".json.gz"])
def test_question_file_roundtrip(pangram, tmp_path, suffix):
    question = DetectAI(
        "detection", question_text="{{ passage }}", timeout=42, poll_interval=0.2
    )
    path = tmp_path / f"detection{suffix}"
    question.save(path)
    restored = QuestionBase.load(path)
    assert isinstance(restored, QuestionDetectAI)
    assert restored.to_dict() == question.to_dict()
    assert (
        restored.answer_question_directly({"passage": "Sample text"})["answer"]
        == pangram[2]
    )
    assert pangram[1].predict.call_args.kwargs["timeout"] == 42
    assert pangram[1].predict.call_args.kwargs["poll_interval"] == 0.2


@pytest.mark.parametrize("as_jobs", [False, True])
def test_survey_and_jobs_package_roundtrip(pangram, tmp_path, as_jobs):
    survey = Survey(
        [
            DetectAI(
                "detection",
                question_text="{{ passage }}",
                timeout=42,
                poll_interval=0.2,
            ),
            QuestionCompute("score", "{{ detection.answer.fraction_ai }}"),
        ]
    ).add_skip_rule("score", "detection['fraction_ai'] < 0.5")
    obj = (
        survey.by(Scenario({"passage": "Sample text"})).by(Model("test"))
        if as_jobs
        else survey
    )
    path = tmp_path / "detection.ep"
    obj.save(path)
    restored = type(obj).load(path)
    assert restored.to_dict() == obj.to_dict()
    restored_survey = restored.survey if as_jobs else restored
    assert isinstance(restored_survey.questions[0], QuestionDetectAI)
    assert "test-key" not in str(restored.to_dict())
    pangram[0].assert_not_called()


@pytest.mark.parametrize(
    "scenario", [{"document": "Sample text"}, Scenario({"document": "Sample text"})]
)
def test_full_json_answer_from_scenario(pangram, scenario):
    factory, client, payload = pangram
    q = DetectAI("detection", question_text="{{ document }}")
    result = q.answer_question_directly(scenario)
    assert result["answer"] == payload
    factory.assert_called_once_with(api_key="test-key")
    client.predict.assert_called_once_with(
        "Sample text",
        model="default",
        public_dashboard_link=False,
        timeout=300,
        poll_interval=0.5,
    )


def test_literal_text(pangram):
    DetectAI("detection", question_text="Literal passage").answer_question_directly({})
    assert pangram[1].predict.call_args.args == ("Literal passage",)


def test_missing_key(pangram, monkeypatch):
    monkeypatch.delenv("PANGRAM_API_KEY")
    with pytest.raises(ValueError, match="PANGRAM_API_KEY"):
        DetectAI("detection", question_text="Passage").answer_question_directly({})
    pangram[0].assert_not_called()


def test_missing_sdk(pangram, monkeypatch):
    monkeypatch.setitem(sys.modules, "pangram", None)
    with pytest.raises(ImportError, match="pip install --upgrade pangram-sdk"):
        DetectAI("detection", question_text="Passage").answer_question_directly({})


@pytest.mark.parametrize("text", ["", "   ", "{{ missing }}"])
def test_empty_text_never_calls_pangram(pangram, text):
    with pytest.raises(ValueError, match="non-empty"):
        DetectAI("detection", question_text=text).answer_question_directly({})
    pangram[0].assert_not_called()


@pytest.mark.parametrize("name", ["timeout", "poll_interval"])
@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan"), True, "3"])
def test_invalid_timing(name, value):
    with pytest.raises(ValueError, match=name):
        DetectAI("detection", question_text="Passage", **{name: value})


def test_question_text_is_required():
    from edsl.questions.exceptions import QuestionInitializationError

    with pytest.raises(
        QuestionInitializationError, match="Missing required parameters"
    ):
        DetectAI(question_name="detection")


def test_text_alias_is_rejected():
    from edsl.questions.exceptions import QuestionInitializationError

    with pytest.raises(QuestionInitializationError, match="Unknown parameter 'text'"):
        DetectAI(question_name="detection", text="Passage")


@pytest.mark.parametrize("error", [TimeoutError("timed out"), ValueError("API error")])
def test_api_errors_propagate(pangram, error):
    pangram[1].predict.side_effect = error
    with pytest.raises(type(error), match=str(error)):
        DetectAI("detection", question_text="Passage").answer_question_directly({})


def test_failed_task_is_not_an_answer(pangram):
    pangram[1].predict.return_value = {"stage": "STAGE_FAILED", "fraction_ai": 0}
    with pytest.raises(ValueError, match="Pangram failed"):
        DetectAI("detection", question_text="Passage").answer_question_directly({})


def test_non_object_response_rejected(pangram):
    pangram[1].predict.return_value = "AI"
    with pytest.raises(ValidationError):
        DetectAI("detection", question_text="Passage").answer_question_directly({})


def test_detect_sends_text_unrendered(pangram):
    q = DetectAI("detection", question_text="{{ passage }}")
    result = q.detect("I wrote {{ this }} myself.")
    assert result == {"answer": pangram[2], "comment": None, "generated_tokens": None}
    assert pangram[1].predict.call_args.args == ("I wrote {{ this }} myself.",)


def test_detect_sends_pangram_parameters(pangram):
    q = DetectAI("detection", question_text="Passage", timeout=42, poll_interval=0.2)
    q.detect("Passage")
    kwargs = pangram[1].predict.call_args.kwargs
    sent = {k: v for k, v in kwargs.items() if k not in ("timeout", "poll_interval")}
    assert sent == q.pangram_parameters()
    assert q.pangram_parameters() == {
        "model": "default",
        "public_dashboard_link": False,
    }


def test_detect_overrides_apply_to_one_call(pangram):
    q = DetectAI("detection", question_text="Passage", timeout=42, poll_interval=0.2)
    q.detect("Passage", api_key="caller-key", timeout=7, poll_interval=1)
    pangram[0].assert_called_once_with(api_key="caller-key")
    kwargs = pangram[1].predict.call_args.kwargs
    assert (kwargs["timeout"], kwargs["poll_interval"]) == (7, 1)
    assert (q.timeout, q.poll_interval) == (42, 0.2)


def test_detect_defaults_to_question_settings_and_env_key(pangram):
    DetectAI("detection", question_text="Passage", timeout=42).detect("Passage")
    pangram[0].assert_called_once_with(api_key="test-key")
    assert pangram[1].predict.call_args.kwargs["timeout"] == 42


@pytest.mark.parametrize("text", ["", "   ", None])
def test_detect_blank_text_never_calls_pangram(pangram, text):
    with pytest.raises(ValueError, match="non-empty"):
        DetectAI("detection", question_text="Passage").detect(text)
    pangram[0].assert_not_called()


def test_detect_blank_key_is_rejected(pangram):
    with pytest.raises(ValueError, match="api_key"):
        DetectAI("detection", question_text="Passage").detect("Passage", api_key=" ")
    pangram[0].assert_not_called()


@pytest.mark.parametrize("name", ["timeout", "poll_interval"])
@pytest.mark.parametrize("value", [0, -1, float("inf"), True])
def test_detect_invalid_timing(pangram, name, value):
    with pytest.raises(ValueError, match=name):
        DetectAI("detection", question_text="Passage").detect(
            "Passage", **{name: value}
        )
    pangram[0].assert_not_called()


def test_detect_rejects_non_object_response(pangram):
    pangram[1].predict.return_value = "AI"
    with pytest.raises(ValidationError):
        DetectAI("detection", question_text="Passage").detect("Passage")


@pytest.mark.asyncio
async def test_async_execution_uses_worker_thread(pangram):
    thread_ids = []

    def predict(*args, **kwargs):
        thread_ids.append(threading.get_ident())
        return pangram[2]

    pangram[1].predict.side_effect = predict
    result = await DetectAI(
        "detection", question_text="Passage"
    ).async_answer_question_directly({})
    assert result["answer"] == pangram[2]
    assert thread_ids[0] != threading.get_ident()


@pytest.mark.asyncio
async def test_invigilator_pipes_prior_answers_and_awaits_detection(pangram):
    thread_ids = []

    def predict(*args, **kwargs):
        thread_ids.append(threading.get_ident())
        return pangram[2]

    pangram[1].predict.side_effect = predict
    source = QuestionFreeText("essay", "Write a passage")
    detection = DetectAI("detection", question_text="{{ essay.answer }}")
    response = await Agent().async_answer_question(
        question=detection,
        scenario=Scenario(),
        survey=Survey([source, detection]),
        model=Model("test"),
        current_answers={"essay": "Sample text"},
        cache=False,
    )
    assert response.answer == pangram[2]
    assert pangram[1].predict.call_args.args == ("Sample text",)
    assert thread_ids[0] != threading.get_ident()


def test_no_llm_cost_estimate():
    from edsl.jobs.cost_estimation.question_estimators import _build_default_registry

    estimate = _build_default_registry(4)["detect_ai"](
        DetectAI("detection", question_text="Passage"), {}
    )
    assert estimate.billable is False


@pytest.mark.parametrize("fraction_ai, skipped", [(0.9, True), (0.1, False)])
def test_survey_piping_skip_rules_and_result_roundtrip(
    pangram, fraction_ai, skipped, tmp_path
):
    pangram[2]["fraction_ai"] = fraction_ai
    source = QuestionCompute("essay", "{{ passage }}")
    detection = DetectAI("detection", question_text="{{ essay.answer }}")
    followup = QuestionCompute("score", "{{ detection.answer.fraction_ai }}")
    conditional = QuestionCompute("conditional", "Reached follow-up")
    survey = Survey([source, detection, followup, conditional]).add_skip_rule(
        "conditional", "detection['fraction_ai'] > 0.5"
    )
    results = (
        survey.by(Scenario({"passage": "Sample text"}))
        .by(Model("test"))
        .run(
            disable_remote_inference=True,
            disable_remote_cache=True,
            stop_on_exception=True,
            cache=False,
        )
    )
    answer = results[0].answer
    assert answer["detection"] == pangram[2]
    assert answer["score"] == fraction_ai
    assert answer.get("conditional") == (None if skipped else "Reached follow-up")
    assert pangram[1].predict.call_args.args == ("Sample text",)
    restored = Results.from_dict(results.to_dict())
    assert restored[0].answer["detection"] == pangram[2]
    for suffix in (".json", ".json.gz", ".ep"):
        path = tmp_path / f"results{suffix}"
        results.save(path)
        loaded = Results.load(path)
        assert isinstance(loaded.survey.questions[1], QuestionDetectAI)
        assert loaded[0].answer == answer
        assert "test-key" not in str(loaded.to_dict())


def test_pangram_fields_pipe_into_llm_prompt(pangram):
    prompts = []

    def respond(user_prompt, system_prompt, files_list):
        prompts.append(user_prompt)
        return "Review the passage."

    survey = Survey(
        [
            DetectAI("detection", question_text="Sample text"),
            QuestionFreeText(
                "review", "Discuss this score: {{ detection.answer.fraction_ai }}"
            ),
        ]
    )
    survey.by(Model("test", func=respond)).run(
        disable_remote_inference=True,
        disable_remote_cache=True,
        stop_on_exception=True,
        cache=False,
    )
    assert len(prompts) == 1
    assert "Discuss this score: 0.9" in prompts[0]
