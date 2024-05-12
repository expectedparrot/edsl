from typing import Optional, Callable
from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import FunctionDescriptor


class QuestionFunctional(QuestionBase):
    """A special type of question that is *not* answered by an LLM."""

    func: Callable = FunctionDescriptor()
    question_type = "functional"
    default_instructions = ""

    def __init__(
        self,
        question_name: str,
        func: Callable,
        question_text: Optional[str] = "Functional question",
    ):
        """Initialize the question."""
        self.question_name = question_name
        self.func = func
        self.question_text = question_text
        self.instructions = self.default_instructions

    def _validate_answer(self, answer: dict[str, str]):
        """Required by Question, but not used by QuestionFunctional."""
        raise NotImplementedError

    def answer_question_directly(self, scenario, agent_traits=None):
        """Return the answer to the question."""
        return {"answer": self.func(scenario, agent_traits), "comment": None}

    def _translate_answer_code_to_answer(self, answer, scenario):
        """Required by Question, but not used by QuestionFunctional."""
        return None

    def _simulate_answer(self, human_readable=True) -> dict[str, str]:
        """Required by Question, but not used by QuestionFunctional."""
        raise NotImplementedError

    @classmethod
    def example(cls):
        """Required by Question, but not used by QuestionFunctional."""
        silly_function = lambda scenario, agent_traits: scenario.get(
            "a", 1
        ) + scenario.get("b", 2)
        return cls(
            question_name="add_two_numbers",
            question_text="functional",
            func=silly_function,
        )
