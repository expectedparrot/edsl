import json
import random

import pytest

from edsl import (
    Agent,
    Model,
    QuestionList,
    QuestionMultipleChoice,
    Scenario,
    ScenarioList,
    Survey,
)
from edsl.runner import Runner
from edsl.runner.models import InterviewDefinition
from edsl.runner.render import RenderService
from edsl.runner.service import JobService
from edsl.questions.probabilistic_response import ProbabilisticResponse


@pytest.mark.parametrize("source", ["scenario", "prior_answer", "prior_with_other"])
def test_dynamic_options_match_prompts_codes_and_results(monkeypatch, source):
    monkeypatch.setattr(random, "getrandbits", lambda bits: 0)
    options = ["Alpha", "Beta", "Gamma", "Other"]
    questions = []
    if source == "scenario":
        option_spec = "{{ scenario.options }}"
    else:
        questions.append(
            QuestionList(question_name="pool", question_text="List the options.")
        )
        option_spec = "{{ pool.answer }}"
        if source == "prior_with_other":
            option_spec = {"from": "{{ pool.answer }}", "add": ["Other"]}
    question = QuestionMultipleChoice(
        question_name="pick",
        question_text="Pick one.",
        question_options=option_spec,
        use_code=True,
    )
    questions.append(question)
    survey = Survey(
        questions,
        questions_to_randomize=["pick"],
        options_to_pin={"pick": ["Other"]},
    )
    prompts = []

    def response(user_prompt, system_prompt, files_list):
        if "List the options." in user_prompt:
            return json.dumps(options[:-1] if source == "prior_with_other" else options)
        prompts.append(user_prompt)
        return "0"

    job = survey.by(Model("test", func=response))
    if source == "scenario":
        job = job.by(ScenarioList.from_list("options", [options]))
    results = job.run(
        n=2,
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exception=True,
    )

    expected = ["Beta", "Gamma", "Alpha", "Other"]
    assert results.select("question_options.pick").to_list() == [expected] * 2
    assert results.select("answer.pick").to_list() == ["Beta"] * 2
    assert len(prompts) == 2
    for prompt in prompts:
        positions = [prompt.index(option) for option in expected]
        assert positions == sorted(positions)
    assert question.question_options == option_spec


@pytest.mark.parametrize("probabilistic", [False, True])
def test_dynamic_direct_answers_are_isolated_and_recorded(monkeypatch, probabilistic):
    monkeypatch.setattr(random, "getrandbits", lambda bits: 0)
    seen = []

    def answer_question_directly(self, question, scenario):
        seen.append((scenario["respondent"], list(question.question_options)))
        answer = question.question_options[0]
        question.question_options.reverse()
        return {"probabilities": [1, 0, 0, 0]} if probabilistic else answer

    agent = Agent()
    agent.add_direct_question_answering_method(answer_question_directly)
    question = QuestionMultipleChoice(
        question_name="pick",
        question_text="Pick one.",
        question_options="{{ scenario.options }}",
        probabilistic_response=(
            ProbabilisticResponse(resolution="mode") if probabilistic else None
        ),
    )
    scenarios = ScenarioList(
        [
            Scenario(
                {"respondent": "first", "options": ["Alpha", "Beta", "Gamma", "Other"]}
            ),
            Scenario(
                {"respondent": "second", "options": ["One", "Two", "Three", "Other"]}
            ),
        ]
    )
    results = (
        Survey(
            [question],
            questions_to_randomize=["pick"],
            options_to_pin={"pick": ["Other"]},
        )
        .by(scenarios)
        .by(agent)
        .by(Model("test"))
        .run(
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exception=True,
        )
    )

    recorded = dict(
        results.select("scenario.respondent", "question_options.pick").to_list()
    )
    assert (
        dict(seen)
        == recorded
        == {
            "first": ["Beta", "Gamma", "Alpha", "Other"],
            "second": ["Two", "Three", "One", "Other"],
        }
    )
    assert scenarios[0]["options"] == ["Alpha", "Beta", "Gamma", "Other"]
    assert question.question_options == "{{ scenario.options }}"
    assert dict(results.select("scenario.respondent", "answer.pick").to_list()) == {
        "first": "Beta",
        "second": "Two",
    }


def test_stored_draws_survive_reload_and_repeated_rendering(monkeypatch):
    seeds = iter([0, 1])
    monkeypatch.setattr(random, "getrandbits", lambda bits: next(seeds))
    question = QuestionMultipleChoice(
        question_name="pick",
        question_text="Pick one.",
        question_options="{{ scenario.options }}",
        use_code=True,
    )
    survey = Survey(
        [question],
        questions_to_randomize=["pick"],
        options_to_pin={"pick": ["Other"]},
    )
    runner = Runner()
    handle = runner.submit(
        survey.by(
            ScenarioList.from_list("options", [["Alpha", "Beta", "Gamma", "Other"]])
        ).by(Model("test", canned_response="0")),
        n=2,
        cache=False,
    )
    definitions = runner.service._jobs.get_definition(handle.job_id)
    renderer = RenderService(runner._storage)
    expected = [
        ["Beta", "Gamma", "Alpha", "Other"],
        ["Alpha", "Gamma", "Beta", "Other"],
    ]
    for index, interview_id in enumerate(definitions.interview_ids):
        original = runner.service._interviews.get_definition(
            handle.job_id, interview_id
        )
        stored = json.loads(json.dumps(original.to_dict()))
        restored = InterviewDefinition.from_dict(interview_id, handle.job_id, stored)
        assert restored.question_option_randomizations == {
            "pick": {"seed": index, "pin_options": ["Other"]}
        }
        runner.service._interviews.create(restored)
        first = renderer.render_task(handle.job_id, interview_id, restored.task_ids[0])
        random.random()  # Unrelated global RNG usage cannot change the stored draw.
        second = renderer.render_task(handle.job_id, interview_id, restored.task_ids[0])
        assert first.user_prompt == second.user_prompt
        assert first.cache_key == second.cache_key
        positions = [first.user_prompt.index(option) for option in expected[index]]
        assert positions == sorted(positions)

    # Batch rendering/execution must agree with the single-task rendering path.
    results = handle.results(stop_on_exception=True)
    assert results.select("question_options.pick").to_list() == expected
    assert results.select("answer.pick").to_list() == ["Beta", "Alpha"]


def test_old_interview_definitions_have_no_deferred_draw():
    definition = InterviewDefinition.from_dict(
        "interview",
        "job",
        {
            "scenario_id": "scenario",
            "agent_id": "agent",
            "model_id": "model",
            "total_tasks": 0,
            "task_ids": [],
        },
    )
    assert definition.question_option_randomizations == {}
    options = ["Alpha", "Beta"]
    assert (
        JobService._resolve_interview_options(
            {"question_name": "pick", "question_options": "{{ scenario.options }}"},
            definition,
            {},
            {"options": options},
        )
        == options
    )


def test_unresolved_options_are_not_shuffled_or_replaced_with_placeholders():
    definition = InterviewDefinition(
        interview_id="interview",
        job_id="job",
        scenario_id="scenario",
        agent_id="agent",
        model_id="model",
        total_tasks=0,
        task_ids=[],
        question_option_randomizations={"pick": {"seed": 0, "pin_options": []}},
    )
    question_data = {
        "question_name": "pick",
        "question_options": "{{ missing.answer }}",
    }
    with pytest.raises(ValueError, match="must resolve to a list"):
        JobService._resolve_interview_options(question_data, definition, {}, {})
    # A failed/skipped question must not prevent collection of other results.
    assert (
        JobService._resolve_interview_options(
            question_data,
            definition,
            {},
            {},
            strict=False,
        )
        == "{{ missing.answer }}"
    )
