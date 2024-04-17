"""This module provides a factory class for creating question objects."""
import textwrap
from typing import Union

from edsl.exceptions import QuestionSerializationError
from edsl.exceptions import QuestionCreationValidationError
from edsl.questions.QuestionBase import RegisterQuestionsMeta


class Meta(type):
    """Metaclass for QuestionBase that provides a __repr__ method that lists all available questions."""

    def __repr__(cls):
        """Return a string that lists all available questions."""

        s = textwrap.dedent(
            """
        You can use the Question class to create objects by name. 
        For example, to create a multiple choice question, you can do:

        >>> from edsl import Question
        >>> q = Question('multiple_choice', question_text='What is your favorite color?', question_name='color')
        
        Question Types:\n"""
        )
        for question_type, question_class in cls.available(
            show_class_names=True
        ).items():
            line_info = (
                f"{question_type} ({question_class.__name__}): {question_class.__doc__}"
            )
            s += line_info + "\n"
        return s


class Question(metaclass=Meta):
    """Factory class for creating question objects."""

    def __new__(cls, question_type, *args, **kwargs):
        """Create a new question object."""
        get_question_classes = RegisterQuestionsMeta.question_types_to_classes()

        subclass = get_question_classes.get(question_type, None)
        if subclass is None:
            raise ValueError(
                f"No question registered with question_type {question_type}"
            )

        # Create an instance of the selected subclass
        instance = object.__new__(subclass)
        instance.__init__(*args, **kwargs)
        return instance

    @classmethod
    def pull(cls, id: int) -> "QuestionBase":
        """Pull the object from coop."""
        from edsl.coop import Coop

        c = Coop()
        return c.get("question", id)

    @classmethod
    def available(cls, show_class_names: bool = False) -> Union[list, dict]:
        """Return a list of available question types.

        :param show_class_names: If True, return a dictionary of question types to class names. If False, return a set of question types.

        Example usage:

        >>> from edsl import Question
        >>> Question.available()
        ['budget', 'checkbox', 'extract', 'free_text', 'functional', 'likert_five', 'linear_scale', 'list', 'multiple_choice', 'numerical', 'rank', 'top_k', 'yes_no']
        """
        if show_class_names:
            return RegisterQuestionsMeta.question_types_to_classes()
        else:
            return sorted(set(RegisterQuestionsMeta.question_types_to_classes().keys()))


def get_question_class(question_type):
    """Return the class for the given question type."""
    q2c = RegisterQuestionsMeta.question_types_to_classes()
    if question_type not in q2c:
        raise ValueError(
            f"The question type, {question_type}, is not recognized. Recognied types are: {q2c.keys()}"
        )
    return q2c.get(question_type)


question_purpose = {
    "multiple_choice": "When options are known and limited",
    "free_text": "When options are unknown or unlimited",
    "checkbox": "When multiple options can be selected",
    "numerical": "When the answer is a single numerical value e.g., a float",
    "linear_scale": "When options are text, but can be ordered, e.g., daily, weekly, monthly, etc.",
    "yes_no": "When the question can be fully answered with either a yes or a no",
    "list": "When the answer should be a list of items",
    "rank": "When the answer should be a ranked list of items",
    "budget": "When the answer should be an amount allocated among a set of options",
    "top_k": "When the answer should be a list of the top k items",
    "likert_five": "When the answer should be a value on the Likert scale from 1 to 5",
    "extract": "When the answer should be information extracted or extrapolated from a text in a given format",
}


if __name__ == "__main__":
    print(Question.available())

    # q = Question("free_text", question_text="How are you doing?", question_name="test")
    # results = q.run()

    q = Question.pull(id=76)
