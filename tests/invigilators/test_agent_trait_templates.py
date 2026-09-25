"""Agent traits take precedence over Python attributes in templates (#2659)."""

import asyncio

import pytest
from jinja2 import StrictUndefined
from jinja2.exceptions import SecurityError

from edsl import Agent, Cache, Model, QuestionFreeText, Scenario, Survey
from edsl.utilities.jinja import make_environment, make_native_environment


@pytest.mark.parametrize(
    "name",
    ["prompt", "instruction", "traits", "duplicate", "codebook", "to_dict", "round"],
)
@pytest.mark.parametrize("notation", ["dot", "bracket"])
def test_question_prompts_use_colliding_traits(name, notation):
    agent = Agent(traits={name: "TRAIT-VALUE"})
    expression = f"agent.{name}" if notation == "dot" else f"agent['{name}']"
    question = QuestionFreeText(
        question_name="choice", question_text="{{ " + expression + " }}"
    )
    for candidate in (agent, Agent.from_dict(agent.to_dict())):
        row = Survey([question]).by(candidate).by(Model("test")).prompts().to_dicts()[0]
        assert str(row["user_prompt"]) == "TRAIT-VALUE"
        assert str(question.prompt_preview(agent=candidate)) == "TRAIT-VALUE"


@pytest.mark.parametrize("expression", ["agent.prompt", "agent['prompt']"])
@pytest.mark.parametrize(
    "value", ["", None, False, 0, ["red", "blue"], {"color": "red"}]
)
def test_trait_lookup_preserves_native_values(expression, value):
    template = make_native_environment().from_string("{{ " + expression + " }}")
    assert template.render(agent=Agent(traits={"prompt": value})) == value


def test_noncolliding_attributes_and_python_methods_remain_available():
    agent = Agent(name="Ada", traits={"prompt": "trait text", "age": 30})
    template = make_environment().from_string(
        "{{ agent.name }}|{{ agent.instruction }}|{{ agent.traits.age }}|{{ agent.age }}"
    )
    assert template.render(agent=agent) == f"Ada|{Agent.default_instruction}|30|30"
    assert callable(agent.prompt)
    assert "trait text" in agent.prompt().text
    assert agent.to_dict()["traits"]["prompt"] == "trait text"


def test_dynamic_traits_are_resolved_for_current_question():
    def traits(question):
        return {"prompt": question.question_text}

    agent = Agent(dynamic_traits_function=traits)
    template = make_environment().from_string("{{ agent.prompt }}")
    for text in ("First question", "Second question"):
        agent.current_question = QuestionFreeText(question_name="q", question_text=text)
        assert template.render(agent=agent) == text


@pytest.mark.parametrize("expression", ["agent._private", "agent['_private']"])
def test_trait_lookup_respects_attribute_sandbox(expression):
    template = make_environment(undefined=StrictUndefined).from_string(
        "{{ " + expression + " }}"
    )
    with pytest.raises(SecurityError):
        template.render(agent=Agent(traits={"_private": "hidden"}))


def test_agent_method_calls_remain_blocked():
    template = make_environment().from_string("{{ agent.to_dict() }}")
    with pytest.raises(SecurityError):
        template.render(agent=Agent())


def test_colliding_trait_reaches_model():
    captured = []

    def capture(user_prompt, system_prompt, files_list):
        captured.append(user_prompt)
        return "ok"

    question = QuestionFreeText(
        question_name="choice", question_text="{{ agent.prompt }}"
    )
    survey = Survey([question])
    invigilator = Agent(
        traits={"prompt": "Participant's round text"}
    ).invigilator.create_invigilator(
        question=question,
        survey=survey,
        scenario=Scenario(),
        model=Model("test", func=capture),
        memory_plan=survey.memory_plan,
        current_answers={},
        cache=Cache(),
    )
    result = asyncio.run(invigilator.async_answer_question())
    assert result.answer == "ok"
    assert captured == ["Participant's round text"]
