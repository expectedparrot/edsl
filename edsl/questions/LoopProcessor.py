from typing import List, Any, Dict, Union
from jinja2 import Environment
from edsl.questions.QuestionBase import QuestionBase
from edsl import ScenarioList


class LoopProcessor:
    def __init__(self, question: QuestionBase):
        self.question = question
        self.env = Environment()

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

        for key, value in [(k, v) for k, v in data.items() if v is not None]:
            processed[key] = self._process_value(key, value, scenario)

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
            import json

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

        raise ValueError(f"Unexpected value type: {type(value)} for key '{key}'")

    def _render_template(self, template: str, scenario: Dict[str, Any]) -> str:
        """Render a single template string.

        Args:
            template: Template string to render
            scenario: Current scenario

        Returns:
            Rendered template string
        """
        return self.env.from_string(template).render(scenario)

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


# Usage example:
"""
from edsl import QuestionFreeText, ScenarioList

question = QuestionFreeText(
    question_text="What are your thoughts on: {{subject}}?",
    question_name="base_{{subject}}"
)
processor = TemplateProcessor(question)
scenarios = ScenarioList.from_list("subject", ["Math", "Economics", "Chemistry"])
processed_questions = processor.process_templates(scenarios)
"""
