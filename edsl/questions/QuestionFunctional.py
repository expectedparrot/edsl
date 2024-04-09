"""A special type of question that is *not* answered by an LLM.

    - Instead, it is "answered" by a function that is passed in, `func`.
    - Useful for questions that require some kind of computation first
      or are the result of a multi-step process.
    See `compose_questions` in `compose_functions.py` for an example of how this is used.

    Notes
    - 'func' is a function that takes in a scenario and agent traits and returns an answer.
    - QuestionFunctional is not meant to be instantiated directly by end-users, but rather
      it is meant to be subclassed by us to create new function types.
    - It is probably *not* safe to allow end-users to have the ability to pass functional-derived questions.
      They could monkey-patch the function to do something malicious, e.g., to replace our function logic
      with "os.system('rm -rf /')".
    - One possible solution is to have interfaces they can pass via the API, like so:
      QuestionDropdown(question_name = "dropdown", question_options = ["a", "b", "c"]...)
      which we then translate to the real QuestionFunctional `under the hood.`

    To see how it's used, see `tests/test_QuestionFunctional_construction_from_function`.


"""
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
