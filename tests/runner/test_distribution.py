"""Distribution contracts through real execution and durable object formats."""

import asyncio
import json

import pytest
from click.testing import CliRunner

from edsl import (
    Agent,
    Cache,
    Jobs,
    Model,
    QuestionDistribution,
    Results,
    Scenario,
    Survey,
)
from edsl.object_store.store import ObjectStore
from edsl.surveys.memory import MemoryPlan


@pytest.fixture(autouse=True)
def isolated_object_store(monkeypatch, tmp_path):
    monkeypatch.setattr(
        ObjectStore, "default_root", staticmethod(lambda: tmp_path / "objects")
    )


def run(question, agent=None, text=None):
    job = question.by(
        Model("test", canned_response=text or '{"a":0.2,"b":0.2,"c":0.6}')
    )
    if agent is not None:
        job = job.by(agent)
    return job.run(
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exception=True,
    )


@pytest.mark.parametrize(
    "config, answer",
    [
        ({"question_options": ["a", "b", "c"]}, {"a": 0.2, "b": 0.2, "c": 0.6}),
        ({"bins": ["[0,10)", "[10, Inf]"]}, {"[0,10)": 0.2, "[10,Inf)": 0.8}),
        (
            {"min_value": 0, "max_value": 25, "bucket_size": 10},
            {"[0,10)": 0.2, "[10,20)": 0.5, "[20,25]": 0.3},
        ),
    ],
)
def test_runner_and_package_roundtrips(config, answer, tmp_path):
    q = QuestionDistribution("forecast", "Predict.", **config)
    survey = Survey([q])
    assert Survey.from_jsonl(survey.to_jsonl()).questions[0] == q
    for obj, name, cls in [
        (survey, "survey", Survey),
        (q.by(Model("test")), "jobs", Jobs),
    ]:
        path = tmp_path / f"{name}.ep"
        obj.save(str(path))
        restored = cls.load(str(path))
        assert (restored if name == "survey" else restored.survey).questions[0] == q
    result = run(q, text=json.dumps(answer, indent=2))
    assert result.select("answer.forecast").to_list() == [answer]
    assert Results.from_jsonl(result.to_jsonl()).select(
        "answer.forecast"
    ).to_list() == [answer]
    path = tmp_path / "results.ep"
    result.save(str(path))
    assert Results.load(str(path)).select("answer.forecast").to_list() == [answer]


@pytest.mark.parametrize(
    "options, answer",
    [
        (["a", "b", "c"], {"c": 0.6, "a": 0.2, "b": 0.2}),
        (["answer", "other"], {"answer": 0.2, "other": 0.8}),
    ],
)
def test_direct_agent_answer_is_validated_and_ordered(options, answer):
    def answer_question_directly(self, question, scenario):
        return answer

    agent = Agent()
    agent.add_direct_question_answering_method(answer_question_directly)
    q = QuestionDistribution("forecast", "Predict.", question_options=options)
    result = run(q, agent)
    observed = result.select("answer.forecast").to_list()[0]
    assert observed == answer and list(observed) == options


def test_invalid_direct_answer_fails():
    def answer_question_directly(self, question, scenario):
        return {"a": 0.2, "b": 0.2, "c": 0.2}

    agent = Agent()
    agent.add_direct_question_answering_method(answer_question_directly)
    with pytest.raises(Exception):
        run(QuestionDistribution.example(), agent)


@pytest.mark.parametrize("direct", [False, True])
def test_legacy_invigilator(direct):
    q = QuestionDistribution(
        "forecast",
        "Predict for {{ topic }}.",
        bins=["(-Inf,0)", "[0,Inf)"],
        min_value="-Inf",
        max_value="Inf",
    )
    answer = {"(-Inf,0)": 0.2, "[0,Inf)": 0.8}
    agent = Agent()
    if direct:

        def answer_question_directly(self, question, scenario):
            return answer

        agent.add_direct_question_answering_method(answer_question_directly)
    survey = Survey([q])
    invigilator = agent.invigilator.create_invigilator(
        question=q,
        scenario=Scenario({"topic": "growth"}),
        survey=survey,
        model=Model("test", canned_response=json.dumps(answer)),
        memory_plan=MemoryPlan(survey=survey),
        current_answers={},
        cache=Cache(),
    )
    result = asyncio.run(invigilator.async_answer_question())
    assert result.validated is True
    assert result.answer == answer


def test_cli_schema_and_validation():
    from edsl.__main__ import app

    runner = CliRunner()
    for args in [
        ["schema", "list"],
        ["schema", "show", "--question_type", "distribution"],
        ["validate", "--json", json.dumps(QuestionDistribution.example().to_dict())],
    ]:
        result = runner.invoke(app, args)
        payload = json.loads(result.output)
        assert result.exit_code == 0, payload
        assert payload["status"] == "ok"
        assert payload["warnings"] == []
    invalid = runner.invoke(
        app,
        [
            "validate",
            "--json",
            json.dumps(
                {
                    "type": "distribution",
                    "question_name": "x",
                    "question_text": "Predict.",
                    "bins": ["[0,10)", "[11,20]"],
                }
            ),
        ],
    )
    payload = json.loads(invalid.output)
    assert invalid.exit_code == 5
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "VALIDATION_ERROR"


def test_humanize_rejects_before_remote_calls(monkeypatch):
    from edsl import Coop

    def unexpected(*args, **kwargs):
        pytest.fail("No remote call should be made for an unsupported question.")

    monkeypatch.setattr(Coop, "push", unexpected)
    with pytest.raises(Exception, match="not yet supported by hosted Humanize"):
        Coop(api_key="test").create_human_survey(
            survey=Survey([QuestionDistribution.example()]),
            human_survey_name="Distribution",
        )


def test_worker_transport_and_downstream_piping():
    from edsl import QuestionNumerical
    from edsl.runner.serialization import serialize_job, deserialize_job

    q = QuestionDistribution("forecast", "Predict.", bins=["[0,10)", "[10,Inf)"])
    followup = QuestionNumerical(
        "check", "Copy this probability: {{ forecast.answer['[10,Inf)'] }}"
    )
    prompts = []

    def respond(user_prompt, system_prompt, files_list):
        prompts.append(user_prompt)
        if "Copy this probability" in user_prompt:
            return "0.8"
        return '{"[0,10)":0.2,"[10,Inf)":0.8}'

    # Exercise the same JSON representation sent to a remote worker locally.
    job = Survey([q, followup]).by(Model("test"))
    restored = deserialize_job(
        json.loads(json.dumps(serialize_job(job), allow_nan=False))
    )
    assert restored.survey.questions[0] == q
    # Replace the transport test model explicitly, without emitting the ordinary
    # warning about chaining two model selections.
    restored.models = [Model("test", func=respond)]
    results = restored.run(
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exception=True,
    )
    assert results.select("answer.check").to_list() == [0.8]
    assert any("Copy this probability: 0.8" in prompt for prompt in prompts)


def test_example_results_uses_valid_json():
    results = QuestionDistribution.example_results()
    assert results.select("answer.outcome").to_list() == [{"a": 1, "b": 0, "c": 0}]


def test_cli_run_select_and_export(tmp_path):
    from edsl.__main__ import app

    answer = {"[0,10)": 0.2, "[10,Inf)": 0.8}
    q = QuestionDistribution("forecast", "Predict.", bins=list(answer))
    job_path = tmp_path / "job.ep"
    result_path = tmp_path / "result.ep"
    export_path = tmp_path / "answers.json"
    q.by(Model("test", canned_response=json.dumps(answer))).save(str(job_path))
    runner = CliRunner()

    def invoke(args):
        result = runner.invoke(app, args)
        payload = json.loads(result.output)
        assert result.exit_code == 0, payload
        assert payload["status"] == "ok", payload
        assert payload["warnings"] == [], payload
        return payload["data"]

    invoke(["run", str(job_path), "--local", "--fresh", "--output", str(result_path)])
    selected = invoke(
        ["results", "select", "--file", str(result_path), "--column", "answer.forecast"]
    )
    assert selected["data"] == [{"answer.forecast": answer}]
    invoke(
        [
            "results",
            "export",
            str(result_path),
            "--column",
            "answer.forecast",
            "--format",
            "json",
            "--output",
            str(export_path),
        ]
    )
    assert json.loads(export_path.read_text()) == [{"answer.forecast": answer}]
