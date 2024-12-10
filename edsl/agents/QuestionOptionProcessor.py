from jinja2 import Environment, meta
from typing import List, Optional, Union


class QuestionOptionProcessor:
    """
    Class that manages the processing of question options.
    These can be provided directly, as a template string, or fetched from prior answers or the scenario.
    """

    def __init__(self, prompt_constructor):
        self.prompt_constructor = prompt_constructor

    @staticmethod
    def _get_default_options() -> list:
        """Return default placeholder options."""
        return [f"<< Option {i} - Placeholder >>" for i in range(1, 4)]

    @staticmethod
    def _parse_template_variable(template_str: str) -> str:
        """
        Extract the variable name from a template string.

        Args:
            template_str (str): Jinja template string

        Returns:
            str: Name of the first undefined variable in the template

        >>> QuestionOptionProcessor._parse_template_variable("Here are some {{ options }}")
        'options'
        >>> QuestionOptionProcessor._parse_template_variable("Here are some {{ options }} and {{ other }}")
        Traceback (most recent call last):
        ...
        ValueError: Multiple variables found in template string
        >>> QuestionOptionProcessor._parse_template_variable("Here are some")
        Traceback (most recent call last):
        ...
        ValueError: No variables found in template string
        """
        env = Environment()
        parsed_content = env.parse(template_str)
        undeclared_variables = list(meta.find_undeclared_variables(parsed_content))
        if not undeclared_variables:
            raise ValueError("No variables found in template string")
        if len(undeclared_variables) > 1:
            raise ValueError("Multiple variables found in template string")
        return undeclared_variables[0]

    @staticmethod
    def _get_options_from_scenario(
        scenario: dict, option_key: str
    ) -> Union[list, None]:
        """
        Try to get options from scenario data.

        >>> from edsl import Scenario
        >>> scenario = Scenario({"options": ["Option 1", "Option 2"]})
        >>> QuestionOptionProcessor._get_options_from_scenario(scenario, "options")
        ['Option 1', 'Option 2']


        Returns:
            list | None: List of options if found in scenario, None otherwise
        """
        scenario_options = scenario.get(option_key)
        return scenario_options if isinstance(scenario_options, list) else None

    @staticmethod
    def _get_options_from_prior_answers(
        prior_answers: dict, option_key: str
    ) -> Union[list, None]:
        """
        Try to get options from prior answers.

        prior_answers (dict): Dictionary of prior answers
        option_key (str): Key to look up in prior answers

        >>> from edsl import QuestionList as Q
        >>> q = Q.example()
        >>> q.answer = ["Option 1", "Option 2"]
        >>> prior_answers = {"options": q}
        >>> QuestionOptionProcessor._get_options_from_prior_answers(prior_answers, "options")
        ['Option 1', 'Option 2']
        >>> QuestionOptionProcessor._get_options_from_prior_answers(prior_answers, "wrong_key") is None
        True

        Returns:
            list | None: List of options if found in prior answers, None otherwise
        """
        prior_answer = prior_answers.get(option_key)
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
        >>> processor = QuestionOptionProcessor(mpc)

        The basic case where options are directly provided:

        >>> question_data = {"question_options": ["Option 1", "Option 2"]}
        >>> processor.get_question_options(question_data)
        ['Option 1', 'Option 2']

        The case where options are provided as a template string:

        >>> question_data = {"question_options": "{{ options }}"}
        >>> processor.get_question_options(question_data)
        ['Option 1', 'Option 2']

        The case where there is a templace string but it's in the prior answers:

        >>> class MockQuestion:
        ...     pass
        >>> q0 = MockQuestion()
        >>> q0.answer = ["Option 1", "Option 2"]
        >>> mpc.prior_answers_dict = lambda: {'q0': q0}
        >>> processor = QuestionOptionProcessor(mpc)
        >>> question_data = {"question_options": "{{ q0 }}"}
        >>> processor.get_question_options(question_data)
        ['Option 1', 'Option 2']

        The case we're no options are found:
        >>> processor.get_question_options({"question_options": "{{ poop }}"})
        ['<< Option 1 - Placeholder >>', '<< Option 2 - Placeholder >>', '<< Option 3 - Placeholder >>']

        """
        options_entry = question_data.get("question_options")

        # If not a template string, return as is or default
        if not isinstance(options_entry, str):
            return options_entry if options_entry else self._get_default_options()

        # Parse template to get variable name
        option_key = self._parse_template_variable(options_entry)

        # Try getting options from scenario
        scenario_options = self._get_options_from_scenario(
            self.prompt_constructor.scenario, option_key
        )
        if scenario_options:
            return scenario_options

        # Try getting options from prior answers
        prior_answer_options = self._get_options_from_prior_answers(
            self.prompt_constructor.prior_answers_dict(), option_key
        )
        if prior_answer_options:
            return prior_answer_options

        return self._get_default_options()


if __name__ == "__main__":
    import doctest

    doctest.testmod()
