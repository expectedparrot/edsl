from typing import Dict, Set, Any, Union, TYPE_CHECKING
from warnings import warn
import logging
import time

from .prompt_constructor import PromptConstructor

if TYPE_CHECKING:
    from ..language_models import Model
    from ..surveys import Survey
    from ..questions import QuestionBase
    from ..scenarios import Scenario
    from ..agents import Agent
    from ..prompts import Prompt


from .question_template_replacements_builder import (
    QuestionTemplateReplacementsBuilder as QTRB,
)

# Global timing statistics for question instructions
_timing_stats = {
    'call_count': 0,
    'total_time': 0.0,
    'base_prompt_time': 0.0,
    'enrich_time': 0.0,
    'render_time': 0.0,
    'render_build_dict': 0.0,
    'render_prompt_render': 0.0,
    'validate_time': 0.0,
    'append_time': 0.0,
}


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

        instance = cls(
            prompt_constructor,
            model,
            survey,
            question,
            scenario,
            prior_answers_dict,
            agent,
        )

        return instance

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

    def build(self) -> "Prompt":
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
        build_start = time.time()

        # Create base prompt
        t0 = time.time()
        base_prompt = self._create_base_prompt()
        base_time = time.time() - t0
        _timing_stats['base_prompt_time'] += base_time

        # Enrich with options
        t1 = time.time()
        enriched_prompt = self._enrich_with_question_options(
            prompt_data=base_prompt,
            scenario=self.scenario,
            prior_answers_dict=self.prior_answers_dict,
        )
        enrich_time = time.time() - t1
        _timing_stats['enrich_time'] += enrich_time

        # Render prompt
        t2 = time.time()
        rendered_prompt = self._render_prompt(enriched_prompt)
        render_time = time.time() - t2
        _timing_stats['render_time'] += render_time

        # Validate template variables
        t3 = time.time()
        self._validate_template_variables(rendered_prompt)
        validate_time = time.time() - t3
        _timing_stats['validate_time'] += validate_time

        # Append survey instructions
        t4 = time.time()
        final_prompt = self._append_survey_instructions(rendered_prompt)
        append_time = time.time() - t4
        _timing_stats['append_time'] += append_time

        total_time = time.time() - build_start
        _timing_stats['total_time'] += total_time
        _timing_stats['call_count'] += 1

        # Print stats every 100 calls
        if _timing_stats['call_count'] % 100 == 0:
            stats = _timing_stats
            print(f"\n[QUESTION_INSTRUCTIONS] Call #{stats['call_count']}")
            print(f"  Total time:       {stats['total_time']:.3f}s")
            print(f"  - Base prompt:    {stats['base_prompt_time']:.3f}s ({100*stats['base_prompt_time']/stats['total_time']:.1f}%)")
            print(f"  - Enrich options: {stats['enrich_time']:.3f}s ({100*stats['enrich_time']/stats['total_time']:.1f}%)")
            print(f"  - Render:         {stats['render_time']:.3f}s ({100*stats['render_time']/stats['total_time']:.1f}%)")
            print(f"    • build_dict:   {stats['render_build_dict']:.3f}s ({100*stats['render_build_dict']/stats['total_time']:.1f}%)")
            print(f"    • prompt.render:{stats['render_prompt_render']:.3f}s ({100*stats['render_prompt_render']/stats['total_time']:.1f}%)")
            print(f"  - Validate:       {stats['validate_time']:.3f}s ({100*stats['validate_time']/stats['total_time']:.1f}%)")
            print(f"  - Append:         {stats['append_time']:.3f}s ({100*stats['append_time']/stats['total_time']:.1f}%)")
            print(f"  Avg per call:     {stats['total_time']/stats['call_count']:.4f}s\n")

        return final_prompt

    def _create_base_prompt(self) -> Dict[str, Union["Prompt", Dict[str, Any]]]:
        """Creates the initial prompt with basic question data.

        The data are, e.g., the question name, question text, question options, etc.

        >>> from edsl import QuestionMultipleChoice
        >>> QuestionMultipleChoice.example().data.copy()
        {'question_name': 'how_feeling', 'question_text': 'How are you?', 'question_options': ['Good', 'Great', 'OK', 'Bad'], 'include_comment': False}

        Returns:
            Dict[str, Union[Prompt, Dict[str, Any]]]: Base question data with prompt and data fields
        """
        from ..prompts import Prompt

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
        if "min_value" in question_data and question_data["min_value"] is not None:
            from .question_numerical_processor import QuestionNumericalProcessor

            question_min_value = QuestionNumericalProcessor(
                scenario, prior_answers_dict
            ).get_question_numerical_value(question_data=question_data, key="min_value")
            question_data["min_value"] = question_min_value
        if "max_value" in question_data and question_data["max_value"] is not None:
            from .question_numerical_processor import QuestionNumericalProcessor

            question_max_value = QuestionNumericalProcessor(
                scenario, prior_answers_dict
            ).get_question_numerical_value(question_data=question_data, key="max_value")
            question_data["max_value"] = question_max_value

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
        prompt_data[
            "data"
        ] = QuestionInstructionPromptBuilder._process_question_options(
            prompt_data["data"], scenario, prior_answers_dict
        )
        return prompt_data

    def _render_prompt(self, prompt_data: Dict) -> "Prompt":
        """Renders the prompt using the replacement dictionary.

        Args:
            prompt_data: Dictionary containing prompt and question data

        Returns:
            Prompt: Rendered instructions
        """
        # Build replacement dict
        t0 = time.time()
        replacement_dict = self.qtrb.build_replacement_dict(prompt_data["data"])
        _timing_stats['render_build_dict'] += (time.time() - t0)

        # Render with dict
        t1 = time.time()
        rendered_prompt = prompt_data["prompt"].render(replacement_dict)
        _timing_stats['render_prompt_render'] += (time.time() - t1)

        # Handle captured variables
        if rendered_prompt.captured_variables:
            self.captured_variables.update(rendered_prompt.captured_variables)

        return rendered_prompt

    def _validate_template_variables(self, rendered_prompt: "Prompt") -> None:
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

    def _append_survey_instructions(self, rendered_prompt: "Prompt") -> "Prompt":
        """Appends any relevant survey instructions to the rendered prompt.

        Args:
            rendered_prompt: The rendered prompt to append instructions to

        Returns:
            Prompt: Final prompt with survey instructions
        """
        from ..prompts import Prompt

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
