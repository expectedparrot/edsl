from typing import Union, TYPE_CHECKING


# import edsl.scenarios.scenario  # noqa: F401
from .question_attribute_processor import (
    QuestionAttributeProcessor,
)

if TYPE_CHECKING:
    from ..scenarios import Scenario


class QuestionOptionProcessor(QuestionAttributeProcessor):
    """
    Class that manages the processing of question options.
    These can be provided directly, as a template string, or fetched from prior answers or the scenario.
    """

    def __init__(self, scenario: "Scenario", prior_answers_dict: dict):
        # Call parent class constructor
        super().__init__(scenario, prior_answers_dict)

    @staticmethod
    def _get_default_options() -> list:
        """Return default placeholder options."""
        return [f"<< Option {i} - Placeholder >>" for i in range(1, 4)]

    def _get_options_from_scenario(
        self, scenario: dict, option_key: tuple
    ) -> Union[list, None]:
        """
        Try to get options from scenario data.

        >>> from edsl import Scenario
        >>> scenario = Scenario({"options": ["Option 1", "Option 2"]})
        >>> processor = QuestionOptionProcessor(scenario, {})
        >>> processor._get_options_from_scenario(scenario, ("options",))
        ['Option 1', 'Option 2']


        Returns:
            list | None: List of options if found in scenario, None otherwise
        """
        scenario_options = self._get_nested_key(scenario, option_key)
        return scenario_options if isinstance(scenario_options, list) else None

    def _get_options_from_prior_answers(
        self, prior_answers: dict, option_key: tuple
    ) -> Union[list, None]:
        """
        Try to get options from prior answers.

        prior_answers (dict): Dictionary of prior answers
        option_key (str): Key to look up in prior answers

        >>> from edsl import QuestionList as Q
        >>> q = Q.example()
        >>> q.answer = ["Option 1", "Option 2"]
        >>> prior_answers = {"options": q}
        >>> from edsl import Scenario
        >>> processor = QuestionOptionProcessor(Scenario({}), prior_answers)
        >>> processor._get_options_from_prior_answers(prior_answers, ("options",))
        ['Option 1', 'Option 2']
        >>> processor._get_options_from_prior_answers(prior_answers, ("wrong_key",)) is None
        True

        Returns:
            list | None: List of options if found in prior answers, None otherwise
        """
        prior_answer = self._get_nested_key(prior_answers, option_key)
        if prior_answer and hasattr(prior_answer, "answer"):
            if isinstance(prior_answer.answer, list):
                return prior_answer.answer
        return None

    def get_question_options(self, question_data: dict) -> list:
        """
        Extract and process question options from question data.

        Args:
            question_data (dict): Dictionary containing question configuration

        Returns:
            list: List of question options. Returns default placeholders if no valid options found.

        >>> class MockPromptConstructor:
        ...     pass
        >>> mpc = MockPromptConstructor()
        >>> from edsl import Scenario
        >>> mpc.scenario = Scenario({"options": ["Option 1", "Option 2"]})
        >>> class MockQuestion:
        ...     pass
        >>> q0 = MockQuestion()
        >>> q0.answer = ["Option 1", "Option 2"]
        >>> mpc.prior_answers_dict = lambda: {'q0': q0}
        >>> processor = QuestionOptionProcessor.from_prompt_constructor(mpc)

        The basic case where options are directly provided:

        >>> question_data = {"question_options": ["Option 1", "Option 2"]}
        >>> processor.get_question_options(question_data)
        ['Option 1', 'Option 2']

        The case where options are provided as a template string:

        >>> question_data = {"question_options": "{{ scenario.options }}"}
        >>> processor.get_question_options(question_data)
        ['Option 1', 'Option 2']

        The case where there is a template string but it's in the prior answers:

        >>> mpc.prior_answers_dict = lambda: {'q0': q0}
        >>> processor = QuestionOptionProcessor.from_prompt_constructor(mpc)
        >>> question_data = {"question_options": "{{ q0.answer }}"}
        >>> processor.get_question_options(question_data)
        ['Option 1', 'Option 2']

        The case where no options are found:
        >>> processor.get_question_options({"question_options": "{{ poop }}"})
        ['<< Option 1 - Placeholder >>', '<< Option 2 - Placeholder >>', '<< Option 3 - Placeholder >>']

        The case where options are piped with additional static options:
        >>> question_data = {"question_options": {"from": "{{ q0.answer }}", "add": ["Option 3", "Option 4"]}}
        >>> processor.get_question_options(question_data)
        ['Option 1', 'Option 2', 'Option 3', 'Option 4']

        """
        options_entry = question_data.get("question_options")

        # Handle dict format for piping with additional options
        if isinstance(options_entry, dict):
            # Extract the base options from the "from" template
            from_template = options_entry.get("from")
            additional_options = options_entry.get("add", [])

            # Get the base options using the template
            base_options = self._get_options_from_template(from_template)

            # Concatenate with additional options
            if base_options and base_options != self._get_default_options():
                return base_options + additional_options
            else:
                # If we can't resolve the template, just return additional options
                # or default if no additional options
                return additional_options if additional_options else self._get_default_options()

        # If not a template string or dict, return as is or default
        if not isinstance(options_entry, str):
            return options_entry if options_entry else self._get_default_options()

        # Handle simple template string (existing logic)
        return self._get_options_from_template(options_entry)

    def _get_options_from_template(self, template_string: str) -> list:
        """
        Helper method to extract options from a template string.

        Args:
            template_string (str): Template string like "{{ q1.answer }}" or "{{ scenario.options }}"

        Returns:
            list: List of options or default placeholders if not found
        """
        if not template_string:
            return self._get_default_options()

        # Parse template to get variable name
        raw_option_key = self._parse_template_variable(template_string)

        source_type = None

        if isinstance(raw_option_key, tuple):
            if raw_option_key[0] == "scenario":
                source_type = "scenario"
                option_key = raw_option_key[1:]
            else:
                source_type = "prior_answers"
                option_key = (raw_option_key[0],)
        else:
            option_key = (raw_option_key,)

        if source_type == "scenario":
            # Try getting options from scenario
            scenario_options = self._get_options_from_scenario(
                self.scenario, option_key
            )
            if scenario_options:
                return scenario_options

        if source_type == "prior_answers":
            # Try getting options from prior answers
            prior_answer_options = self._get_options_from_prior_answers(
                self.prior_answers_dict, option_key
            )
            if prior_answer_options:
                return prior_answer_options

        return self._get_default_options()


if __name__ == "__main__":
    import doctest

    doctest.testmod()
