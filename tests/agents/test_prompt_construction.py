
from edsl.agents import Agent
from edsl.questions import QuestionMultipleChoice, QuestionList, QuestionFreeText
from edsl.scenarios import Scenario
from edsl.surveys import Survey
from edsl.questions import QuestionMultipleChoice as q


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
    assert "example_question" in i.prompt_constructor.prior_answers_dict
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
    assert "example_question" in i.prompt_constructor.prior_answers_dict
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
    assert "example_question" in i.prompt_constructor.prior_answers_dict
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


# Invigilator prompt construction tests moved to test_AgentInvigilator.py
