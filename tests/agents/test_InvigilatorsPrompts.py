import pytest
from edsl.agents import Agent

from edsl.prompts import Prompt

# from edsl.prompts.registry import get_classes
from edsl.exceptions.questions import QuestionScenarioRenderError

# from edsl.prompts.registry import get_classes
from edsl.surveys import Survey

from edsl.invigilators import InvigilatorAI


class MockModel:
    model = "gpt-4-1106-preview"


class MockQuestion:
    question_type = "free_text"
    question_text = "How are you feeling?"
    question_name = "q0"
    name = "q0"
    data = {
        "question_name": "feelings",
        "question_text": "How are you feeling?",
        "question_type": "feelings_question",
    }

    def get_instructions(self, model):
        return Prompt(
            text="You are a robot being asked the following question: How are you feeling? Return a valid JSON formatted like this: {'answer': '<put free text answer here>'}"
        )


# Assuming get_classes and InvigilatorAI are defined elsewhere in your codebase
# from your_module import get_classes, InvigilatorAI


@pytest.fixture
def mock_model():
    return MockModel()


@pytest.fixture
def mock_question():
    return MockQuestion()


def test_invigilator_ai_no_trait_template(mock_model, mock_question):
    # applicable_prompts = get_classes(
    #     component_type="question_instructions",
    #     question_type=mock_question.question_type,
    #     model=mock_model.model,
    # )

    a = Agent(
        instruction="You are a happy-go lucky agent.",
        traits={"feeling": "happy", "age": "Young at heart"},
        codebook={"feeling": "Feelings right now", "age": "Age in years"},
        traits_presentation_template="",
    )

    i = InvigilatorAI(
        agent=a,
        question=mock_question,
        scenario={},
        model=mock_model,
        survey=Survey.example(),
        memory_plan=None,
        current_answers=None,
    )

    assert i.get_prompts()["system_prompt"].text == "You are a happy-go lucky agent."


def test_invigilator_ai_with_trait_template(mock_model, mock_question):
    a = Agent(
        instruction="You are a happy-go lucky agent.",
        traits={"feeling": "happy", "age": "Young at heart"},
        codebook={"feeling": "Feelings right now", "age": "Age in years"},
        traits_presentation_template="You are feeling {{ feeling }}.",
    )

    i = InvigilatorAI(
        agent=a,
        question=mock_question,
        scenario={},
        survey=Survey.example(),
        model=mock_model,
        memory_plan=None,
        current_answers=None,
    )

    assert (
        i.get_prompts()["system_prompt"].text
        == "You are a happy-go lucky agent.You are feeling happy."
    )


def test_invigilator_ai_with_incomplete_trait_template(mock_model, mock_question):
    a = Agent(
        instruction="You are a happy-go lucky agent.",
        traits={"feeling": "happy", "age": "Young at heart"},
        codebook={"feeling": "Feelings right now", "age": "Age in years"},
        traits_presentation_template="You are feeling {{ feeling }}. You eat lots of {{ food }}.",
    )

    i = InvigilatorAI(
        agent=a,
        question=mock_question,
        scenario={},
        model=mock_model,
        survey=Survey.example(),
        memory_plan=None,
        current_answers=None,
    )

    # Assuming QuestionScenarioRenderError is a specific exception you expect
    with pytest.raises(QuestionScenarioRenderError):
        i.get_prompts()["system_prompt"]


# Add more test functions as needed
