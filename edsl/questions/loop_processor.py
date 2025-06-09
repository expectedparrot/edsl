from typing import List, Any, Dict, Tuple
from jinja2 import Environment, Undefined
from .question_base import QuestionBase
from ..scenarios import Scenario, ScenarioList
from ..surveys import Survey


class LoopProcessor:
    def __init__(self, question: QuestionBase):
        self.question = question
        self.env = Environment(undefined=Undefined)

    def process_templates(self, scenario_list: ScenarioList) -> List[QuestionBase]:
        """Process templates for each scenario and return list of modified questions.

        Args:
            scenario_list: List of scenarios to process templates against

        Returns:
            List of QuestionBase objects with rendered templates
        """
        questions = []
        starting_name = self.question.question_name

        for index, scenario in enumerate(scenario_list):
            question_data = self.question.to_dict().copy()
            processed_data = self._process_data(question_data, scenario)

            if processed_data["question_name"] == starting_name:
                processed_data["question_name"] += f"_{index}"

            questions.append(QuestionBase.from_dict(processed_data))

        return questions

    def _process_data(
        self, data: Dict[str, Any], scenario: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process all data fields according to their type.

        Args:
            data: Dictionary of question data
            scenario: Current scenario to render templates against

        Returns:
            Processed dictionary with rendered templates
        """
        processed = {}

        extended_scenario = scenario.copy()
        extended_scenario.update({"scenario": scenario})

        for key, value in [(k, v) for k, v in data.items() if v is not None]:
            processed[key] = self._process_value(key, value, extended_scenario)

        return processed

    def _process_value(self, key: str, value: Any, scenario: Dict[str, Any]) -> Any:
        """Process a single value according to its type.

        Args:
            key: Dictionary key
            value: Value to process
            scenario: Current scenario

        Returns:
            Processed value
        """
        if key == "question_options" and isinstance(value, str):
            return value

        if key == "option_labels":

            return (
                eval(self._render_template(value, scenario))
                if isinstance(value, str)
                else value
            )

        if isinstance(value, str):
            return self._render_template(value, scenario)

        if isinstance(value, list):
            return self._process_list(value, scenario)

        if isinstance(value, dict):
            return self._process_dict(value, scenario)

        if isinstance(value, (int, float)):
            return value

        from .exceptions import QuestionValueError

        raise QuestionValueError(
            f"Unexpected value type: {type(value)} for key '{key}'"
        )

    def _render_template(self, template: str, scenario: Dict[str, Any]) -> str:
        """Render a single template string.

        Args:
            template: Template string to render
            scenario: Current scenario

        Returns:
            Rendered template string, preserving any unmatched template variables

        Examples:
            >>> from edsl.questions import QuestionBase
            >>> q = QuestionBase()
            >>> q.question_text = "test"
            >>> p = LoopProcessor(q)
            >>> p._render_template("Hello {{name}}!", {"name": "World"})
            'Hello World!'

            >>> p._render_template("{{a}} and {{b}}", {"b": 6})
            '{{ a }} and 6'

            >>> p._render_template("{{x}} + {{y}} = {{z}}", {"x": 2, "y": 3})
            '2 + 3 = {{ z }}'

            >>> p._render_template("No variables here", {})
            'No variables here'

            >>> p._render_template("{{item.price}}", {"item": {"price": 9.99}})
            '9.99'

            >>> p._render_template("{{item.missing}}", {"item": {"price": 9.99}})
            '{{ item.missing }}'
        """
        import re

        # Regular expression to find Jinja2 variables in the template
        pattern = r"(?P<open>\{\{\s*)(?P<var>[a-zA-Z0-9_.]+)(?P<close>\s*\}\})"

        def replace_var(match):
            var_name = match.group("var")
            # We're keeping the original formatting with braces
            # but not using these variables directly
            # open_brace = match.group('open')
            # close_brace = match.group('close')

            # Try to evaluate the variable in the context
            try:
                # Handle nested attributes (like item.price)
                parts = var_name.split(".")
                value = scenario
                for part in parts:
                    if part in value:
                        value = value[part]
                    else:
                        # If any part doesn't exist, return the original with spacing
                        return f"{{ {var_name} }}".replace("{", "{{").replace("}", "}}")
                # Return the rendered value if successful
                return str(value)
            except (KeyError, TypeError):
                # Return the original variable name with the expected spacing
                return f"{{ {var_name} }}".replace("{", "{{").replace("}", "}}")

        # Replace all variables in the template
        result = re.sub(pattern, replace_var, template)
        return result

    def _process_list(self, items: List[Any], scenario: Dict[str, Any]) -> List[Any]:
        """Process all items in a list.

        Args:
            items: List of items to process
            scenario: Current scenario

        Returns:
            List of processed items
        """
        return [
            self._render_template(item, scenario) if isinstance(item, str) else item
            for item in items
        ]

    def _process_dict(
        self, data: Dict[str, Any], scenario: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process all keys and values in a dictionary.

        Args:
            data: Dictionary to process
            scenario: Current scenario

        Returns:
            Dictionary with processed keys and values
        """
        return {
            (self._render_template(k, scenario) if isinstance(k, str) else k): (
                self._render_template(v, scenario) if isinstance(v, str) else v
            )
            for k, v in data.items()
        }


class LongSurveyLoopProcessor:
    """
    A modified LoopProcessor that creates a long survey where each question is rendered for each scenario.

    Returns a tuple of (long_questions, long_scenario_list).
    The long scenario list is essentially a flattened scenario list with one scenario that has many fields.

    Usage:
    >>> loop_processor = LongSurveyLoopProcessor(survey, scenario_list)
    >>> long_questions_list, long_scenario_list = loop_processor.process_templates_for_all_questions()
    """

    def __init__(self, survey: Survey, scenario_list: ScenarioList):
        self.survey = survey
        self.scenario_list = scenario_list
        self.env = Environment(undefined=Undefined)
        self.long_scenario_dict = {}

    def process_templates_for_all_questions(
        self,
    ) -> Tuple[List[QuestionBase], ScenarioList]:
        long_questions_list = []

        self.long_scenario_dict = {}

        for question in self.survey.questions:
            updates_for_one_question = self.process_templates(
                question, self.scenario_list
            )
            long_questions_list.extend(updates_for_one_question)

        long_scenario_list = ScenarioList([Scenario(data=self.long_scenario_dict)])

        return long_questions_list, long_scenario_list

    def process_templates(
        self, question: QuestionBase, scenario_list: ScenarioList
    ) -> List[QuestionBase]:
        """Process templates for each scenario and return list of modified questions.

        Args:
            scenario_list: List of scenarios to process templates against

        Returns:
            List of QuestionBase objects with rendered templates
        """
        import re

        questions = []
        starting_name = question.question_name

        # Check for Jinja2 variables in the question text
        pattern = self._jinja_variable_pattern()
        variables_in_question_text = (
            re.search(pattern, question.question_text) is not None
        )
        if variables_in_question_text:
            for index, scenario in enumerate(scenario_list):
                question_data = question.to_dict().copy()
                processed_data = self._process_data(question_data, scenario, index)

                if processed_data["question_name"] == starting_name:
                    processed_data["question_name"] += f"_{index}"

                questions.append(QuestionBase.from_dict(processed_data))
        else:
            questions.append(question)

        return questions

    def _process_data(
        self, data: Dict[str, Any], scenario: Dict[str, Any], scenario_index: int
    ) -> Dict[str, Any]:
        """Process all data fields according to their type.

        Args:
            data: Dictionary of question data
            scenario: Current scenario to render templates against

        Returns:
            Processed dictionary with rendered templates
        """
        processed = {}

        extended_scenario = scenario.copy()
        extended_scenario.update({"scenario": scenario})

        for key, value in [(k, v) for k, v in data.items() if v is not None]:
            processed[key] = self._process_value(
                key, value, extended_scenario, scenario_index
            )

        return processed

    def _process_value(
        self, key: str, value: Any, scenario: Dict[str, Any], scenario_index: int
    ) -> Any:
        """Process a single value according to its type.

        Args:
            key: Dictionary key
            value: Value to process
            scenario: Current scenario

        Returns:
            Processed value
        """
        if key == "question_options" and isinstance(value, str):
            return value

        if key == "option_labels":

            return (
                eval(self._render_template(value, scenario, scenario_index))
                if isinstance(value, str)
                else value
            )

        if isinstance(value, str):
            return self._render_template(value, scenario, scenario_index)

        if isinstance(value, list):
            return self._process_list(value, scenario, scenario_index)

        if isinstance(value, dict):
            return self._process_dict(value, scenario, scenario_index)

        if isinstance(value, (int, float)):
            return value

        from edsl.questions.exceptions import QuestionValueError

        raise QuestionValueError(
            f"Unexpected value type: {type(value)} for key '{key}'"
        )

    def _jinja_variable_pattern(self) -> str:

        # Regular expression to find Jinja2 variables in the template
        pattern = r"(?P<open>\{\{\s*)(?P<var>[a-zA-Z0-9_.]+)(?P<close>\s*\}\})"
        return pattern

    def _render_template(
        self, template: str, scenario: Dict[str, Any], scenario_index: int
    ) -> str:
        """Render a single template string.

        Args:
            template: Template string to render
            scenario: Current scenario

        Returns:
            Rendered template string, preserving any unmatched template variables

        Examples:
            >>> from edsl.questions import QuestionBase
            >>> q = QuestionBase()
            >>> q.question_text = "test"
            >>> sl = ScenarioList([Scenario({"name": "World"}), Scenario({"name": "everyone"})])
            >>> p = LongSurveyLoopProcessor(q, sl)
            >>> p._render_template("Hello {{name}}!", {"name": "everyone"}, scenario_index=1)
            'Hello {{ scenario.name_1 }}!'

            >>> p._render_template("{{a}} and {{b}}", {"b": 6}, scenario_index=1)
            '{{ a }} and {{ scenario.b_1 }}'

            >>> p._render_template("{{x}} + {{y}} = {{z}}", {"x": 2, "y": 3}, scenario_index=5)
            '{{ scenario.x_5 }} + {{ scenario.y_5 }} = {{ z }}'

            >>> p._render_template("No variables here", {}, scenario_index=0)
            'No variables here'

            >>> p._render_template("{{item.price}}", {"item": {"price": 9.99}}, scenario_index=3)
            '{{ scenario.item_3.price }}'

            >>> p._render_template("{{item.missing}}", {"item": {"price": 9.99}}, scenario_index=3)
            '{{ scenario.item_3.missing }}'
        """
        import re

        # Regular expression to find Jinja2 variables in the template
        pattern = self._jinja_variable_pattern()

        def replace_var(match):
            var_name = match.group("var")
            # We're keeping the original formatting with braces
            # but not using these variables directly
            # open_brace = match.group('open')
            # close_brace = match.group('close')
            try:
                # Handle nested attributes (like item.price)
                parts = var_name.split(".")
                base_var = parts[0]

                self.long_scenario_dict.update(
                    {f"{base_var}_{scenario_index}": scenario[base_var]}
                )

                if len(parts) > 1:
                    non_name_parts = ".".join(parts[1:])
                    result = (
                        f"{{ scenario.{base_var}_{scenario_index}.{non_name_parts} }}"
                    )
                else:
                    result = f"{{ scenario.{base_var}_{scenario_index} }}"

                result = result.replace("{", "{{").replace("}", "}}")
                return result
            except (KeyError, TypeError) as e:
                # Return the original variable name with the expected spacing
                result = f"{{ {var_name} }}".replace("{", "{{").replace("}", "}}")
                return result

        # Replace all variables in the template
        result = re.sub(pattern, replace_var, template)
        return result

    def _process_list(
        self, items: List[Any], scenario: Dict[str, Any], scenario_index: int
    ) -> List[Any]:
        """Process all items in a list.

        Args:
            items: List of items to process
            scenario: Current scenario

        Returns:
            List of processed items
        """
        return [
            (
                self._render_template(item, scenario, scenario_index)
                if isinstance(item, str)
                else item
            )
            for item in items
        ]

    def _process_dict(
        self, data: Dict[str, Any], scenario: Dict[str, Any], scenario_index: int
    ) -> Dict[str, Any]:
        """Process all keys and values in a dictionary.

        Args:
            data: Dictionary to process
            scenario: Current scenario

        Returns:
            Dictionary with processed keys and values
        """
        return {
            (
                self._render_template(k, scenario, scenario_index)
                if isinstance(k, str)
                else k
            ): (
                self._render_template(v, scenario, scenario_index)
                if isinstance(v, str)
                else v
            )
            for k, v in data.items()
        }


if __name__ == "__main__":
    import doctest

    doctest.testmod()
