import pytest

from edsl import Agent
from edsl.questions import QuestionMultipleChoice as q


def test_system_prompt_traits_passed():
    agent = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
    i = agent._create_invigilator(question=q.example(), survey=q.example().to_survey())
    system_prompt = i.prompt_constructor.construct_system_prompt()
    assert True == all([key in system_prompt for key in agent.traits.keys()])


def test_user_prompt_question_text_passed():
    agent = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
    from edsl.questions import QuestionMultipleChoice as q
    from edsl import Survey

    i = agent._create_invigilator(question=q.example(), survey=Survey([q.example()]))
    user_prompt = i.prompt_constructor.construct_user_prompt()
    assert q.example().question_text in user_prompt


def test_scenario_render_in_user_prompt():
    from edsl.questions import QuestionFreeText
    from edsl.scenarios import Scenario
    from edsl import Agent

    agent = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
    q = QuestionFreeText(
        question_text="How are you today {{first_name}}?", question_name="name"
    )
    q_no_nesting = QuestionFreeText(
        question_text="How are you today?", question_name="name"
    )
    s = Scenario({"first_name": "Peter"})
    i = agent._create_invigilator(
        question=q, scenario=s, survey=q_no_nesting.to_survey()
    )
    user_prompt = i.prompt_constructor.construct_user_prompt()
    assert "Peter" in user_prompt
