from typing import Dict, List, Set
from warnings import warn
from edsl.prompts.Prompt import Prompt

from edsl.agents.QuestionTemplateReplacementsBuilder import (
    QuestionTemplateReplacementsBuilder as QTRB,
)


class QuestionInstructionPromptBuilder:
    """Handles the construction and rendering of question instructions."""

    def __init__(self, prompt_constructor: "PromptConstructor"):
        self.prompt_constructor = prompt_constructor

        self.model = self.prompt_constructor.model
        self.survey = self.prompt_constructor.survey
        self.question = self.prompt_constructor.question

    def build(self) -> Prompt:
        """Builds the complete question instructions prompt with all necessary components.

        Returns:
            Prompt: The fully rendered question instructions
        """
        base_prompt = self._create_base_prompt()
        enriched_prompt = self._enrich_with_question_options(base_prompt)
        rendered_prompt = self._render_prompt(enriched_prompt)
        self._validate_template_variables(rendered_prompt)

        return self._append_survey_instructions(rendered_prompt)

    def _create_base_prompt(self) -> Dict:
        """Creates the initial prompt with basic question data.

        Returns:
            Dict: Base question data
        """
        return {
            "prompt": Prompt(self.question.get_instructions(model=self.model.model)),
            "data": self.question.data.copy(),
        }

    def _enrich_with_question_options(self, prompt_data: Dict) -> Dict:
        """Enriches the prompt data with question options if they exist.

        Args:
            prompt_data: Dictionary containing prompt and question data

        Returns:
            Dict: Enriched prompt data
        """
        if "question_options" in prompt_data["data"]:
            from edsl.agents.question_option_processor import QuestionOptionProcessor

            question_options = QuestionOptionProcessor(
                self.prompt_constructor
            ).get_question_options(question_data=prompt_data["data"])

            prompt_data["data"]["question_options"] = question_options
        return prompt_data

    def _render_prompt(self, prompt_data: Dict) -> Prompt:
        """Renders the prompt using the replacement dictionary.

        Args:
            prompt_data: Dictionary containing prompt and question data

        Returns:
            Prompt: Rendered instructions
        """

        replacement_dict = QTRB(self.prompt_constructor).build_replacement_dict(
            prompt_data["data"]
        )
        return prompt_data["prompt"].render(replacement_dict)

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
                print(
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
