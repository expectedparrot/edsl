"""Regression coverage for instruction-only agents (issue #2657)."""

import asyncio

import pytest

from edsl import Agent, Cache, Model, QuestionFreeText, Scenario, Survey
from edsl.invigilators.prompt_helpers import PromptPlan


@pytest.fixture
def survey():
    return Survey(
        [QuestionFreeText(question_name="name", question_text="What is your name?")]
    )


@pytest.mark.parametrize(
    "agent_kwargs, expected",
    [
        ({}, ""),
        ({"traits": {}}, ""),
        ({"instruction": Agent.default_instruction}, ""),
        ({"instruction": ""}, ""),
        ({"instruction": "You are a pirate."}, "You are a pirate."),
        (
            {"traits": {}, "instruction": "You are a pirate."},
            "You are a pirate.",
        ),
        (
            {"traits": {"age": 30}, "instruction": "You are a pirate."},
            "You are a pirate.\nYour traits: {'age': 30}",
        ),
        (
            {"traits": {"age": 30}},
            Agent.default_instruction + "\nYour traits: {'age': 30}",
        ),
        (
            {"traits": {"age": 30}, "instruction": ""},
            "Your traits: {'age': 30}",
        ),
        (
            {"traits_presentation_template": "You are a pirate."},
            "You are a pirate.",
        ),
        (
            {
                "instruction": "Stay in character.",
                "traits_presentation_template": "You are a pirate.",
            },
            "Stay in character.\nYou are a pirate.",
        ),
        (
            {"instruction": "You are a pirate.", "traits_presentation_template": ""},
            "You are a pirate.",
        ),
    ],
)
def test_agent_system_prompt(survey, agent_kwargs, expected):
    agent = Agent(**agent_kwargs)
    # Saved jobs must preserve the same prompt behavior.
    for candidate in (agent, Agent.from_dict(agent.to_dict())):
        row = survey.by(candidate).by(Model("test")).prompts().to_dicts()[0]
        assert str(row["system_prompt"]) == expected


@pytest.mark.parametrize("user_prompt_only", [False, True])
def test_instruction_only_agent_reaches_model(survey, user_prompt_only):
    captured = []

    def capture(user_prompt, system_prompt, files_list):
        captured.append((user_prompt, system_prompt))
        return "Blackbeard"

    plan = PromptPlan.user_prompt_only() if user_prompt_only else PromptPlan.default()
    invigilator = Agent(instruction="You are a pirate.").invigilator.create_invigilator(
        question=survey.questions[0],
        scenario=Scenario(),
        survey=survey,
        model=Model("test", func=capture, prompt_plan=plan),
        prompt_plan=plan,
        memory_plan=survey.memory_plan,
        current_answers={},
        cache=Cache(),
    )

    result = asyncio.run(invigilator.async_answer_question())

    assert result.answer == "Blackbeard"
    assert len(captured) == 1
    user_prompt, system_prompt = captured[0]
    if user_prompt_only:
        assert system_prompt == ""
        assert user_prompt.startswith("You are a pirate.\n")
    else:
        assert system_prompt == "You are a pirate."
