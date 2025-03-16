from typing import List, Any, Dict
from jinja2 import Environment, Undefined
from .question_base import QuestionBase
from ..scenarios import ScenarioList

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
        raise QuestionValueError(f"Unexpected value type: {type(value)} for key '{key}'")

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
        pattern = r'(?P<open>\{\{\s*)(?P<var>[a-zA-Z0-9_.]+)(?P<close>\s*\}\})'
        
        def replace_var(match):
            var_name = match.group('var')
            # We're keeping the original formatting with braces
            # but not using these variables directly
            # open_brace = match.group('open')
            # close_brace = match.group('close')
            
            # Try to evaluate the variable in the context
            try:
                # Handle nested attributes (like item.price)
                parts = var_name.split('.')
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


if __name__ == "__main__":
    import doctest

    doctest.testmod()
