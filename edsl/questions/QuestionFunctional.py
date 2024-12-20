from typing import Optional, Callable
import inspect

from edsl.questions.QuestionBase import QuestionBase

from edsl.utilities.restricted_python import create_restricted_function
from edsl.utilities.decorators import add_edsl_version, remove_edsl_version


class QuestionFunctional(QuestionBase):
    """A special type of question that is *not* answered by an LLM.

    >>> from edsl import Scenario, Agent

    # Create an instance of QuestionFunctional with the new function
    >>> question = QuestionFunctional.example()

    # Activate and test the function
    >>> question.activate()
    >>> scenario = Scenario({"numbers": [1, 2, 3, 4, 5]})
    >>> agent = Agent(traits={"multiplier": 10})
    >>> results = question.by(scenario).by(agent).run(disable_remote_cache = True, disable_remote_inference = True)
    >>> results.select("answer.*").to_list()[0] == 150
    True

    # Serialize the question to a dictionary

    >>> from edsl.questions.QuestionBase import QuestionBase
    >>> new_question = QuestionBase.from_dict(question.to_dict())
    >>> results = new_question.by(scenario).by(agent).run(disable_remote_cache = True, disable_remote_inference = True)
    >>> results.select("answer.*").to_list()[0] == 150
    True

    """

    question_type = "functional"
    default_instructions = ""
    activated = True
    function_source_code = ""
    function_name = ""

    _response_model = None
    response_validator_class = None

    def __init__(
        self,
        question_name: str,
        func: Optional[Callable] = None,
        question_text: Optional[str] = "Functional question",
        requires_loop: Optional[bool] = False,
        function_source_code: Optional[str] = None,
        function_name: Optional[str] = None,
        unsafe: Optional[bool] = False,
    ):
        super().__init__()
        if func:
            self.function_source_code = inspect.getsource(func)
            self.function_name = func.__name__
        else:
            self.function_source_code = function_source_code
            self.function_name = function_name

        self.requires_loop = requires_loop

        if unsafe:
            self.func = func
        else:
            self.func = create_restricted_function(
                self.function_name, self.function_source_code
            )

        self.question_name = question_name
        self.question_text = question_text
        self.instructions = self.default_instructions

    def activate(self):
        self.activated = True

    def activate_loop(self):
        """Activate the function with loop logic using RestrictedPython."""
        self.func = create_restricted_function(
            self.function_name, self.function_source_code, loop_activated=True
        )

    def answer_question_directly(self, scenario, agent_traits=None):
        """Return the answer to the question, ensuring the function is activated."""
        if not self.activated:
            raise Exception("Function not activated. Please activate it first.")
        try:
            return {"answer": self.func(scenario, agent_traits), "comment": None}
        except Exception as e:
            print("Function execution error:", e)
            raise Exception("Error during function execution.")

    def _translate_answer_code_to_answer(self, answer, scenario):
        """Required by Question, but not used by QuestionFunctional."""
        return None

    def _simulate_answer(self, human_readable=True) -> dict[str, str]:
        """Required by Question, but not used by QuestionFunctional."""
        raise NotImplementedError

    def _validate_answer(self, answer: dict[str, str]):
        """Required by Question, but not used by QuestionFunctional."""
        raise NotImplementedError

    @property
    def question_html_content(self) -> str:
        return "NA for QuestionFunctional"

    # @add_edsl_version
    def to_dict(self, add_edsl_version=True):
        d = {
            "question_name": self.question_name,
            "function_source_code": self.function_source_code,
            "question_type": "functional",
            "requires_loop": self.requires_loop,
            "function_name": self.function_name,
        }
        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = self.__class__.__name__

        return d

    @classmethod
    def example(cls):
        return cls(
            question_name="sum_and_multiply",
            func=calculate_sum_and_multiply,
            question_text="Calculate the sum of the list and multiply it by the agent trait multiplier.",
            requires_loop=True,
        )


def calculate_sum_and_multiply(scenario, agent_traits):
    numbers = scenario.get("numbers", [])
    multiplier = agent_traits.get("multiplier", 1) if agent_traits else 1
    sum = 0
    for num in numbers:
        sum = sum + num
    return sum * multiplier


def main():
    from edsl import Scenario, Agent
    from edsl.questions.QuestionFunctional import QuestionFunctional

    # Create an instance of QuestionFunctional with the new function
    question = QuestionFunctional.example()

    # Activate and test the function
    question.activate()
    scenario = Scenario({"numbers": [1, 2, 3, 4, 5]})
    agent = Agent(traits={"multiplier": 10})
    results = question.by(scenario).by(agent).run()
    assert results.select("answer.*").to_list()[0] == 150


if __name__ == "__main__":
    # main()
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
