import pytest

from edsl.agents import Agent
from edsl.questions import QuestionMultipleChoice, QuestionList, QuestionFreeText
from edsl.scenarios.Scenario import Scenario
from edsl.surveys.Survey import Survey
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice as q


def test_option_expansion_from_current_answers_list_not_present_yet():
    # from edsl import QuestionMultipleChoice, QuestionList, Survey
    from edsl.invigilators.invigilators import InvigilatorBase

    q0 = QuestionList(
        question_text="What are some age levels?",
        question_name="age_levels",
    )
    q1 = QuestionMultipleChoice(
        question_text="Here is a question",
        question_name="example_question",
        question_options=["{{age_levels.answer[0]}}", "{{age_levels.answer[1]}}"],
    )
    i = InvigilatorBase.example(question=q1, survey=Survey([q0, q1]))
    i.current_answers = {}
    assert "example_question" in i.prompt_constructor.prior_answers_dict()
    # breakpoint()
    _ = i.prompt_constructor.question_instructions_prompt


def test_option_expansion_from_current_answers_list():
    from edsl.invigilators.invigilators import InvigilatorBase

    q0 = QuestionList(
        question_text="What are some age levels?",
        question_name="age_levels",
    )
    q1 = QuestionMultipleChoice(
        question_text="Here is a question",
        question_name="example_question",
        question_options=["{{age_levels.answer[0]}}", "{{age_levels.answer[1]}}"],
    )
    i = InvigilatorBase.example(question=q1, survey=Survey([q0, q1]))
    i.current_answers = {"age_levels": ["10-20", "20-30"]}
    assert "example_question" in i.prompt_constructor.prior_answers_dict()
    assert "10-20" in i.prompt_constructor.question_instructions_prompt


def test_option_expansion_from_current_answers():
    from edsl.invigilators.invigilators import InvigilatorBase

    q0 = QuestionList(
        question_text="What are some age levels?",
        question_name="age_levels",
    )
    q1 = QuestionMultipleChoice(
        question_text="Here is a question",
        question_name="example_question",
        question_options="{{ age_levels.answer }}",
    )
    i = InvigilatorBase.example(question=q1, survey=Survey([q0, q1]))
    i.current_answers = {"age_levels": ["10-20", "20-30"]}
    assert "example_question" in i.prompt_constructor.prior_answers_dict()
    assert "10-20" in i.prompt_constructor.question_instructions_prompt


def test_option_expansion_from_scenario():

    from edsl.invigilators.invigilators import InvigilatorBase

    q = QuestionMultipleChoice(
        question_text="Here is a question",
        question_name="example_question",
        question_options="{{ scenario.age_levels }}",
    )

    i = InvigilatorBase.example(question=q)
    i.scenario = Scenario({"age_levels": ["10-20", "20-30"]})
    assert "10-20" in i.prompt_constructor.question_instructions_prompt


def test_system_prompt_traits_passed():
    agent = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
    i = agent._create_invigilator(question=q.example(), survey=q.example().to_survey())
    system_prompt = i.prompt_constructor.get_prompts()["system_prompt"]
    assert True == all([key in system_prompt for key in agent.traits.keys()])


def test_user_prompt_question_text_passed():
    agent = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})

    i = agent._create_invigilator(question=q.example(), survey=Survey([q.example()]))
    user_prompt = i.prompt_constructor.get_prompts()["user_prompt"]
    assert q.example().question_text in user_prompt


def test_scenario_render_in_user_prompt():

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
    user_prompt = i.prompt_constructor.get_prompts()["user_prompt"]
    assert "Peter" in user_prompt
