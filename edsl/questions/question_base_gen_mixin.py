from __future__ import annotations
import copy
import itertools
from typing import Optional, List, Callable, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from edsl.questions.QuestionBase import QuestionBase
    from edsl.scenarios.ScenarioList import ScenarioList


class QuestionBaseGenMixin:
    """Mixin for QuestionBase."""

    def copy(self) -> QuestionBase:
        """Return a deep copy of the question.

        >>> from edsl.questions import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "color", question_text = "What is your favorite color?")
        >>> q2 = q.copy()
        >>> q2.question_name
        'color'

        """
        return copy.deepcopy(self)

    def option_permutations(self) -> list[QuestionBase]:
        """Return a list of questions with all possible permutations of the options.

        >>> from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice as Q
        >>> len(Q.example().option_permutations())
        24
        """

        if not hasattr(self, "question_options"):
            return [self]

        questions = []
        for index, permutation in enumerate(
            itertools.permutations(self.question_options)
        ):
            question = copy.deepcopy(self)
            question.question_options = list(permutation)
            question.question_name = f"{self.question_name}_{index}"
            questions.append(question)
        return questions

    def draw(self) -> "QuestionBase":
        """Return a new question with a randomly selected permutation of the options.

        If the question has no options, returns a copy of the original question.

        >>> from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice as Q
        >>> q = Q.example()
        >>> drawn = q.draw()
        >>> len(drawn.question_options) == len(q.question_options)
        True
        >>> q is drawn
        False
        """

        if not hasattr(self, "question_options"):
            return copy.deepcopy(self)

        import random

        question = copy.deepcopy(self)
        question.question_options = list(
            random.sample(self.question_options, len(self.question_options))
        )
        return question

    def loop(self, scenario_list: ScenarioList) -> List[QuestionBase]:
        """Return a list of questions with the question name modified for each scenario.

        :param scenario_list: The list of scenarios to loop through.

        >>> from edsl.questions.QuestionFreeText import QuestionFreeText
        >>> from edsl.scenarios.ScenarioList import ScenarioList
        >>> q = QuestionFreeText(question_text = "What are your thoughts on: {{ subject}}?", question_name = "base_{{subject}}")
        >>> len(q.loop(ScenarioList.from_list("subject", ["Math", "Economics", "Chemistry"])))
        3
        """
        from edsl.questions.loop_processor import LoopProcessor

        lp = LoopProcessor(self)
        return lp.process_templates(scenario_list)

    def render(self, replacement_dict: dict) -> "QuestionBase":
        """Render the question components as jinja2 templates with the replacement dictionary.

        :param replacement_dict: The dictionary of values to replace in the question components.

        >>> from edsl.questions.QuestionFreeText import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "color", question_text = "What is your favorite {{ thing }}?")
        >>> q.render({"thing": "color"})
        Question('free_text', question_name = \"""color\""", question_text = \"""What is your favorite color?\""")

        """
        from jinja2 import Environment
        from edsl.scenarios.Scenario import Scenario

        strings_only_replacement_dict = {
            k: v for k, v in replacement_dict.items() if not isinstance(v, Scenario)
        }

        def render_string(value: str) -> str:
            if value is None or not isinstance(value, str):
                return value
            else:
                try:
                    return (
                        Environment()
                        .from_string(value)
                        .render(strings_only_replacement_dict)
                    )
                except Exception as e:
                    import warnings

                    warnings.warn("Failed to render string: " + value)
                    # breakpoint()
                    return value

        return self.apply_function(render_string)

    def apply_function(
        self, func: Callable, exclude_components: List[str] = None
    ) -> QuestionBase:
        """Apply a function to the question parts

        :param func: The function to apply to the question parts.
        :param exclude_components: The components to exclude from the function application.

        >>> from edsl.questions import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "color", question_text = "What is your favorite color?")
        >>> shouting = lambda x: x.upper()
        >>> q.apply_function(shouting)
        Question('free_text', question_name = \"""color\""", question_text = \"""WHAT IS YOUR FAVORITE COLOR?\""")

        >>> q.apply_function(shouting, exclude_components = ["question_type"])
        Question('free_text', question_name = \"""COLOR\""", question_text = \"""WHAT IS YOUR FAVORITE COLOR?\""")

        """
        from edsl.questions.QuestionBase import QuestionBase

        if exclude_components is None:
            exclude_components = ["question_name", "question_type"]

        d = copy.deepcopy(self.to_dict(add_edsl_version=False))
        for key, value in d.items():
            if key in exclude_components:
                continue
            if isinstance(value, dict):
                for k, v in value.items():
                    value[k] = func(v)
                d[key] = value
                continue
            if isinstance(value, list):
                value = [func(v) for v in value]
                d[key] = value
                continue
            d[key] = func(value)
        return QuestionBase.from_dict(d)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
