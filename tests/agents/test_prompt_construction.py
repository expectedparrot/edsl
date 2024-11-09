import pytest

from edsl import Agent
from edsl.questions import QuestionMultipleChoice as q


def test_option_expansion_from_current_answers():
    from edsl import QuestionMultipleChoice, QuestionList, Survey
    from edsl.agents.InvigilatorBase import InvigilatorBase

    q0 = QuestionList(
        question_text="What are some age levels?",
        question_name="age_levels",
    )
    q1 = QuestionMultipleChoice(
        question_text="Here is a question",
        question_name="example_question",
        question_options="{{ age_levels }}",
    )
    i = InvigilatorBase.example(question=q1, survey=Survey([q0, q1]))
    i.current_answers = {"age_levels": ["10-20", "20-30"]}
    assert "example_question" in i.prompt_constructor.prior_answers_dict()
    assert "10-20" in i.prompt_constructor.question_instructions_prompt


def test_option_expansion_from_scenario():
    from edsl import QuestionMultipleChoice, Scenario

    q = QuestionMultipleChoice(
        question_text="Here is a question",
        question_name="example_question",
        question_options="{{ age_levels }}",
    )
    from edsl.agents.InvigilatorBase import InvigilatorBase

    i = InvigilatorBase.example(question=q)
    i.scenario = Scenario({"age_levels": ["10-20", "20-30"]})
    assert "10-20" in i.prompt_constructor.question_instructions_prompt
    # breakpoint()


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
