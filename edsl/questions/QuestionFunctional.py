from typing import Optional, Callable
from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import FunctionDescriptor
import inspect
from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Guards import (
    safe_builtins,
    full_write_guard,
    guarded_iter_unpack_sequence,
)


class QuestionFunctionRunningException(Exception):
    """Exception for errors during function execution in a restricted environment."""


class QuestionFunctionActivatedException(Exception):
    """Exception for function not activated yet."""


class QuestionFunctionAForbiddenAttributeException(Exception):
    """Exception for errors during function execution when forbidden key is used."""


def guarded_iter(obj, allowed_types=(list, tuple, set, dict, range)):
    """Ensures iteration is only performed on safe, allowable types."""
    if not isinstance(obj, allowed_types):
        raise TypeError(f"Iteration over {type(obj).__name__} not allowed.")
    return iter(obj)


def default_guarded_getitem(ob, key):
    sensitive_python_keys = [
        "__dict__",
        "__class__",
        "__module__",
        "__bases__",
        "__mro__",
        "__subclasses__",
        "__func__",
        "__self__",
        "__closure__",
        "__code__",
        "__globals__",
        "__call__",
        "__getattr__",
        "__getattribute__",
        "__delattr__",
        "__setattr__",
    ]
    if key in sensitive_python_keys:
        raise QuestionFunctionAForbiddenAttributeException(
            f"Access denied for attribute: {key}"
        )

    return ob[key]


from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import FunctionDescriptor


class QuestionFunctional(QuestionBase):
    """A special type of question that is *not* answered by an LLM."""

    question_type = "functional"
    default_instructions = ""
    activated = False
    function_source_code = ""
    function_name = ""

    def __init__(
        self,
        question_name: str,
        func: Optional[Callable] = None,
        question_text: Optional[str] = "Functional question",
        requires_loop: Optional[bool] = False,
        function_source_code: Optional[str] = None,
        function_name: Optional[str] = None,
    ):
        super().__init__()
        if func:
            self.function_source_code = inspect.getsource(func)
            self.function_name = func.__name__
        else:
            self.function_source_code = function_source_code
            self.function_name = function_name

        self.requires_loop = requires_loop

        self.func = self.create_restricted_function()

        self.question_name = question_name
        self.question_text = question_text
        self.instructions = self.default_instructions

    def create_restricted_function(self):
        """Activate the function using RestrictedPython with basic restrictions."""
        safe_env = safe_globals.copy()
        safe_env["__builtins__"] = {**safe_builtins}
        safe_env["_getitem_"] = default_guarded_getitem

        if self.requires_loop:
            safe_env["_getiter_"] = guarded_iter
            safe_env["_iter_unpack_sequence_"] = guarded_iter_unpack_sequence

        byte_code = compile_restricted(self.function_source_code, "<string>", "exec")
        loc = {}
        try:
            exec(byte_code, safe_env, loc)
            func = loc[self.function_name]
        except Exception as e:
            print("Creating restricted funtion error", e)
            raise QuestionFunctionActivatedException(
                "Creating restricted funtion failed"
            )

        return func

    def activate(self):
        self.activated = True

    def activate_loop(self):
        """Activate the function with loop logic using RestrictedPython."""
        safe_env = safe_globals.copy()
        safe_env["__builtins__"] = {**safe_builtins}
        safe_env["_getiter_"] = guarded_iter
        safe_env["_iter_unpack_sequence_"] = guarded_iter_unpack_sequence
        byte_code = compile_restricted(self.function_source_code, "<string>", "exec")
        loc = {}

        self.requires_loop = True
        self.activated = True

        try:
            exec(byte_code, safe_env, loc)
            self.func = loc[self.function_name]
        except Exception as e:
            print("Loop activation error:", e)
            raise QuestionFunctionRunningException("Activation with loops failed.")

    def answer_question_directly(self, scenario, agent_traits=None):
        """Return the answer to the question, ensuring the function is activated."""
        if not self.activated:
            raise QuestionFunctionActivatedException(
                "Function not activated. Please activate it first."
            )
        try:
            return {"answer": self.func(scenario, agent_traits), "comment": None}
        except Exception as e:
            print("Function execution error:", e)
            raise QuestionFunctionRunningException("Error during function execution.")

    def _translate_answer_code_to_answer(self, answer, scenario):
        """Required by Question, but not used by QuestionFunctional."""
        return None

    def _simulate_answer(self, human_readable=True) -> dict[str, str]:
        """Required by Question, but not used by QuestionFunctional."""
        raise NotImplementedError

    def _validate_answer(self, answer: dict[str, str]):
        """Required by Question, but not used by QuestionFunctional."""
        raise NotImplementedError

    def to_dict(self):
        return {
            "question_name": self.question_name,
            "function_source_code": self.function_source_code,
            "question_type": "functional",
            "requires_loop": self.requires_loop,
            "function_name": self.function_name,
        }


def calculate_sum_and_multiply(scenario, agent_traits):
    numbers = scenario.get("numbers", [])
    multiplier = agent_traits.get("multiplier", 1) if agent_traits else 1
    sum = 0
    for num in numbers:
        sum = sum + num
    return sum * multiplier


if __name__ == "__main__":
    from edsl import Scenario, Agent

    # Create an instance of QuestionFunctional with the new function
    question = QuestionFunctional(
        question_name="sum_and_multiply",
        func=calculate_sum_and_multiply,
        question_text="Calculate the sum of the list and multiply it by the agent trait multiplier.",
    )

    # Activate and test the function
    question.activate_loop()
    scenario = Scenario({"numbers": [1, 2, 3, 4, 5]})
    agent = Agent(traits={"multiplier": 10})
    results = question.by(scenario).by(agent).run()
    print(results)

    dict_q = question.to_dict()
    print("#####")
    new_q = QuestionFunctional.from_dict(dict_q)

    new_q.activate()
    results = new_q.by(scenario).by(agent).run()
    print(results)
