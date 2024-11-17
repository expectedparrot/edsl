from __future__ import annotations
import copy
import itertools
from typing import Optional, List, Callable, Type
from typing import TypeVar


class QuestionBaseGenMixin:
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

        >>> from edsl import QuestionMultipleChoice as Q
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

    def loop(self, scenario_list: ScenarioList) -> List[QuestionBase]:
        """Return a list of questions with the question name modified for each scenario.

        :param scenario_list: The list of scenarios to loop through.

        >>> from edsl import QuestionFreeText
        >>> from edsl import ScenarioList
        >>> q = QuestionFreeText(question_text = "What are your thoughts on: {{ subject}}?", question_name = "base_{{subject}}")
        >>> len(q.loop(ScenarioList.from_list("subject", ["Math", "Economics", "Chemistry"])))
        3

        """
        from jinja2 import Environment
        from edsl.questions.QuestionBase import QuestionBase

        starting_name = self.question_name
        questions = []
        for index, scenario in enumerate(scenario_list):
            env = Environment()
            new_data = self.to_dict().copy()
            for key, value in [(k, v) for k, v in new_data.items() if v is not None]:
                if (
                    isinstance(value, str) or isinstance(value, int)
                ) and key != "question_options":
                    new_data[key] = env.from_string(value).render(scenario)
                elif isinstance(value, list):
                    new_data[key] = [
                        env.from_string(v).render(scenario) if isinstance(v, str) else v
                        for v in value
                    ]
                elif isinstance(value, dict):
                    new_data[key] = {
                        (
                            env.from_string(k).render(scenario)
                            if isinstance(k, str)
                            else k
                        ): (
                            env.from_string(v).render(scenario)
                            if isinstance(v, str)
                            else v
                        )
                        for k, v in value.items()
                    }
                elif key == "question_options" and isinstance(value, str):
                    new_data[key] = value
                else:
                    raise ValueError(
                        f"Unexpected value type: {type(value)} for key '{key}'"
                    )

            if new_data["question_name"] == starting_name:
                new_data["question_name"] = new_data["question_name"] + f"_{index}"

            questions.append(QuestionBase.from_dict(new_data))
        return questions

    def render(self, replacement_dict: dict) -> "QuestionBase":
        """Render the question components as jinja2 templates with the replacement dictionary."""
        from jinja2 import Environment
        from edsl import Scenario

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

    def apply_function(self, func: Callable, exclude_components=None) -> QuestionBase:
        """Apply a function to the question parts

        >>> from edsl.questions import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "color", question_text = "What is your favorite color?")
        >>> shouting = lambda x: x.upper()
        >>> q.apply_function(shouting)
        Question('free_text', question_name = \"""color\""", question_text = \"""WHAT IS YOUR FAVORITE COLOR?\""")

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
