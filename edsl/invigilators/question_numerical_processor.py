from typing import Union, Literal

import edsl.scenarios.scenario  # noqa: F401
from .question_attribute_processor import (
    QuestionAttributeProcessor,
)


class QuestionNumericalProcessor(QuestionAttributeProcessor):
    """
    Class that manages the processing of numerical question attributes (e.g. min_value, max_value for QuestionNumerical).
    These can be provided directly, as a template string, or fetched from prior answers or the scenario.
    """

    def __init__(
        self, scenario: "edsl.scenarios.scenario.Scenario", prior_answers_dict: dict
    ):
        # Call parent class constructor
        super().__init__(scenario, prior_answers_dict)

    @staticmethod
    def _get_default_numerical_value() -> Union[int, float, None]:
        """Return default placeholder numerical value."""
        return None

    def _get_numerical_value_from_scenario(
        self, scenario: dict, numerical_key: tuple
    ) -> Union[int, float, None]:
        """
        Try to get numerical value from scenario data.

        >>> from edsl import Scenario
        >>> scenario = Scenario({"age_min": 20, "age_max": 100})
        >>> QuestionNumberProcessor._get_numerical_value_from_scenario(scenario, ("age_min",))
        20


        Returns:
            int | float | None: Numerical value if found in scenario, None otherwise
        """
        scenario_numerical_value = self._get_nested_key(scenario, numerical_key)
        return (
            scenario_numerical_value
            if isinstance(scenario_numerical_value, (int, float))
            else None
        )

    def _get_numerical_value_from_prior_answers(
        self, prior_answers: dict, numerical_key: tuple
    ) -> Union[int, float, None]:
        """
        Try to get numerical value from prior answers.

        prior_answers (dict): Dictionary of prior answers
        numerical_key (str): Key to look up in prior answers

        >>> from edsl import QuestionNumerical as Q
        >>> q = Q.example()
        >>> q.answer = 35
        >>> prior_answers = {"age": q}
        >>> QuestionNumericalProcessor._get_numerical_value_from_prior_answers(prior_answers, ("age",))
        35
        >>> QuestionNumericalProcessor._get_numerical_value_from_prior_answers(prior_answers, ("wrong_key",)) is None
        True

        Returns:
            int | float | None: Numerical value if found in prior answers, None otherwise
        """
        prior_answer = self._get_nested_key(prior_answers, numerical_key)
        if prior_answer and hasattr(prior_answer, "answer"):
            if isinstance(prior_answer.answer, (int, float)):
                return prior_answer.answer
        return None

    def get_question_numerical_value(
        self, question_data: dict, key: Literal["min_value", "max_value"]
    ) -> list:
        """
        Extract and process question numerical value from question data.

        Args:
            question_data (dict): Dictionary containing question configuration

        Returns:
            int | float | None: Question numerical value. Returns default placeholders if no valid numerical value found.

        >>> class MockPromptConstructor:
        ...     pass
        >>> mpc = MockPromptConstructor()
        >>> from edsl import Scenario
        >>> mpc.scenario = Scenario({"age_min": 20, "age_max": 100})
        >>> mpc.prior_answers_dict = lambda: {'q0': q0}
        >>> processor = QuestionNumericalProcessor.from_prompt_constructor(mpc)

        The basic case where the numerical value is directly provided:

        >>> question_data = {"min_value": 35}
        >>> processor.get_question_numerical_value(question_data)
        35

        The case where the numerical value is provided as a template string:

        >>> question_data = {"min_value": "{{ scenario.age_min }}"}
        >>> processor.get_question_numerical_value(question_data)
        20

        The case where there is a template string but it's in the prior answers:

        >>> class MockQuestion:
        ...     pass
        >>> q0 = MockQuestion()
        >>> q0.answer = 35
        >>> mpc.prior_answers_dict = lambda: {'q0': q0}
        >>> processor = QuestionNumericalProcessor.from_prompt_constructor(mpc)
        >>> question_data = {"min_value": "{{ q0.answer }}"}
        >>> processor.get_question_numerical_value(question_data)
        35

        The case where no numerical value is found:
        >>> processor.get_question_numerical_value({"min_value": "{{ poop }}"})
        None

        """
        numerical_value = question_data.get(key)

        # If not a template string, return as is or default
        if not isinstance(numerical_value, str):
            return (
                numerical_value
                if numerical_value
                else self._get_default_numerical_value()
            )

        # Parse template to get variable name
        raw_numerical_key = self._parse_template_variable(numerical_value)

        source_type = None

        if isinstance(raw_numerical_key, tuple):
            if raw_numerical_key[0] == "scenario":
                source_type = "scenario"
                numerical_key = raw_numerical_key[1:]
            else:
                source_type = "prior_answers"
                numerical_key = (raw_numerical_key[0],)
        else:
            numerical_key = (raw_numerical_key,)

        if source_type == "scenario":
            # Try getting numerical value from scenario
            scenario_numerical_value = self._get_numerical_value_from_scenario(
                self.scenario, numerical_key
            )
            if scenario_numerical_value:
                return scenario_numerical_value

        if source_type == "prior_answers":

            # Try getting numerical value from prior answers
            prior_answer_numerical_value = self._get_numerical_value_from_prior_answers(
                self.prior_answers_dict, numerical_key
            )
            if prior_answer_numerical_value:
                return prior_answer_numerical_value

        return self._get_default_numerical_value()


if __name__ == "__main__":
    import doctest

    doctest.testmod()
