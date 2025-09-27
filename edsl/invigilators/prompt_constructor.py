from __future__ import annotations
from typing import Dict, Any, Optional, TYPE_CHECKING, Literal
from functools import cached_property
import logging

from .prompt_helpers import PromptPlan
from .question_template_replacements_builder import (
    QuestionTemplateReplacementsBuilder,
)
from .question_numerical_processor import QuestionNumericalProcessor
from .question_option_processor import QuestionOptionProcessor

if TYPE_CHECKING:
    from .invigilators import InvigilatorBase
    from ..questions import QuestionBase
    from ..agents import Agent
    from ..language_models import LanguageModel
    from ..surveys.memory import MemoryPlan
    from ..scenarios import Scenario
    from ..surveys import Survey
    from ..prompts import Prompt

logger = logging.getLogger(__name__)


class BasePlaceholder:
    """
    Base class for placeholder values used when a question is not yet answered.

    This class provides a mechanism for handling references to previous question
    answers that don't yet exist or are unavailable. It serves as a marker or
    placeholder in prompts and template processing, ensuring that the system can
    gracefully handle dependencies on missing answers.

    Attributes:
        value: The default value to use when the placeholder is accessed directly.
        comment: Description of the placeholder's purpose.
        _type: The type of placeholder (e.g., "answer", "comment").

    Technical Design:
    - Implements __getitem__ to act like an empty collection when indexed
    - Provides clear string representation for debugging and logging
    - Serves as a base for specific placeholder types like PlaceholderAnswer
    - Used during template rendering to handle missing or future answers

    Implementation Notes:
    - This is important for template-based question logic where not all answers
      may be available at template rendering time
    - The system can detect these placeholders and handle them appropriately
      rather than failing when encountering missing answers
    """

    def __init__(self, placeholder_type: str = "answer"):
        """
        Initialize a new BasePlaceholder.

        Args:
            placeholder_type: The type of placeholder (e.g., "answer", "comment").
        """
        self.value = "N/A"
        self.comment = "Will be populated by prior answer"
        self._type = placeholder_type

    def __getitem__(self, index: Any) -> str:
        """
        Allow indexing into the placeholder, always returning an empty string.

        This method makes placeholders act like empty collections when indexed,
        preventing errors when templates try to access specific items.

        Args:
            index: The index being accessed (ignored).

        Returns:
            An empty string.
        """
        return ""

    def __str__(self) -> str:
        """
        Get a string representation of the placeholder for display.

        Returns:
            A string identifying this as a placeholder of a specific type.
        """
        return f"<<{self.__class__.__name__}:{self._type}>>"

    def __repr__(self) -> str:
        """
        Get a string representation for debugging purposes.

        Returns:
            Same string as __str__.
        """
        return self.__str__()


class PlaceholderAnswer(BasePlaceholder):
    def __init__(self):
        super().__init__("answer")


class PlaceholderComment(BasePlaceholder):
    def __init__(self):
        super().__init__("comment")


class PlaceholderGeneratedTokens(BasePlaceholder):
    def __init__(self):
        super().__init__("generated_tokens")


class PromptConstructor:
    """
    Constructs structured prompts for language models based on questions, agents, and context.

    The PromptConstructor is a critical component in the invigilator architecture that
    assembles the various elements needed to form effective prompts for language models.
    It handles the complex task of combining question content, agent characteristics,
    response requirements, and contextual information into coherent prompts that elicit
    well-structured responses.

    Prompt Architecture:
        The constructor builds prompts with several distinct components:

        1. Agent Instructions:
            Core instructions about the agent's role and behavior
            Example: "You are answering questions as if you were a human. Do not break character."

        2. Persona Prompt:
            Details about the agent's characteristics and traits
            Example: "You are an agent with the following persona: {'age': 22, 'hair': 'brown'}"

        3. Question Instructions:
            The question itself with instructions on how to answer
            Example: "You are being asked: Do you like school? The options are 0: yes 1: no
                    Return a valid JSON with your answer code and explanation."

        4. Memory Prompt:
            Information about previous questions and answers in the sequence
            Example: "Before this question, you answered: Question: Do you like school? Answer: Yes"

    Technical Design:
        - Uses a template-based approach for flexibility and consistency
        - Processes question options to present them clearly to the model
        - Handles template variable replacements for scenarios and previous answers
        - Supports both system and user prompts with appropriate content separation
        - Caches computed properties for efficiency

    Implementation Notes:
        - The class performs no direct I/O or model calls
        - It focuses solely on prompt construction, adhering to single responsibility principle
        - Various helper classes handle specialized aspects of prompt construction
        - Extensive use of cached_property for computational efficiency with complex prompts
    """

    @classmethod
    def from_invigilator(
        cls, invigilator: "InvigilatorBase", prompt_plan: Optional["PromptPlan"] = None
    ) -> "PromptConstructor":
        """
        Create a PromptConstructor from an invigilator instance.

        This factory method extracts the necessary components from an invigilator
        and creates a PromptConstructor instance. This is the primary way to create
        a PromptConstructor in the context of administering questions.

        Args:
            invigilator: The invigilator instance containing all necessary components
            prompt_plan: Optional custom prompt plan. If None, uses the invigilator's plan

        Returns:
            A new PromptConstructor instance configured with the invigilator's components

        Technical Notes:
            - This method simplifies the creation of a PromptConstructor with all necessary context
            - It extracts all required components from the invigilator
            - The created PromptConstructor has access to agent, question, scenario, etc.
            - This factory pattern promotes code reuse and maintainability
        """
        return cls(
            agent=invigilator.agent,
            question=invigilator.question,
            scenario=invigilator.scenario,
            survey=invigilator.survey,
            model=invigilator.model,
            current_answers=invigilator.current_answers,
            memory_plan=invigilator.memory_plan,
            prompt_plan=prompt_plan or invigilator.prompt_plan,
        )

    def __init__(
        self,
        agent: "Agent",
        question: "QuestionBase",
        scenario: "Scenario",
        survey: "Survey",
        model: "LanguageModel",
        current_answers: dict,
        memory_plan: "MemoryPlan",
        prompt_plan: Optional["PromptPlan"] = None,
    ):
        """
        Initialize a new PromptConstructor with all necessary components.

        This constructor sets up a prompt constructor with references to all the
        components needed to build effective prompts for language models. It establishes
        the context for constructing prompts that are specific to the given question,
        agent, scenario, and other context.

        Args:
            agent: The agent for which to construct prompts
            question: The question being asked
            scenario: The scenario providing context for the question
            survey: The survey containing the question
            model: The language model that will process the prompts
            current_answers: Dictionary of answers to previous questions
            memory_plan: Plan for managing memory across questions
            prompt_plan: Configuration for how to structure the prompts

        Technical Notes:
            - All components are stored as instance attributes for use in prompt construction
            - The prompt_plan determines which components are included in the prompts and how
            - The captured_variables dictionary is used to store variables extracted during
              template processing
            - This class uses extensive caching via @cached_property to optimize performance
        """
        self.agent = agent
        self.question = question
        self.scenario = scenario
        self.survey = survey
        self.model = model
        self.current_answers = current_answers
        self.memory_plan = memory_plan
        self.prompt_plan = prompt_plan or PromptPlan()

        # Storage for variables captured during template processing
        self.captured_variables = {}

    def get_question_options(self, question_data: dict) -> list[str]:
        """
        Get formatted options for a question based on its data.

        This method delegates to a QuestionOptionProcessor to transform raw question
        option data into a format appropriate for inclusion in prompts. It handles
        various question types and their specific option formatting requirements.

        Args:
            question_data: Dictionary containing the question data, including options

        Returns:
            list[str]: A list of formatted option strings ready for inclusion in prompts

        Examples:
            >>> from edsl.invigilators.invigilators import InvigilatorBase
            >>> i = InvigilatorBase.example()
            >>> question_data = {"question_options": ["yes", "no"]}
            >>> i.prompt_constructor.get_question_options(question_data)
            ['yes', 'no']

            >>> question_data = {"question_options": ["strongly agree", "agree", "disagree"]}
            >>> i.prompt_constructor.get_question_options(question_data)
            ['strongly agree', 'agree', 'disagree']

        Technical Notes:
            - Delegates the actual option processing to the QuestionOptionProcessor
            - The processor has specialized logic for different question types
            - Options are formatted to be clear and unambiguous in prompts
            - This separation of concerns keeps the PromptConstructor focused on
              overall prompt construction rather than option formatting details
        """
        return QuestionOptionProcessor.from_prompt_constructor(
            self
        ).get_question_options(question_data)

    def get_question_numerical_value(
        self, question_data: dict, key: Literal["min_value", "max_value"]
    ) -> int | float | None:
        """
        Get the numerical value for a question based on its data.
        """
        return QuestionNumericalProcessor.from_prompt_constructor(
            self
        ).get_question_numerical_value(question_data, key)

    @cached_property
    def agent_instructions_prompt(self) -> "Prompt":
        """
        Get the agent's core instruction prompt.

        Returns:
            Prompt: A prompt containing the agent's core instructions

        Examples:
            >>> from .invigilators import InvigilatorBase
            >>> i = InvigilatorBase.example()
            >>> i.prompt_constructor.agent_instructions_prompt
            Prompt(text=\"""You are answering questions as if you were a human. Do not break character.\""")
        """
        from ..agents import Agent
        from ..prompts import Prompt

        if self.agent == Agent():  # if agent is empty, then return an empty prompt
            return Prompt(text="")

        return Prompt(text=self.agent.instruction)

    @cached_property
    def agent_persona_prompt(self) -> "Prompt":
        """
        Get the agent's persona characteristics prompt.

        Returns:
            Prompt: A prompt containing the agent's traits and characteristics

        Examples:
            >>> from edsl.invigilators.invigilators import InvigilatorBase
            >>> i = InvigilatorBase.example()
            >>> i.prompt_constructor.agent_persona_prompt
            Prompt(text=\"""Your traits: {'age': 22, 'hair': 'brown', 'height': 5.5}\""")
        """
        from ..agents import Agent
        from ..prompts import Prompt

        if self.agent == Agent():  # if agent is empty, then return an empty prompt
            return Prompt(text="")

        return self.agent.prompt()

    @cached_property
    def prior_answers_dict(self) -> dict[str, "QuestionBase"]:
        """
        Get a dictionary of prior answers if they exist.

        Returns:
            dict[str, QuestionBase]: A dictionary mapping question names to their answered instances

        Examples:
            >>> from edsl.invigilators.invigilators import InvigilatorBase
            >>> i = InvigilatorBase.example()
            >>> i.prompt_constructor.prior_answers_dict
            {'q0': ..., 'q1': ...}
        """
        return self._add_answers(
            self.survey.question_names_to_questions, self.current_answers
        )

    @staticmethod
    def _extract_question_and_entry_type(key_entry: str) -> tuple[str, str]:
        """
        Extract the question name and type from a dictionary key entry.

        Args:
            key_entry: The key from the answers dictionary to parse

        Returns:
            tuple[str, str]: A tuple of (question_name, entry_type)

        Examples:
            >>> PromptConstructor._extract_question_and_entry_type("q0")
            ('q0', 'answer')
            >>> PromptConstructor._extract_question_and_entry_type("q0_comment")
            ('q0', 'comment')
            >>> PromptConstructor._extract_question_and_entry_type("q0_alternate_generated_tokens")
            ('q0_alternate', 'generated_tokens')
            >>> PromptConstructor._extract_question_and_entry_type("q0_alt_comment")
            ('q0_alt', 'comment')
        """
        split_list = key_entry.rsplit("_", maxsplit=1)
        if len(split_list) == 1:
            question_name = split_list[0]
            entry_type = "answer"
        else:
            if split_list[1] == "comment":
                question_name = split_list[0]
                entry_type = "comment"
            elif split_list[1] == "tokens":  # it's actually 'generated_tokens'
                question_name = key_entry.replace("_generated_tokens", "")
                entry_type = "generated_tokens"
            else:
                question_name = key_entry
                entry_type = "answer"
        return question_name, entry_type

    @staticmethod
    def _augmented_answers_dict(current_answers: dict) -> dict:
        """
        Create a nested dictionary of current answers organized by question.

        Creates a dictionary where each question's answers, comments, and generated tokens
        are grouped together in a sub-dictionary.

        Args:
            current_answers: The flat dictionary of current answers

        Returns:
            dict: A nested dictionary with answers organized by question

        Examples:
            >>> PromptConstructor._augmented_answers_dict({"q0": "LOVE IT!", "q0_comment": "I love school!"})
            {'q0': {'answer': 'LOVE IT!', 'comment': 'I love school!'}}
        """
        from collections import defaultdict

        d = defaultdict(dict)
        for key, value in current_answers.items():
            (
                question_name,
                entry_type,
            ) = PromptConstructor._extract_question_and_entry_type(key)
            d[question_name][entry_type] = value
        return dict(d)

    @staticmethod
    def _add_answers(
        answer_dict: dict, current_answers: dict
    ) -> dict[str, "QuestionBase"]:
        """
        Add current answers to the answer dictionary, handling missing answers with placeholders.

        Args:
            answer_dict: The base dictionary of questions
            current_answers: The dictionary of current answers to add

        Returns:
            dict[str, QuestionBase]: The updated dictionary with answers added

        Examples:
            >>> from edsl import QuestionFreeText
            >>> d = {"q0": QuestionFreeText(question_text="Do you like school?", question_name = "q0")}
            >>> current_answers = {"q0": "LOVE IT!"}
            >>> PromptConstructor._add_answers(d, current_answers)['q0'].answer
            'LOVE IT!'
        """
        augmented_answers = PromptConstructor._augmented_answers_dict(current_answers)

        for question in answer_dict:
            if question in augmented_answers:
                for entry_type, value in augmented_answers[question].items():
                    setattr(answer_dict[question], entry_type, value)
            else:
                answer_dict[question].answer = PlaceholderAnswer()
                answer_dict[question].comment = PlaceholderComment()
                answer_dict[question].generated_tokens = PlaceholderGeneratedTokens()
        return answer_dict

    @cached_property
    def file_keys_from_question(self) -> list:
        """
        Extract file keys referenced in the question text.

        Checks if variables in the question text correspond to scenario file keys.

        Returns:
            list: A list of file keys found in the question text
        """
        import time

        start_total = time.time()

        start_builder = time.time()
        builder = QuestionTemplateReplacementsBuilder.from_prompt_constructor(self)
        builder_time = time.time() - start_builder

        start_keys = time.time()
        result = builder.question_file_keys()
        keys_time = time.time() - start_keys

        total_time = time.time() - start_total

        return result

    @cached_property
    def question_instructions_prompt(self) -> "Prompt":
        """
        >>> from edsl.invigilators.invigilators import InvigilatorBase
        >>> i = InvigilatorBase.example()
        >>> i.prompt_constructor.question_instructions_prompt
        Prompt(text=\"""...
        ...
        """
        return self.build_question_instructions_prompt()

    def build_question_instructions_prompt(self) -> "Prompt":
        """
        Builds the question instructions prompt by combining question text, options, and formatting.

        This method uses the QuestionInstructionPromptBuilder to construct a complete
        prompt that includes the question text, available options, and any necessary
        formatting or additional instructions for the model.

        Returns:
            Prompt: A Prompt object containing the fully constructed question instructions

        Examples:
            >>> from edsl.invigilators.invigilators import InvigilatorBase
            >>> i = InvigilatorBase.example()
            >>> i.question.use_code = True
            >>> prompt = i.prompt_constructor.build_question_instructions_prompt()
            >>> "Do you like school?" in prompt.text
            True
            >>> "0: yes" in prompt.text
            True
            >>> "1: no" in prompt.text
            True

        Technical Notes:
            - Uses QuestionInstructionPromptBuilder for consistent prompt formatting
            - Captures any variables set during prompt construction
            - Updates the captured_variables dictionary with any new variables
            - Returns a complete Prompt object ready for rendering
        """
        import time

        start_total = time.time()

        from .question_instructions_prompt_builder import (
            QuestionInstructionPromptBuilder,
        )

        start_create = time.time()
        qipb = QuestionInstructionPromptBuilder.from_prompt_constructor(self)
        create_time = time.time() - start_create

        start_build = time.time()
        prompt = qipb.build()
        build_time = time.time() - start_build

        start_capture = time.time()
        if prompt.captured_variables:
            self.captured_variables.update(prompt.captured_variables)
        capture_time = time.time() - start_capture

        total_time = time.time() - start_total

        return prompt

    @cached_property
    def prior_question_memory_prompt(self) -> "Prompt":
        """
        Get the prompt containing memory of prior questions and answers.

        Returns:
            Prompt: A prompt containing the relevant prior question memory
        """
        import time

        start_total = time.time()

        from ..prompts import Prompt

        # OPTIMIZATION: Skip memory processing during cost estimation
        # Since we don't have real answers yet, processing prior memory is pointless
        try:
            from ..jobs.jobs_pricing_estimation import is_cost_estimation

            if is_cost_estimation():
                return Prompt(text="")
        except ImportError:
            # Fallback if import fails
            pass

        memory_prompt = Prompt(text="")
        if self.memory_plan is not None:
            start_memory = time.time()
            memory_creation = self.create_memory_prompt(self.question.question_name)
            memory_creation_time = time.time() - start_memory

            start_render = time.time()
            # OPTIMIZATION: Only pass scenario files that are actually referenced in the memory template
            memory_template_variables = (
                QuestionTemplateReplacementsBuilder.get_jinja2_variables(
                    memory_creation.text
                )
            )
            scenario_file_keys = [
                key
                for key, value in self.scenario.items()
                if hasattr(value, "__class__") and "FileStore" in str(value.__class__)
            ]

            # Find which scenario files are actually referenced in the memory template
            referenced_file_keys = []
            for var in memory_template_variables:
                if var in scenario_file_keys:
                    referenced_file_keys.append(var)
                elif var == "scenario":
                    # Check for scenario.file_key patterns
                    import re

                    scenario_refs = re.findall(
                        r"{{\\s*scenario\\.(\\w+)\\s*}}", memory_creation.text
                    )
                    for key in scenario_refs:
                        if key in scenario_file_keys:
                            referenced_file_keys.append(key)

            # Only include referenced files and all non-file scenario items
            optimized_scenario = {
                k: v
                for k, v in self.scenario.items()
                if k not in scenario_file_keys or k in referenced_file_keys
            }

            rendered_memory = memory_creation.render(
                optimized_scenario | self.prior_answers_dict
            )
            render_time = time.time() - start_render

            memory_prompt += rendered_memory

            total_time = time.time() - start_total
        else:
            total_time = time.time() - start_total

        return memory_prompt

    def create_memory_prompt(self, question_name: str) -> "Prompt":
        """
        Create a memory prompt containing previous question answers for the agent.

        Args:
            question_name: The name of the current question

        Returns:
            Prompt: A memory prompt containing relevant prior answers

        Examples:
            >>> from edsl.invigilators.invigilators import InvigilatorBase
            >>> i = InvigilatorBase.example()
            >>> i.current_answers = {"q0": "Prior answer"}
            >>> i.memory_plan.add_single_memory("q1", "q0")
            >>> p = i.prompt_constructor.create_memory_prompt("q1")
            >>> p.text.strip().replace("\\n", " ").replace("\\t", " ")
            'Before the question you are now answering, you already answered the following question(s):          Question: Do you like school?  Answer: Prior answer'
        """
        return self.memory_plan.get_memory_prompt_fragment(
            question_name, self.current_answers
        )

    def get_prompts(self) -> Dict[str, Any]:
        """
        Get all prompts needed for the question, properly formatted and organized.

        This method assembles all the different components of the prompt system:
        - Agent instructions
        - Agent persona
        - Question instructions
        - Prior question memory
        And combines them according to the prompt plan's specifications.

        Returns:
            Dict[str, Any]: A dictionary containing the formatted prompts and any associated files.
            The dictionary typically includes:
                - 'system_prompt': Instructions for the model's behavior
                - 'user_prompt': The actual question and context
                - 'files_list': Any relevant files (if file keys are present)

        Examples:
            >>> from edsl.invigilators.invigilators import InvigilatorBase
            >>> i = InvigilatorBase.example()
            >>> prompts = i.prompt_constructor.get_prompts()
            >>> "Do not break character" in prompts['system_prompt']
            True
            >>> "Do you like school?" in prompts['user_prompt']
            True

            # Test with file keys requires FileStore objects
            >>> from edsl.scenarios import FileStore
            >>> import tempfile
            >>> with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            ...     _ = f.write('print("Hello")')
            ...     temp_path = f.name
            >>> fs = FileStore(temp_path)
            >>> from edsl.questions import QuestionFreeText
            >>> from edsl import Scenario, Survey
            >>> q_with_file = QuestionFreeText(question_text='Analyze: {{ code_file }}', question_name='q1')
            >>> scenario_with_file = Scenario({'code_file': fs})
            >>> survey_with_file = Survey([q_with_file])
            >>> i_with_file = InvigilatorBase.example(question=q_with_file, scenario=scenario_with_file, survey=survey_with_file)
            >>> prompts_with_file = i_with_file.prompt_constructor.get_prompts()
            >>> 'files_list' in prompts_with_file
            True

        Technical Notes:
            - Builds all prompt components first
            - Uses the prompt plan to organize components
            - Handles file attachments if specified in the question
            - Returns a complete dictionary ready for use with the language model
        """
        import time

        start_total = time.time()

        # Build all the components
        start_agent_instr = time.time()
        agent_instructions = self.agent_instructions_prompt
        agent_instr_time = time.time() - start_agent_instr

        start_agent_persona = time.time()
        agent_persona = self.agent_persona_prompt
        agent_persona_time = time.time() - start_agent_persona

        start_question_instr = time.time()
        question_instructions = self.question_instructions_prompt
        question_instr_time = time.time() - start_question_instr

        start_prior_memory = time.time()
        prior_question_memory = self.prior_question_memory_prompt
        prior_memory_time = time.time() - start_prior_memory

        # Get components dict
        start_components = time.time()
        components = {
            "agent_instructions": agent_instructions.text,
            "agent_persona": agent_persona.text,
            "question_instructions": question_instructions.text,
            "prior_question_memory": prior_question_memory.text,
        }
        components_time = time.time() - start_components

        start_prompt_plan = time.time()
        prompts = self.prompt_plan.get_prompts(**components)
        prompt_plan_time = time.time() - start_prompt_plan

        # Handle file keys if present
        start_file_keys = time.time()
        file_keys = self.file_keys_from_question
        if file_keys:
            files_list = []
            for key in file_keys:
                files_list.append(self.scenario[key])
            prompts["files_list"] = files_list
        file_keys_time = time.time() - start_file_keys

        total_time = time.time() - start_total

        return prompts

    def get_captured_variables(self) -> dict:
        """
        Get all variables that were captured during prompt construction and rendering.

        This method returns any variables that were set during the template rendering
        process. These variables can be used for tracking state, storing intermediate
        values, or capturing information about the prompt construction process.

        Returns:
            dict: A dictionary containing all captured variables and their values

        Examples:
            >>> from edsl.invigilators.invigilators import InvigilatorBase
            >>> i = InvigilatorBase.example()
            >>> pc = i.prompt_constructor
            >>> pc.captured_variables = {'answer_count': 5, 'last_response': 'yes'}
            >>> vars = pc.get_captured_variables()
            >>> vars['answer_count']
            5
            >>> vars['last_response']
            'yes'

        Technical Notes:
            - Variables are captured during template rendering
            - The dictionary is updated throughout the prompt construction process
            - Useful for debugging and tracking template variable usage
            - Can be used to pass information between different parts of the system
        """
        return self.captured_variables


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
