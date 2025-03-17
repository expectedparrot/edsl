from __future__ import annotations
import copy
import itertools
from typing import Optional, List, Callable, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .question_base import QuestionBase
    from ..scenarios import ScenarioList

class QuestionBaseGenMixin:
    """Mixin for QuestionBase.
    
    This mostly has functions that are used to generate new questions from existing ones.
    
    """

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

        >>> from edsl.questions import QuestionMultipleChoice as Q
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

        >>> from edsl.questions import QuestionMultipleChoice as Q
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

        >>> from edsl.questions import QuestionFreeText
        >>> from edsl.scenarios import ScenarioList
        >>> q = QuestionFreeText(question_text = "What are your thoughts on: {{ subject}}?", question_name = "base_{{subject}}")
        >>> len(q.loop(ScenarioList.from_list("subject", ["Math", "Economics", "Chemistry"])))
        3
        """
        from edsl.questions.loop_processor import LoopProcessor

        lp = LoopProcessor(self)
        return lp.process_templates(scenario_list)

    class MaxTemplateNestingExceeded(Exception):
        """Raised when template rendering exceeds maximum allowed nesting level."""
        pass

    def render(self, replacement_dict: dict, return_dict: bool = False) -> Union["QuestionBase", dict]:
        """Render the question components as jinja2 templates with the replacement dictionary.
        Handles nested template variables by recursively rendering until all variables are resolved.
        
        Raises:
            MaxTemplateNestingExceeded: If template nesting exceeds MAX_NESTING levels
        
        >>> from edsl.questions import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "color", question_text = "What is your favorite {{ thing }}?")
        >>> q.render({"thing": "color"})
        Question('free_text', question_name = \"""color\""", question_text = \"""What is your favorite color?\""")

        >>> from edsl.questions import QuestionMultipleChoice
        >>> q = QuestionMultipleChoice(question_name = "color", question_text = "What is your favorite {{ thing }}?", question_options = ["red", "blue", "green"])
        >>> from edsl.scenarios import Scenario
        >>> q.render(Scenario({"thing": "color"})).data
        {'question_name': 'color', 'question_text': 'What is your favorite color?', 'question_options': ['red', 'blue', 'green']}

        >>> from edsl.questions import QuestionMultipleChoice
        >>> q = QuestionMultipleChoice(question_name = "color", question_text = "What is your favorite {{ thing }}?", question_options = ["red", "blue", "green"])
        >>> q.render({"thing": 1}).data
        {'question_name': 'color', 'question_text': 'What is your favorite 1?', 'question_options': ['red', 'blue', 'green']}


        >>> from edsl.questions import QuestionMultipleChoice
        >>> from edsl.scenarios import Scenario
        >>> q = QuestionMultipleChoice(question_name = "color", question_text = "What is your favorite {{ thing }}?", question_options = ["red", "blue", "green"])
        >>> q.render(Scenario({"thing": "color of {{ object }}", "object":"water"})).data
        {'question_name': 'color', 'question_text': 'What is your favorite color of water?', 'question_options': ['red', 'blue', 'green']}

        
        >>> from edsl.questions import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "infinite", question_text = "This has {{ a }}")
        >>> q.render({"a": "{{ b }}", "b": "{{ a }}"}) # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        edsl.questions.question_base_gen_mixin.QuestionBaseGenMixin.MaxTemplateNestingExceeded:...
        """
        from jinja2 import Environment, meta
        from edsl.scenarios import Scenario

        MAX_NESTING = 10  # Maximum allowed nesting levels
        
        strings_only_replacement_dict = {
            k: v for k, v in replacement_dict.items() if not isinstance(v, Scenario)
        }

        strings_only_replacement_dict['scenario'] = strings_only_replacement_dict

        def _has_unrendered_variables(template_str: str, env: Environment) -> bool:
            """Check if the template string has any unrendered variables."""
            if not isinstance(template_str, str):
                return False
            ast = env.parse(template_str)
            return bool(meta.find_undeclared_variables(ast))

        def render_string(value: str) -> str:
            if value is None or not isinstance(value, str):
                return value
            
            try:
                env = Environment()
                result = value
                nesting_count = 0
                
                while _has_unrendered_variables(result, env):
                    if nesting_count >= MAX_NESTING:
                        raise self.MaxTemplateNestingExceeded(
                            f"Template rendering exceeded {MAX_NESTING} levels of nesting. "
                            f"Current value: {result}"
                        )
                    
                    template = env.from_string(result)
                    new_result = template.render(strings_only_replacement_dict)
                    if new_result == result:  # Break if no changes made
                        break
                    result = new_result
                    nesting_count += 1
                
                return result
            except self.MaxTemplateNestingExceeded:
                raise
            except Exception:
                import warnings
                warnings.warn("Failed to render string: " + value)
                return value
        if return_dict:
            return self._apply_function_dict(render_string)
        else:
            return self.apply_function(render_string)
      
    def apply_function(
        self, func: Callable, exclude_components: Optional[List[str]] = None
    ) -> QuestionBase:
        from .question_base import QuestionBase
        d = self._apply_function_dict(func, exclude_components)
        return QuestionBase.from_dict(d)

    def _apply_function_dict(
        self, func: Callable, exclude_components: Optional[List[str]] = None
    ) -> dict:
        """Apply a function to the question parts, excluding certain components.

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
        return d


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
