"""Tests for PromptPlan exposure via Model (Issue #1167)."""

import pytest

from edsl.invigilators.prompt_helpers import PromptPlan, PromptComponent


# 1. Convenience constructors

def test_prompt_plan_default():
    pp = PromptPlan.default()
    assert pp.system_prompt_order == (
        PromptComponent.AGENT_INSTRUCTIONS,
        PromptComponent.AGENT_PERSONA,
    )
    assert pp.user_prompt_order == (
        PromptComponent.QUESTION_INSTRUCTIONS,
        PromptComponent.PRIOR_QUESTION_MEMORY,
    )


def test_prompt_plan_user_prompt_only():
    pp = PromptPlan.user_prompt_only()
    assert pp.system_prompt_order == ()
    assert len(pp.user_prompt_order) == 4
    assert set(pp.user_prompt_order) == set(PromptComponent)


# 2. Empty system prompt produces empty Prompt

def test_user_prompt_only_produces_empty_system():
    pp = PromptPlan.user_prompt_only()
    result = pp.get_prompts(
        agent_instructions="Be helpful.",
        agent_persona="You are 30.",
        question_instructions="What color?",
        prior_question_memory="",
    )
    assert result["system_prompt"].text == ""
    assert "Be helpful" in result["user_prompt"].text
    assert "What color" in result["user_prompt"].text


# 3. Serialization roundtrip

def test_prompt_plan_serialization():
    for pp in [PromptPlan.default(), PromptPlan.user_prompt_only()]:
        restored = PromptPlan.from_dict(pp.to_dict())
        assert restored == pp


# 4. Model serialization

def test_model_with_prompt_plan_roundtrip():
    from edsl import Model
    from edsl.language_models.language_model import LanguageModel

    m = Model("test", prompt_plan=PromptPlan.user_prompt_only())
    d = m.to_dict()
    assert "prompt_plan" in d
    m2 = LanguageModel.from_dict(d)
    assert m2.prompt_plan == PromptPlan.user_prompt_only()


# 5. Backward compat — old models without prompt_plan

def test_model_without_prompt_plan():
    from edsl import Model

    m = Model("test")
    assert m.prompt_plan is None  # Falls back to default in InvigilatorBase


# 6. PromptList.reduce() handles empty lists

def test_prompt_list_reduce_empty():
    from edsl.invigilators.prompt_helpers import PromptList

    result = PromptList([]).reduce()
    assert result.text == ""


# 7. __eq__ and __repr__

def test_prompt_plan_eq():
    assert PromptPlan.default() == PromptPlan.default()
    assert PromptPlan.default() != PromptPlan.user_prompt_only()
    assert PromptPlan.default() != "not a prompt plan"


def test_prompt_plan_repr():
    pp = PromptPlan.default()
    r = repr(pp)
    assert "PromptPlan" in r
    assert "user_prompt_order" in r


# 8. End-to-end: user_prompt_only produces empty system prompt

def test_end_to_end_user_prompt_only():
    from edsl import QuestionFreeText, Survey, Agent, Model

    q = QuestionFreeText(question_name="q", question_text="Say hi")
    a = Agent(traits={"persona": "a chef"})
    m = Model("test", prompt_plan=PromptPlan.user_prompt_only())
    prompts = Survey([q]).by(a).by(m).prompts()
    system = prompts.select("system_prompt").to_list()[0]
    user = prompts.select("user_prompt").to_list()[0]
    assert system.strip() == ""
    assert "chef" in user
    assert "Say hi" in user
