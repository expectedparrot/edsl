from typing import Dict, Set, Any, Union, TYPE_CHECKING
from warnings import warn
import logging
from ..prompts import Prompt

if TYPE_CHECKING:
    from .prompt_constructor import PromptConstructor
    from ..language_models import Model
    from ..surveys import Survey
    from ..questions import QuestionBase
    from ..scenarios import Scenario
    from ..agents import Agent

from .question_template_replacements_builder import (
    QuestionTemplateReplacementsBuilder as QTRB,
)


class QuestionInstructionPromptBuilder:
    """Handles the construction and rendering of question instructions."""

    @classmethod
    def from_prompt_constructor(cls, prompt_constructor: "PromptConstructor"):

        model = prompt_constructor.model
        survey = prompt_constructor.survey
        question = prompt_constructor.question
        scenario = prompt_constructor.scenario
        prior_answers_dict = prompt_constructor.prior_answers_dict()
        agent = prompt_constructor.agent
        return cls(
            prompt_constructor,
            model,
            survey,
            question,
            scenario,
            prior_answers_dict,
            agent,
        )

    def __init__(
        self,
        prompt_constructor: "PromptConstructor",
        model: "Model",
        survey: "Survey",
        question: "QuestionBase",
        scenario: "Scenario",
        prior_answers_dict: Dict[str, Any],
        agent: "Agent",
    ):

        self.qtrb = QTRB(scenario, question, prior_answers_dict, agent)

        self.model = model
        self.survey = survey
        self.question = question
        self.agent = agent
        self.scenario = scenario
        self.prior_answers_dict = prior_answers_dict

        self.captured_variables = {}

    def build(self) -> Prompt:
        """Builds the complete question instructions prompt with all necessary components.

        Returns:
            Prompt: The fully rendered question instructions to be send to the Language Model

        >>> from edsl import QuestionMultipleChoice
        >>> from edsl import Survey
        >>> q = Survey.example().questions[0]
        >>> from edsl import Model
        >>> class FakePromptConstructor:
        ...     def __init__(self, scenario, question, agent):
        ...         self.scenario = scenario
        ...         self.question = question
        ...         self.agent = agent
        ...         self.model = Model('test')
        ...         self.survey = Survey.example()
        ...     scenario = {"file1": "file1"}
        ...     question = q
        ...     agent = "agent"
        ...     def prior_answers_dict(self):
        ...         return {'q0': 'q0'}
        >>> mpc = FakePromptConstructor(
        ...     scenario={"file1": "file1"},
        ...     question=q,
        ...     agent="agent"
        ... )
        >>> qipb = QuestionInstructionPromptBuilder.from_prompt_constructor(mpc)
        >>> qipb.build()
        Prompt(text=\"""
        Do you like school?
        <BLANKLINE>
        <BLANKLINE>
        yes
        <BLANKLINE>
        no
        <BLANKLINE>
        <BLANKLINE>
        Only 1 option may be selected.
        <BLANKLINE>
        Respond only with a string corresponding to one of the options.
        <BLANKLINE>
        <BLANKLINE>
        After the answer, you can put a comment explaining why you chose that option on the next line.\""")
        """
        # Create base prompt
        base_prompt = self._create_base_prompt()

        # Enrich with options
        enriched_prompt = self._enrich_with_question_options(
            prompt_data=base_prompt,
            scenario=self.scenario,
            prior_answers_dict=self.prior_answers_dict,
        )

        # Render prompt
        rendered_prompt = self._render_prompt(enriched_prompt)

        # Validate template variables
        self._validate_template_variables(rendered_prompt)

        # Append survey instructions
        final_prompt = self._append_survey_instructions(rendered_prompt)

        return final_prompt

    def _create_base_prompt(self) -> Dict[str, Union[Prompt, Dict[str, Any]]]:
        """Creates the initial prompt with basic question data.

        The data are, e.g., the question name, question text, question options, etc.

        >>> from edsl import QuestionMultipleChoice
        >>> QuestionMultipleChoice.example().data.copy()
        {'question_name': 'how_feeling', 'question_text': 'How are you?', 'question_options': ['Good', 'Great', 'OK', 'Bad'], 'include_comment': False}

        Returns:
            Dict[str, Union[Prompt, Dict[str, Any]]]: Base question data with prompt and data fields
        """
        return {
            "prompt": Prompt(self.question.get_instructions(model=self.model.model)),
            "data": self.question.data.copy(),
        }

    @staticmethod
    def _process_question_options(
        question_data: Dict, scenario: "Scenario", prior_answers_dict: Dict
    ) -> Dict:
        """Processes and replaces question options in the question data if they exist.

        The question_options could be intended to be replaced with data from a scenario or prior answers.

        >>> question_data = {'question_name': 'q0', 'question_text': 'Do you like school?', 'question_options': '{{ scenario.options }}'}
        >>> scenario = {"options": ["yes", "no"]}
        >>> prior_answers_dict = {}
        >>> QuestionInstructionPromptBuilder._process_question_options(question_data, scenario, prior_answers_dict)
        {'question_name': 'q0', 'question_text': 'Do you like school?', 'question_options': ['yes', 'no']}

        Args:
            question_data: Dictionary containing question data
            scenario: Scenario object
            prior_answers_dict: Dictionary of prior answers

        Returns:
            Dict: Question data with processed question options
        """
        if "question_options" in question_data:
            from .question_option_processor import QuestionOptionProcessor
            question_options = QuestionOptionProcessor(
                scenario, prior_answers_dict
            ).get_question_options(question_data=question_data)
            question_data["question_options"] = question_options

        return question_data

    @staticmethod
    def _enrich_with_question_options(
        prompt_data: Dict, scenario: "Scenario", prior_answers_dict: Dict
    ) -> Dict:
        """Enriches the prompt data with processed question options if they exist.

        Args:
            prompt_data: Dictionary containing prompt and question data
            scenario: Scenario object
            prior_answers_dict: Dictionary of prior answers

        Returns:
            Dict: Enriched prompt data
        """
        prompt_data["data"] = (
            QuestionInstructionPromptBuilder._process_question_options(
                prompt_data["data"], scenario, prior_answers_dict
            )
        )
        return prompt_data

    def _render_prompt(self, prompt_data: Dict) -> Prompt:
        """Renders the prompt using the replacement dictionary.

        Args:
            prompt_data: Dictionary containing prompt and question data

        Returns:
            Prompt: Rendered instructions
        """
        # Build replacement dict
        replacement_dict = self.qtrb.build_replacement_dict(prompt_data["data"])

        # Render with dict
        rendered_prompt =prompt_data["prompt"].render(replacement_dict)
        if rendered_prompt.captured_variables:
            self.captured_variables.update(rendered_prompt.captured_variables)
            #print(f"Captured variables in QIPB: {self.captured_variables}")
        return rendered_prompt

    def _validate_template_variables(self, rendered_prompt: Prompt) -> None:
        """Validates that all template variables have been properly replaced.

        Args:
            rendered_prompt: The rendered prompt to validate

        Warns:
            If any template variables remain undefined
        """
        undefined_vars = rendered_prompt.undefined_template_variables({})

        # Check for question names in undefined variables
        self._check_question_names_in_undefined_vars(undefined_vars)

        # Warn about any remaining undefined variables
        if undefined_vars:
            warn(f"Question instructions still has variables: {undefined_vars}.")

    def _check_question_names_in_undefined_vars(self, undefined_vars: Set[str]) -> None:
        """Checks if any undefined variables match question names in the survey.

        Args:
            undefined_vars: Set of undefined template variables
        """
        for question_name in self.survey.question_names:
            if question_name in undefined_vars:
                logging.warning(
                    f"Question name found in undefined_template_variables: {question_name}"
                )

    def _append_survey_instructions(self, rendered_prompt: Prompt) -> Prompt:
        """Appends any relevant survey instructions to the rendered prompt.

        Args:
            rendered_prompt: The rendered prompt to append instructions to

        Returns:
            Prompt: Final prompt with survey instructions
        """
        relevant_instructions = self.survey._relevant_instructions(
            self.question.question_name
        )

        if not relevant_instructions:
            return rendered_prompt

        preamble = Prompt(text="")
        for instruction in relevant_instructions:
            preamble += instruction.text

        return preamble + rendered_prompt


if __name__ == "__main__":
    import doctest

    doctest.testmod()
