from __future__ import annotations
import copy
import itertools
from typing import Optional, List, Callable, TYPE_CHECKING, Union
from jinja2 import Environment, meta

if TYPE_CHECKING:
    from .question_base import QuestionBase
    from ..scenarios import ScenarioList


class TemplateRenderer:
    """Helper class for rendering Jinja2 templates with nested variable support.
    
    This class handles the rendering of template strings, supporting nested templates
    up to a maximum nesting level to prevent infinite recursion.
    """
    
    def __init__(self, max_nesting: int = 10, jinja_env: Optional[Environment] = None):
        """Initialize the template renderer.
        
        Args:
            max_nesting: Maximum allowed nesting levels for template rendering
            jinja_env: Optional Jinja2 Environment to use for rendering
        """
        self.max_nesting = max_nesting
        self.jinja_env = jinja_env or Environment()
    
    def has_unrendered_variables(self, template_str: str) -> bool:
        """Check if the template string has any unrendered variables.
        
        Args:
            template_str: The template string to check
            
        Returns:
            True if there are unrendered variables, False otherwise
        """
        if not isinstance(template_str, str):
            return False
        ast = self.jinja_env.parse(template_str)
        return bool(meta.find_undeclared_variables(ast))
    
    def render_string(
        self,
        value: str,
        replacement_dict: dict,
        exception_class: type = Exception
    ) -> str:
        """Render a template string with the replacement dictionary.
        
        Handles nested template variables by recursively rendering until all
        variables are resolved or max nesting is reached.
        
        Args:
            value: The template string to render
            replacement_dict: Dictionary of values to substitute
            exception_class: Exception class to raise on max nesting exceeded
            
        Returns:
            The rendered string
            
        Raises:
            exception_class: If template nesting exceeds max_nesting levels
        """
        if value is None or not isinstance(value, str):
            return value
        
        try:
            result = value
            nesting_count = 0
            
            while self.has_unrendered_variables(result):
                if nesting_count >= self.max_nesting:
                    raise exception_class(
                        f"Template rendering exceeded {self.max_nesting} levels of nesting. "
                        f"Current value: {result}"
                    )
                
                template = self.jinja_env.from_string(result)
                new_result = template.render(replacement_dict)
                if new_result == result:  # Break if no changes made
                    break
                result = new_result
                nesting_count += 1
            
            return result
        except exception_class:
            raise
        except Exception:
            import warnings
            warnings.warn("Failed to render string: " + value)
            return value


class QuestionBaseGenMixin:
    """Mixin for QuestionBase.

    This mostly has functions that are used to generate new questions from existing ones.

    """
    
    # Maximum allowed nesting levels for template rendering
    MAX_NESTING = 10

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

    def draw(
        self,
        random_seed: Optional[int] = None,
        random_instance: Optional["random.Random"] = None
    ) -> "QuestionBase":
        """Return a new question with a randomly selected permutation of the options.

        If the question has no options, returns a copy of the original question.
        
        Args:
            random_seed: Optional seed for reproducible randomization
            random_instance: Optional random.Random instance for randomization.
                If both random_seed and random_instance are provided, random_instance takes precedence.

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

        # Use provided random instance or create one with seed
        if random_instance is not None:
            rng = random_instance
        elif random_seed is not None:
            rng = random.Random(random_seed)
        else:
            rng = random

        question = copy.deepcopy(self)
        question.question_options = list(
            rng.sample(self.question_options, len(self.question_options))
        )
        return question

    def loop(
        self,
        scenario_list: ScenarioList,
        loop_processor: Optional[Callable] = None
    ) -> List[QuestionBase]:
        """Return a list of questions with the question name modified for each scenario.

        Args:
            scenario_list: The list of scenarios to loop through.
            loop_processor: Optional callable that takes a question and returns a processor
                with a process_templates method. If None, uses LoopProcessor.

        >>> from edsl.questions import QuestionFreeText
        >>> from edsl.scenarios import ScenarioList
        >>> q = QuestionFreeText(question_text = "What are your thoughts on: {{ subject}}?", question_name = "base_{{subject}}")
        >>> len(q.loop(ScenarioList.from_list("subject", ["Math", "Economics", "Chemistry"])))
        3
        """
        if loop_processor is None:
            from edsl.questions.loop_processor import LoopProcessor
            loop_processor = LoopProcessor

        lp = loop_processor(self)
        return lp.process_templates(scenario_list)

    class MaxTemplateNestingExceeded(Exception):
        """Raised when template rendering exceeds maximum allowed nesting level."""

        pass

    def render(
        self,
        replacement_dict: dict,
        return_dict: bool = False,
        jinja_env: Optional[Environment] = None,
        max_nesting: Optional[int] = None,
        template_renderer: Optional[TemplateRenderer] = None
    ) -> Union["QuestionBase", dict]:
        """Render the question components as jinja2 templates with the replacement dictionary.
        Handles nested template variables by recursively rendering until all variables are resolved.

        Args:
            replacement_dict: Dictionary of values to substitute in templates
            return_dict: If True, return a dict instead of QuestionBase instance
            jinja_env: Optional Jinja2 Environment to use for rendering
            max_nesting: Optional maximum nesting level (defaults to self.MAX_NESTING)
            template_renderer: Optional TemplateRenderer instance to use

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

        >>> from edsl.questions import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "all_data", question_text = "Scenario data: {{ scenario }}")
        >>> result = q.render({"name": "Alice", "age": 30})
        >>> "Alice" in result.question_text and "30" in result.question_text
        True

        >>> from edsl.questions import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "mixed", question_text = "Name: {{ scenario.name }}, All: {{ scenario }}")
        >>> result = q.render({"name": "Bob", "city": "NYC"})
        >>> "Name: Bob" in result.question_text and "city" in result.question_text
        True
        """
        from ..scenarios import Scenario

        # Prepare replacement dict
        strings_only_replacement_dict = {
            k: v for k, v in replacement_dict.items() if not isinstance(v, Scenario)
        }
        
        # Create a shallow copy for the "scenario" key to avoid infinite recursion
        # This allows both {{ scenario.x }} and {{ scenario }} to work
        # {{ scenario.x }} accesses keys, {{ scenario }} converts to string
        # Filter out keys starting with underscore (private/internal keys)
        scenario_dict_for_template = {
            k: v for k, v in strings_only_replacement_dict.items()
            if not k.startswith('_')
        }
        strings_only_replacement_dict["scenario"] = scenario_dict_for_template

        # Create or use provided template renderer
        if template_renderer is None:
            if max_nesting is None:
                max_nesting = self.MAX_NESTING
            template_renderer = TemplateRenderer(
                max_nesting=max_nesting,
                jinja_env=jinja_env
            )

        # Create render function that uses the template renderer
        def render_string(value: str) -> str:
            return template_renderer.render_string(
                value,
                strings_only_replacement_dict,
                exception_class=self.MaxTemplateNestingExceeded
            )

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
