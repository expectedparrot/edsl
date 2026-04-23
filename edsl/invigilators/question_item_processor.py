from typing import Union, TYPE_CHECKING

from .question_attribute_processor import QuestionAttributeProcessor

if TYPE_CHECKING:
    from ..scenarios import Scenario


class QuestionItemProcessor(QuestionAttributeProcessor):
    """
    Class that manages the processing of question items.
    These can be provided directly, as a template string, or fetched from prior
    answers or the scenario.
    """

    def __init__(self, scenario: "Scenario", prior_answers_dict: dict):
        super().__init__(scenario, prior_answers_dict)

    @staticmethod
    def _get_default_items() -> list:
        """Return default placeholder items."""
        return [f"<< Item {i} - Placeholder >>" for i in range(1, 4)]

    def _get_items_from_scenario(
        self, scenario: dict, item_key: tuple
    ) -> Union[list, None]:
        """
        Try to get items from scenario data.

        Returns:
            list | None: List of items if found in scenario, None otherwise
        """
        scenario_items = self._get_nested_key(scenario, item_key)
        return scenario_items if isinstance(scenario_items, list) else None

    def _get_items_from_prior_answers(
        self, prior_answers: dict, item_key: tuple
    ) -> Union[list, None]:
        """
        Try to get items from prior answers.

        Returns:
            list | None: List of items if found in prior answers, None otherwise
        """
        prior_answer = self._get_nested_key(prior_answers, item_key)
        if prior_answer and hasattr(prior_answer, "answer"):
            if isinstance(prior_answer.answer, list):
                return prior_answer.answer
        return None

    def get_question_items(self, question_data: dict) -> list:
        """
        Extract and process question items from question data.

        Args:
            question_data (dict): Dictionary containing question configuration

        Returns:
            list: List of question items. Returns default placeholders if no valid
                items are found.
        """
        items_entry = question_data.get("question_items")

        # Handle dict format for piping with additional items
        if isinstance(items_entry, dict):
            from_template = items_entry.get("from")
            additional_items = items_entry.get("add", [])

            base_items = self._get_items_from_template(from_template)

            if base_items and base_items != self._get_default_items():
                return base_items + additional_items

            return additional_items if additional_items else self._get_default_items()

        # If not a template string or dict, return as is or default
        if not isinstance(items_entry, str):
            return items_entry if items_entry else self._get_default_items()

        # Handle simple template string
        return self._get_items_from_template(items_entry)

    def _get_items_from_template(self, template_string: str) -> list:
        """
        Helper method to extract items from a template string.

        Args:
            template_string (str): Template string like "{{ q1.answer }}" or
                "{{ scenario.items }}"

        Returns:
            list: List of items or default placeholders if not found
        """
        if not template_string:
            return self._get_default_items()

        raw_item_key = self._parse_template_variable(template_string)

        source_type = None

        if isinstance(raw_item_key, tuple):
            if raw_item_key[0] == "scenario":
                source_type = "scenario"
                item_key = raw_item_key[1:]
            else:
                source_type = "prior_answers"
                item_key = (raw_item_key[0],)
        else:
            item_key = (raw_item_key,)

        if source_type == "scenario":
            scenario_items = self._get_items_from_scenario(self.scenario, item_key)
            if scenario_items:
                return scenario_items

        if source_type == "prior_answers":
            prior_answer_items = self._get_items_from_prior_answers(
                self.prior_answers_dict, item_key
            )
            if prior_answer_items:
                return prior_answer_items

        return self._get_default_items()

