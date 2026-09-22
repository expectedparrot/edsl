import random

import pytest

from edsl import Agent, Model, QuestionMultipleChoice, Survey


@pytest.mark.parametrize(
    "pins, expected",
    [
        (["Other"], ["Beta", "Fixed", "Alpha", "Other"]),
        (["Fixed", "Other"], ["Beta", "Fixed", "Alpha", "Other"]),
        (["Alpha", "Fixed", "Beta", "Other"], ["Alpha", "Fixed", "Beta", "Other"]),
        ([], ["Other", "Beta", "Fixed", "Alpha"]),
    ],
)
def test_runner_pins_match_prompts_and_translated_answers(monkeypatch, pins, expected):
    # Force a non-identity permutation without relying on random draws differing.
    monkeypatch.setattr(
        random, "sample", lambda population, k: list(reversed(population))
    )
    prompts = []

    def first_option(user_prompt, system_prompt, files_list):
        prompts.append(user_prompt)
        return "0"

    original = ["Alpha", "Fixed", "Beta", "Other"]
    question = QuestionMultipleChoice(
        question_name="pick",
        question_text="Pick one.",
        question_options=original,
        use_code=True,
    )
    survey = Survey(
        [question],
        questions_to_randomize=["pick"],
        options_to_pin={"pick": pins},
    )
    results = survey.by(Model("test", func=first_option)).run(
        n=2,
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exception=True,
    )

    assert results.select("question_options.pick").to_list() == [expected, expected]
    assert results.select("answer.pick").to_list() == [expected[0], expected[0]]
    assert len(prompts) == 2
    for prompt in prompts:
        positions = [prompt.index(option) for option in expected]
        assert positions == sorted(positions)
    assert question.question_options == original


def test_direct_answer_receives_the_recorded_permutation(monkeypatch):
    monkeypatch.setattr(
        random, "sample", lambda population, k: list(reversed(population))
    )
    seen = []

    def answer_question_directly(self, question, scenario):
        seen.append(list(question.question_options))
        answer = question.question_options[0]
        question.question_options.reverse()  # Must not mutate another interview.
        return answer

    agent = Agent()
    agent.add_direct_question_answering_method(answer_question_directly)
    question = QuestionMultipleChoice(
        question_name="pick",
        question_text="Pick one.",
        question_options=["Alpha", "Beta", "Other"],
    )
    survey = Survey(
        [question],
        questions_to_randomize=["pick"],
        options_to_pin={"pick": ["Other"]},
    )
    results = (
        survey.by(agent)
        .by(Model("test"))
        .run(
            n=2,
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exception=True,
        )
    )

    assert seen == [["Beta", "Alpha", "Other"]] * 2
    assert results.select("question_options.pick").to_list() == seen
    assert results.select("answer.pick").to_list() == ["Beta", "Beta"]
    assert question.question_options == ["Alpha", "Beta", "Other"]
