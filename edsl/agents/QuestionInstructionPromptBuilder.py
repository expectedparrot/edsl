from typing import Dict, List, Set
from warnings import warn
import logging
from edsl.prompts.Prompt import Prompt

from edsl.agents.QuestionTemplateReplacementsBuilder import (
    QuestionTemplateReplacementsBuilder as QTRB,
)


class QuestionInstructionPromptBuilder:
    """Handles the construction and rendering of question instructions."""

    @classmethod
    def from_prompt_constructor(cls, prompt_constructor: "PromptConstructor"):
        
        model = prompt_constructor.model
        survey = prompt_constructor.survey
        question = prompt_constructor.question
        return cls(prompt_constructor, model, survey, question)

    def __init__(self, prompt_constructor: "PromptConstructor", model, survey, question):
        self.prompt_constructor = prompt_constructor
        self.model = model
        self.survey = survey
        self.question = question

        self.scenario = prompt_constructor.scenario
        self.prior_answers_dict = prompt_constructor.prior_answers_dict()


    def build(self) -> Prompt:
        """Builds the complete question instructions prompt with all necessary components.

        Returns:
            Prompt: The fully rendered question instructions
        """
        import time
        
        start = time.time()
        
        # Create base prompt
        base_start = time.time()
        base_prompt = self._create_base_prompt()
        base_end = time.time()
        logging.debug(f"Time for base prompt: {base_end - base_start}")
        
        # Enrich with options
        enrich_start = time.time()
        enriched_prompt = self._enrich_with_question_options(base_prompt)
        enrich_end = time.time()
        logging.debug(f"Time for enriching with options: {enrich_end - enrich_start}")
        
        # Render prompt
        render_start = time.time()
        rendered_prompt = self._render_prompt(enriched_prompt)
        render_end = time.time()
        logging.debug(f"Time for rendering prompt: {render_end - render_start}")
        
        # Validate template variables
        validate_start = time.time()
        self._validate_template_variables(rendered_prompt)
        validate_end = time.time()
        logging.debug(f"Time for template validation: {validate_end - validate_start}")
        
        # Append survey instructions
        append_start = time.time()
        final_prompt = self._append_survey_instructions(rendered_prompt)
        append_end = time.time()
        logging.debug(f"Time for appending survey instructions: {append_end - append_start}")
        
        end = time.time()
        logging.debug(f"Total time in build_question_instructions: {end - start}")
        
        return final_prompt

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
        import time
        
        start = time.time()
        
        if "question_options" in prompt_data["data"]:
            from edsl.agents.question_option_processor import QuestionOptionProcessor
            
            processor_start = time.time()

            question_options = (QuestionOptionProcessor(self.scenario, self.prior_answers_dict)
                                .get_question_options(question_data=prompt_data["data"])
            )
            processor_end = time.time()
            logging.debug(f"Time to process question options: {processor_end - processor_start}")
            
            prompt_data["data"]["question_options"] = question_options
            
        end = time.time()
        logging.debug(f"Total time in _enrich_with_question_options: {end - start}")
        
        return prompt_data

    def _render_prompt(self, prompt_data: Dict) -> Prompt:
        """Renders the prompt using the replacement dictionary.

        Args:
            prompt_data: Dictionary containing prompt and question data

        Returns:
            Prompt: Rendered instructions
        """
        import time
        
        start = time.time()
        
        # Build replacement dict
        dict_start = time.time()
        replacement_dict = QTRB.from_prompt_constructor(self.prompt_constructor).build_replacement_dict(
            prompt_data["data"]
        )
        dict_end = time.time()
        logging.debug(f"Time to build replacement dict: {dict_end - dict_start}")
        
        # Render with dict
        render_start = time.time()
        result = prompt_data["prompt"].render(replacement_dict)
        render_end = time.time()
        logging.debug(f"Time to render with dict: {render_end - render_start}")
        
        end = time.time()
        logging.debug(f"Total time in _render_prompt: {end - start}")
        
        return result

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
                logging.warning(f"Question name found in undefined_template_variables: {question_name}")

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
