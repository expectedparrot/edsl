from __future__ import annotations
import copy
import itertools
from typing import Optional, List, Callable, Type, TYPE_CHECKING, Union
from jinja2 import Environment, meta

if TYPE_CHECKING:
    from edsl.questions.QuestionBase import QuestionBase
    from edsl.scenarios.ScenarioList import ScenarioList


class QuestionBaseGenMixin:
    """Mixin for QuestionBase.
    
    This mostly has functions that are used to generate new questions from existing ones.
    
    """

    @staticmethod
    def get_jinja2_variables(template_str: str) -> Set[str]:
        """
        Extracts all variable names from a Jinja2 template using Jinja2's built-in parsing.

        Args:
        template_str (str): The Jinja2 template string

        Returns:
        Set[str]: A set of variable names found in the template
        """
        env = Environment()
        try:
            ast = env.parse(template_str)
        except TemplateSyntaxError:
            print(f"Error parsing template: {template_str}")
            raise

        return meta.find_undeclared_variables(ast)


    def _variables(self) -> dict:
        """Extract the variables from the question."""
        d = {}
        for key, value in self.data.items():
            if isinstance(value, str):
                d[key] = self.get_jinja2_variables(value)
        return d
    
    def _file_keys(self, scenario: "Scenario") -> list[str]:
        """Extract the file keys from the question."""
        file_keys = scenario._find_file_keys()
        question_text_variables = self._variables()['question_text']
        return [key for key in question_text_variables if key in file_keys]

    #     """Extract the file keys from the question."""
        
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

    class MaxTemplateNestingExceeded(Exception):
        """Raised when template rendering exceeds maximum allowed nesting level."""
        pass

    def _extract_question_options(self, scenario: Scenario, prior_answers_dict: dict):
        from edsl.agents.question_option_processor import QuestionOptionProcessor
        qop = QuestionOptionProcessor(scenario, prior_answers_dict)
        return qop.get_question_options(self.data)

    def render(self, replacement_dict: dict, return_dict: bool = False, question_data: Optional[dict] = None) -> Union["QuestionBase", dict]:
        """Render the question components as jinja2 templates with the replacement dictionary.
        Handles nested template variables by recursively rendering until all variables are resolved.
        
        Raises:
            MaxTemplateNestingExceeded: If template nesting exceeds MAX_NESTING levels
        
        >>> from edsl.questions.QuestionFreeText import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "color", question_text = "What is your favorite {{ thing }}?")
        >>> q.render({"thing": "color"})
        Question('free_text', question_name = \"""color\""", question_text = \"""What is your favorite color?\""")

        >>> from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
        >>> q = QuestionMultipleChoice(question_name = "color", question_text = "What is your favorite {{ thing }}?", question_options = ["red", "blue", "green"])
        >>> from edsl.scenarios.Scenario import Scenario
        >>> q.render(Scenario({"thing": "color"})).data
        {'question_name': 'color', 'question_text': 'What is your favorite color?', 'question_options': ['red', 'blue', 'green']}

        >>> from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
        >>> q = QuestionMultipleChoice(question_name = "color", question_text = "What is your favorite {{ thing }}?", question_options = ["red", "blue", "green"])
        >>> q.render({"thing": 1}).data
        {'question_name': 'color', 'question_text': 'What is your favorite 1?', 'question_options': ['red', 'blue', 'green']}


        >>> from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
        >>> from edsl.scenarios.Scenario import Scenario
        >>> q = QuestionMultipleChoice(question_name = "color", question_text = "What is your favorite {{ thing }}?", question_options = ["red", "blue", "green"])
        >>> q.render(Scenario({"thing": "color of {{ object }}", "object":"water"})).data
        {'question_name': 'color', 'question_text': 'What is your favorite color of water?', 'question_options': ['red', 'blue', 'green']}

        
        >>> from edsl.questions.QuestionFreeText import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "infinite", question_text = "This has {{ a }}")
        >>> q.render({"a": "{{ b }}", "b": "{{ a }}"}) # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        edsl.questions.question_base_gen_mixin.QuestionBaseGenMixin.MaxTemplateNestingExceeded:...
        """
        from jinja2 import Environment, meta
        from edsl.scenarios.Scenario import Scenario

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
            except Exception as e:
                import warnings
                warnings.warn("Failed to render string: " + value)
                return value
        if return_dict:
            return self._apply_function_dict(render_string, question_data=question_data)
        else:
            return self.apply_function(render_string, question_data=question_data)
      
    def apply_function(
        self, func: Callable, 
        exclude_components: Optional[List[str]] = None,
        question_data: Optional[dict] = None
    ) -> QuestionBase:
        from edsl.questions.QuestionBase import QuestionBase
        d = self._apply_function_dict(func, exclude_components, question_data)
        return QuestionBase.from_dict(d)

    def _apply_function_dict(
        self, func: Callable, 
        exclude_components: Optional[List[str]] = None, 
        question_data: Optional[dict] = None
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

        if question_data is None:
            question_data = copy.deepcopy(self.to_dict(add_edsl_version=False))
            
        for key, value in question_data.items():
            if key in exclude_components:
                continue
            if isinstance(value, dict):
                for k, v in value.items():
                    value[k] = func(v)
                question_data[key] = value
                continue
            if isinstance(value, list):
                value = [func(v) for v in value]
                question_data[key] = value
                continue
            question_data[key] = func(value)
        return question_data


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
