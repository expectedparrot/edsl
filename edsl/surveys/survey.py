"""A Survey is a collection of questions that can be administered to an Agent or a Human.

This module defines the Survey class, which is the central data structure for creating
and managing surveys. A Survey consists of questions, instructions, and rules that
determine the flow of questions based on previous answers.

Surveys can include skip logic, memory management, and question groups, making them
flexible for a variety of use cases from simple linear questionnaires to complex
branching surveys with conditional logic.
"""

from __future__ import annotations
import re
import random
from collections import UserDict
from uuid import uuid4

from typing import (
    Any,
    Generator,
    Optional,
    Union,
    List,
    Callable,
    TYPE_CHECKING,
    Dict,
    Tuple,
)
from typing_extensions import Literal
from ..base import Base
from ..scenarios import Scenario
from ..utilities import remove_edsl_version

if TYPE_CHECKING:
    from ..questions import QuestionBase
    from ..agents import Agent, AgentList
    from .dag import DAG
    from ..language_models import LanguageModel, ModelList
    from ..caching import Cache
    from ..jobs import Jobs
    from ..results import Results, Result
    from ..scenarios import ScenarioList
    from ..buckets.bucket_collection import BucketCollection
    from ..key_management.key_lookup import KeyLookup
    from ..scenarios import FileStore

    # Define types for documentation purpose only
    VisibilityType = Literal["unlisted", "public", "private"]
    Table = Any  # Type for table display
    # Type alias for docx document
    Document = Any

    QuestionType = Union[QuestionBase, "Instruction", "ChangeInstruction"]
    QuestionGroupType = Dict[str, Tuple[int, int]]


from ..instructions import InstructionCollection
from ..instructions import Instruction
from ..instructions import ChangeInstruction

from .base import EndOfSurvey, EndOfSurveyParent
from .descriptors import QuestionsDescriptor
from .memory import MemoryPlan
from .survey_flow_visualization import SurveyFlowVisualization
from ..instructions import InstructionHandler
from .edit_survey import EditSurvey
from .survey_simulator import Simulator
from .memory import MemoryManagement
from .rules import RuleManager, RuleCollection
from .survey_export import SurveyExport
from .exceptions import SurveyCreationError, SurveyHasNoRulesError, SurveyError


class PseudoIndices(UserDict):
    """A dictionary of pseudo-indices for the survey.

    This class manages indices for both questions and instructions in a survey. It assigns
    floating-point indices to instructions so they can be interspersed between integer-indexed
    questions while maintaining order. This is crucial for properly serializing and deserializing
    surveys with both questions and instructions.

    Attributes:
        data (dict): The underlying dictionary mapping item names to their pseudo-indices.
    """

    @property
    def max_pseudo_index(self) -> float:
        """Return the maximum pseudo index in the survey.

        Returns:
            float: The highest pseudo-index value currently assigned, or -1 if empty.

        Examples:
            >>> Survey.example()._pseudo_indices.max_pseudo_index
            2
        """
        if len(self) == 0:
            return -1
        return max(self.values())

    @property
    def last_item_was_instruction(self) -> bool:
        """Determine if the last item added to the survey was an instruction.

        This is used to determine the pseudo-index of the next item added to the survey.
        Instructions are assigned floating-point indices (e.g., 1.5) while questions
        have integer indices.

        Returns:
            bool: True if the last added item was an instruction, False otherwise.

        Examples:
            >>> s = Survey.example()
            >>> s._pseudo_indices.last_item_was_instruction
            False
            >>> from edsl.instructions import Instruction
            >>> s = s.add_instruction(Instruction(text="Pay attention to the following questions.", name="intro"))
            >>> s._pseudo_indices.last_item_was_instruction
            True
        """
        return isinstance(self.max_pseudo_index, float)


class Survey(Base):
    """A collection of questions with logic for navigating between them.

    Survey is the main class for creating, modifying, and running surveys. It supports:

    - Skip logic: conditional navigation between questions based on previous answers
    - Memory: controlling which previous answers are visible to agents
    - Question grouping: organizing questions into logical sections
    - Randomization: randomly ordering certain questions to reduce bias
    - Instructions: adding non-question elements to guide respondents

    A Survey instance can be used to:
    1. Define a set of questions and their order
    2. Add rules for navigating between questions
    3. Run the survey with agents or humans
    4. Export the survey in various formats

    The survey maintains the order of questions, any skip logic rules, and handles
    serialization for storage or transmission.
    """

    __documentation__ = """https://docs.expectedparrot.com/en/latest/surveys.html"""

    questions = QuestionsDescriptor()
    """A descriptor that manages the list of questions in the survey.
    
    This descriptor handles the setting and getting of questions, ensuring
    proper validation and maintaining internal data structures. It manages
    both direct question objects and their names.
    
    The underlying questions are stored in the protected `_questions` attribute,
    while this property provides the public interface for accessing them.
    
    Notes:
        - The presumed order of the survey is the order in which questions are added
        - Questions must have unique names within a survey
        - Each question can have rules associated with it that determine the next question
    """

    def __init__(
        self,
        questions: Optional[List["QuestionType"]] = None,
        memory_plan: Optional["MemoryPlan"] = None,
        rule_collection: Optional["RuleCollection"] = None,
        question_groups: Optional["QuestionGroupType"] = None,
        name: Optional[str] = None,
        questions_to_randomize: Optional[List[str]] = None,
    ):
        """Initialize a new Survey instance.

        This constructor sets up a new survey with the provided questions and optional
        configuration for memory, rules, grouping, and randomization.

        Args:
            questions: A list of question objects to include in the survey.
                Can include QuestionBase objects, Instructions, and ChangeInstructions.
            memory_plan: Defines which previous questions and answers are available
                when answering each question. If None, a default plan is created.
            rule_collection: Contains rules for determining which question comes next
                based on previous answers. If None, default sequential rules are created.
            question_groups: A dictionary mapping group names to (start_idx, end_idx)
                tuples that define groups of questions.
            name: DEPRECATED. The name of the survey.
            questions_to_randomize: A list of question names to randomize when the
                survey is drawn. This affects the order of options in these questions.

        Examples:
            Create a basic survey with three questions:

            >>> from edsl import QuestionFreeText
            >>> q1 = QuestionFreeText(question_text="What is your name?", question_name="name")
            >>> q2 = QuestionFreeText(question_text="What is your favorite color?", question_name="color")
            >>> q3 = QuestionFreeText(question_text="Is a hot dog a sandwich?", question_name="food")
            >>> s = Survey([q1, q2, q3])

            Create a survey with question groups:

            >>> s = Survey([q1, q2, q3], question_groups={"demographics": (0, 1), "food_questions": (2, 2)})
        """

        self.raw_passed_questions = questions

        true_questions = self._process_raw_questions(self.raw_passed_questions)

        self.rule_collection = RuleCollection(
            num_questions=len(true_questions) if true_questions else None
        )
        # the RuleCollection needs to be present while we add the questions; we might override this later
        # if a rule_collection is provided. This allows us to serialize the survey with the rule_collection.

        # this is where the Questions constructor is called.
        self.questions = true_questions
        # self.instruction_names_to_instructions = instruction_names_to_instructions

        self.memory_plan = memory_plan or MemoryPlan(self)
        if question_groups is not None:
            self.question_groups = question_groups
        else:
            self.question_groups = {}

        # if a rule collection is provided, use it instead of the constructed one
        if rule_collection is not None:
            self.rule_collection = rule_collection

        # if name is not None:
        #     import warnings

        #     warnings.warn("name parameter to a survey is deprecated.")
        self.name = name

        if questions_to_randomize is not None:
            self.questions_to_randomize = questions_to_randomize
        else:
            self.questions_to_randomize = []

        self._seed: Optional[int] = None

        # Cache the InstructionCollection
        self._cached_instruction_collection: Optional[InstructionCollection] = None

        self._exporter = SurveyExport(self)

    def clipboard_data(self):
        """Return the clipboard data for the survey."""
        text = []
        for question in self.questions:
            text.append(question.human_readable())
        return "\n\n".join(text)

    @classmethod
    def auto_survey(
        cls, overall_question: str, population: str, num_questions: int
    ) -> Survey:
        """Create a survey with a single question that asks the user how they are doing."""
        from edsl import ext

        survey_info = ext.create_survey(
            overall_question=overall_question,
            population=population,
            num_questions=num_questions,
        )
        return survey_info["survey"]

    def generate_description(self) -> str:
        """Generate a description of the survey."""
        from ..questions import QuestionFreeText

        question_texts = [q.question_text for q in self.questions]
        q = QuestionFreeText(
            question_text=f"What is a good one sentence description of this survey? The questions are: {question_texts}",
            question_name="description",
        )
        results = q.run(verbose=False)
        return results.select("answer.description").first()

    def question_names_valid(self) -> bool:
        """Check if the question names are valid."""
        return all(q.is_valid_question_name() for q in self.questions)

    def question_to_attributes(self) -> dict:
        """Return a dictionary of question attributes.

        >>> s = Survey.example()
        >>> s.question_to_attributes()
        {'q0': {'question_text': 'Do you like school?', 'question_type': 'multiple_choice', 'question_options': ['yes', 'no']}, 'q1': {'question_text': 'Why not?', 'question_type': 'multiple_choice', 'question_options': ['killer bees in cafeteria', 'other']}, 'q2': {'question_text': 'Why?', 'question_type': 'multiple_choice', 'question_options': ['**lack*** of killer bees in cafeteria', 'other']}}
        """
        return {
            q.question_name: {
                "question_text": q.question_text,
                "question_type": q.question_type,
                "question_options": (
                    None if not hasattr(q, "question_options") else q.question_options
                ),
            }
            for q in self.questions
        }

    def draw(self) -> "Survey":
        """Return a new survey with a randomly selected permutation of the options."""
        if self._seed is None:  # only set once
            self._seed = hash(self)
            random.seed(self._seed)  # type: ignore

        # Always create new questions to avoid sharing state between interviews
        new_questions = []
        for question in self.questions:
            if question.question_name in self.questions_to_randomize:
                new_questions.append(question.draw())
            else:
                new_questions.append(question.duplicate())

        d = self.to_dict()
        d["questions"] = [q.to_dict() for q in new_questions]
        new_survey = Survey.from_dict(d)
        # Preserve any non-serialized attributes from the new_questions
        for i, new_question in enumerate(new_questions):
            survey_question = new_survey.questions[i]
            if hasattr(new_question, 'exception_to_throw'):
                survey_question.exception_to_throw = new_question.exception_to_throw
            if hasattr(new_question, 'override_answer'):
                survey_question.override_answer = new_question.override_answer
        return new_survey

    def _process_raw_questions(self, questions: Optional[List["QuestionType"]]) -> list:
        """Process the raw questions passed to the survey."""
        handler = InstructionHandler(self)
        result = handler.separate_questions_and_instructions(questions or [])

        # Handle result safely for mypy
        if (
            hasattr(result, "true_questions")
            and hasattr(result, "instruction_names_to_instructions")
            and hasattr(result, "pseudo_indices")
        ):
            # It's the SeparatedComponents dataclass
            self._instruction_names_to_instructions = result.instruction_names_to_instructions  # type: ignore
            self._pseudo_indices = PseudoIndices(result.pseudo_indices)  # type: ignore
            return result.true_questions  # type: ignore
        else:
            # For older versions that return a tuple
            # This is a hacky way to get mypy to allow tuple unpacking of an Any type
            result_list = list(result)  # type: ignore
            if len(result_list) == 3:
                true_q = result_list[0]
                inst_dict = result_list[1]
                pseudo_idx = result_list[2]
                self._instruction_names_to_instructions = inst_dict
                self._pseudo_indices = PseudoIndices(pseudo_idx)
                return true_q
            else:
                raise TypeError(
                    f"Unexpected result type from separate_questions_and_instructions: {type(result)}"
                )

    @property
    def _relevant_instructions_dict(self) -> InstructionCollection:
        """Return a dictionary with keys as question names and values as instructions that are relevant to the question."""
        if self._cached_instruction_collection is None:
            self._cached_instruction_collection = InstructionCollection(
                self._instruction_names_to_instructions, self.questions
            )
        return self._cached_instruction_collection

    def _relevant_instructions(self, question: QuestionBase) -> dict:
        """Return instructions that are relevant to the question."""
        return self._relevant_instructions_dict[question]

    def show_flow(self, filename: Optional[str] = None) -> None:
        """Show the flow of the survey."""
        SurveyFlowVisualization(self).show_flow(filename=filename)

    def add_instruction(
        self, instruction: Union["Instruction", "ChangeInstruction"]
    ) -> Survey:
        """
        Add an instruction to the survey.

        :param instruction: The instruction to add to the survey.

        >>> from edsl import Instruction
        >>> i = Instruction(text="Pay attention to the following questions.", name="intro")
        >>> s = Survey().add_instruction(i)
        >>> s._instruction_names_to_instructions
        {'intro': Instruction(name="intro", text="Pay attention to the following questions.")}
        >>> s._pseudo_indices
        {'intro': -0.5}
        """
        return EditSurvey(self).add_instruction(instruction)

    @classmethod
    def random_survey(cls):
        return Simulator.random_survey()

    def simulate(self) -> dict:
        """Simulate the survey and return the answers."""
        return Simulator(self).simulate()

    def _get_question_index(
        self, q: Union["QuestionBase", str, EndOfSurveyParent]
    ) -> Union[int, EndOfSurveyParent]:
        """Return the index of the question or EndOfSurvey object.

        :param q: The question or question name to get the index of.

        It can handle it if the user passes in the question name, the question object, or the EndOfSurvey object.

        >>> s = Survey.example()
        >>> s._get_question_index("q0")
        0

        This doesnt' work with questions that don't exist:

        # Example with a non-existent question name would raise SurveyError
        """
        if q is EndOfSurvey:
            return EndOfSurvey
        else:
            if isinstance(q, str):
                question_name = q
            elif isinstance(q, EndOfSurveyParent):
                return EndOfSurvey
            else:
                question_name = q.question_name
            if question_name not in self.question_name_to_index:
                raise SurveyError(
                    f"""Question name {question_name} not found in survey. The current question names are {self.question_name_to_index}."""
                )
            return self.question_name_to_index[question_name]

    def _get_question_by_name(self, question_name: str) -> QuestionBase:
        """Return the question object given the question name.

        :param question_name: The name of the question to get.

        >>> s = Survey.example()
        >>> s._get_question_by_name("q0")
        Question('multiple_choice', question_name = \"""q0\""", question_text = \"""Do you like school?\""", question_options = ['yes', 'no'])
        """
        if question_name not in self.question_name_to_index:
            raise SurveyError(f"Question name {question_name} not found in survey.")
        return self.questions[self.question_name_to_index[question_name]]

    def get(self, question_name: str) -> QuestionBase:
        """Return the question object given the question name."""
        return self._get_question_by_name(question_name)

    def question_names_to_questions(self) -> dict:
        """Return a dictionary mapping question names to question attributes."""
        return {q.question_name: q.duplicate() for q in self.questions}
        #return {q.question_name: q for q in self.questions}

    @property
    def question_names(self) -> list[str]:
        """Return a list of question names in the survey.

        Example:

        >>> s = Survey.example()
        >>> s.question_names
        ['q0', 'q1', 'q2']
        """
        return [q.question_name for q in self.questions]

    @property
    def question_name_to_index(self) -> dict[str, int]:
        """Return a dictionary mapping question names to question indices.

        Example:

        >>> s = Survey.example()
        >>> s.question_name_to_index
        {'q0': 0, 'q1': 1, 'q2': 2}
        """
        return {q.question_name: i for i, q in enumerate(self.questions)}

    def to_long_format(
        self, scenario_list: 'ScenarioList'
    ) -> Tuple[List[QuestionBase], ScenarioList]:
        """Return a new survey with the questions in long format and the associated scenario list."""

        from ..questions.loop_processor import LongSurveyLoopProcessor

        lp = LongSurveyLoopProcessor(self, scenario_list)
        return lp.process_templates_for_all_questions()

    def to_dict(self, add_edsl_version:bool=True) -> dict[str, Any]:
        """Serialize the Survey object to a dictionary for storage or transmission.

        This method converts the entire survey structure, including questions, rules,
        memory plan, and question groups, into a dictionary that can be serialized to JSON.
        This is essential for saving surveys, sharing them, or transferring them between
        systems.

        The serialized dictionary contains the complete state of the survey, allowing it
        to be fully reconstructed using the from_dict() method.

        Args:
            add_edsl_version: If True (default), includes the EDSL version and class name
                in the dictionary, which can be useful for backward compatibility when
                deserializing.

        Returns:
            dict[str, Any]: A dictionary representation of the survey with the following keys:
                - 'questions': List of serialized questions and instructions
                - 'memory_plan': Serialized memory plan
                - 'rule_collection': Serialized rule collection
                - 'question_groups': Dictionary of question groups
                - 'questions_to_randomize': List of questions to randomize (if any)
                - 'edsl_version': EDSL version (if add_edsl_version=True)
                - 'edsl_class_name': Class name (if add_edsl_version=True)

        Examples:
            >>> s = Survey.example()
            >>> s.to_dict(add_edsl_version=False).keys()
            dict_keys(['questions', 'memory_plan', 'rule_collection', 'question_groups'])

            With version information:

            >>> d = s.to_dict(add_edsl_version=True)
            >>> 'edsl_version' in d and 'edsl_class_name' in d
            True
        """
        from edsl import __version__

        # Create the base dictionary with all survey components
        d = {
            "questions": [
                q.to_dict(add_edsl_version=add_edsl_version)
                for q in self._recombined_questions_and_instructions()
            ],
            "memory_plan": self.memory_plan.to_dict(add_edsl_version=add_edsl_version),
            "rule_collection": self.rule_collection.to_dict(
                add_edsl_version=add_edsl_version
            ),
            "question_groups": self.question_groups,
        }
        if self.name is not None:
            d["name"] = self.name

        # Include randomization information if present
        if self.questions_to_randomize != []:
            d["questions_to_randomize"] = self.questions_to_randomize

        # Add version information if requested
        if add_edsl_version:
            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Survey"

        return d

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict) -> Survey:
        """Reconstruct a Survey object from its dictionary representation.

        This class method is the counterpart to to_dict() and allows you to recreate
        a Survey object from a serialized dictionary. This is useful for loading saved
        surveys, receiving surveys from other systems, or cloning surveys.

        The method handles deserialization of all survey components, including questions,
        instructions, memory plan, rules, and question groups.

        Args:
            data: A dictionary containing the serialized survey data, typically
                created by the to_dict() method.

        Returns:
            Survey: A fully reconstructed Survey object with all the original
                questions, rules, and configuration.

        Examples:
            Create a survey, serialize it, and deserialize it back:

            >>> d = Survey.example().to_dict()
            >>> s = Survey.from_dict(d)
            >>> s == Survey.example()
            True

            Works with instructions as well:

            >>> s = Survey.example(include_instructions=True)
            >>> d = s.to_dict()
            >>> news = Survey.from_dict(d)
            >>> news == s
            True
        """

        # Helper function to determine the correct class for each serialized component
        def get_class(pass_dict):
            from ..questions import QuestionBase

            if (class_name := pass_dict.get("edsl_class_name")) == "QuestionBase":
                return QuestionBase
            elif pass_dict.get("edsl_class_name") == "QuestionDict":
                from ..questions import QuestionDict

                return QuestionDict
            elif class_name == "Instruction":
                from ..instructions import Instruction

                return Instruction
            elif class_name == "ChangeInstruction":
                from ..instructions import ChangeInstruction

                return ChangeInstruction
            else:
                return QuestionBase

        # Deserialize each question and instruction
        questions = [
            get_class(q_dict).from_dict(q_dict) for q_dict in data["questions"]
        ]

        # Deserialize the memory plan
        memory_plan = MemoryPlan.from_dict(data["memory_plan"])

        # Get the list of questions to randomize if present
        if "questions_to_randomize" in data:
            questions_to_randomize = data["questions_to_randomize"]
        else:
            questions_to_randomize = None

        if "name" in data:
            name = data["name"]
        else:
            name = None

        # Create and return the reconstructed survey
        survey = cls(
            questions=questions,
            memory_plan=memory_plan,
            rule_collection=RuleCollection.from_dict(data["rule_collection"]),
            question_groups=data["question_groups"],
            questions_to_randomize=questions_to_randomize,
            name=name,
        )
        return survey

    @property
    def scenario_attributes(self) -> list[str]:
        """Return a list of attributes that admissible Scenarios should have.

        Here we have a survey with a question that uses a jinja2 style {{ }} template:

        >>> from edsl import QuestionFreeText
        >>> s = Survey().add_question(QuestionFreeText(question_text="{{ greeting }}. What is your name?", question_name="name"))
        >>> s.scenario_attributes
        ['greeting']

        >>> s = Survey().add_question(QuestionFreeText(question_text="{{ greeting }}. What is your {{ attribute }}?", question_name="name"))
        >>> s.scenario_attributes
        ['greeting', 'attribute']


        """
        temp = []
        for question in self.questions:
            question_text = question.question_text
            # extract the contents of all {{ }} in the question text using regex
            matches = re.findall(r"\{\{(.+?)\}\}", question_text)
            # remove whitespace
            matches = [match.strip() for match in matches]
            # add them to the temp list
            temp.extend(matches)
        return temp

    @property
    def parameters(self) -> set:
        """Return a set of parameters in the survey.

        >>> s = Survey.example()
        >>> s.parameters
        set()
        """
        return set.union(*[q.parameters for q in self.questions])

    @property
    def parameters_by_question(self) -> dict[str, set]:
        """Return a dictionary of parameters by question in the survey.
        >>> from edsl import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "example", question_text = "What is the capital of {{ country}}?")
        >>> s = Survey([q])
        >>> s.parameters_by_question
        {'example': {'country'}}
        """
        return {q.question_name: q.parameters for q in self.questions}

    def __add__(self, other: Survey) -> Survey:
        """Combine two surveys.

        :param other: The other survey to combine with this one.
        >>> s1 = Survey.example()
        >>> from edsl import QuestionFreeText
        >>> s2 = Survey([QuestionFreeText(question_text="What is your name?", question_name="yo")])
        >>> s3 = s1.clear_non_default_rules() + s2
        >>> len(s3.questions)
        4

        """
        if (
            len(self.rule_collection.non_default_rules) > 0
            or len(other.rule_collection.non_default_rules) > 0
        ):
            raise SurveyCreationError(
                "Cannot combine two surveys with non-default rules. Please use the 'clear_non_default_rules' method to remove non-default rules from the survey.",
            )

        return Survey(questions=self.questions + other.questions)

    def move_question(self, identifier: Union[str, int], new_index: int) -> Survey:
        """
        >>> from edsl import QuestionMultipleChoice, Survey
        >>> s = Survey.example()
        >>> s.question_names
        ['q0', 'q1', 'q2']
        >>> s.move_question("q0", 2).question_names
        ['q1', 'q2', 'q0']
        """
        return EditSurvey(self).move_question(identifier, new_index)

    def delete_question(self, identifier: Union[str, int]) -> Survey:
        """
        Delete a question from the survey.

        :param identifier: The name or index of the question to delete.
        :return: The updated Survey object.

        >>> from edsl import QuestionMultipleChoice, Survey
        >>> q1 = QuestionMultipleChoice(question_text="Q1", question_options=["A", "B"], question_name="q1")
        >>> q2 = QuestionMultipleChoice(question_text="Q2", question_options=["C", "D"], question_name="q2")
        >>> s = Survey().add_question(q1).add_question(q2)
        >>> _ = s.delete_question("q1")
        >>> len(s.questions)
        1
        >>> _ = s.delete_question(0)
        >>> len(s.questions)
        0
        """
        return EditSurvey(self).delete_question(identifier)

    def add_question(
        self, question: QuestionBase, index: Optional[int] = None
    ) -> Survey:
        """
        Add a question to survey.

        :param question: The question to add to the survey.
        :param question_name: The name of the question. If not provided, the question name is used.

        The question is appended at the end of the self.questions list
        A default rule is created that the next index is the next question.

        >>> from edsl import QuestionMultipleChoice
        >>> q = QuestionMultipleChoice(question_text = "Do you like school?", question_options=["yes", "no"], question_name="q0")
        >>> s = Survey().add_question(q)

        # Adding a question with a duplicate name would raise SurveyCreationError
        """
        return EditSurvey(self).add_question(question, index)

    def _recombined_questions_and_instructions(
        self,
    ) -> List[Union["QuestionBase", "Instruction"]]:
        """Return a list of questions and instructions sorted by pseudo index."""
        questions_and_instructions = list(self.questions) + list(
            self._instruction_names_to_instructions.values()
        )
        return sorted(
            questions_and_instructions, key=lambda x: self._pseudo_indices[x.name]
        )

    # NEW: Public alias for compatibility with other modules such as SurveyExport
    def recombined_questions_and_instructions(
        self,
    ) -> List[Union["QuestionBase", "Instruction"]]:
        """Return a list of questions and instructions (public wrapper).

        This is a thin wrapper around the internal
        `_recombined_questions_and_instructions` method, provided for
        compatibility with modules that expect a public accessor.
        """
        return self._recombined_questions_and_instructions()

    def set_full_memory_mode(self) -> Survey:
        """Configure the survey so agents remember all previous questions and answers.

        In full memory mode, when an agent answers any question, it will have access to
        all previously asked questions and the agent's answers to them. This is useful
        for surveys where later questions build on or reference earlier responses.

        Returns:
            Survey: The modified survey instance (allows for method chaining).

        Examples:
            >>> s = Survey.example().set_full_memory_mode()
        """
        MemoryManagement(self)._set_memory_plan(lambda i: self.question_names[:i])
        return self

    def set_lagged_memory(self, lags: int) -> Survey:
        """Configure the survey so agents remember a limited window of previous questions.

        In lagged memory mode, when an agent answers a question, it will only have access
        to the most recent 'lags' number of questions and answers. This is useful for
        limiting context when only recent questions are relevant.

        Args:
            lags: The number of previous questions to remember. For example, if lags=2,
                only the two most recent questions and answers will be remembered.

        Returns:
            Survey: The modified survey instance (allows for method chaining).

        Examples:
            Remember only the two most recent questions:

            >>> s = Survey.example().set_lagged_memory(2)
        """
        MemoryManagement(self)._set_memory_plan(
            lambda i: self.question_names[max(0, i - lags) : i]
        )
        return self

    def _set_memory_plan(self, prior_questions_func: Callable) -> None:
        """Set a custom memory plan based on a provided function.

        This is an internal method used to define custom memory plans. The function
        provided determines which previous questions should be remembered for each
        question index.

        Args:
            prior_questions_func: A function that takes the index of the current question
                and returns a list of question names to remember.

        Examples:
            >>> s = Survey.example()
            >>> s._set_memory_plan(lambda i: s.question_names[:i])
        """
        MemoryManagement(self)._set_memory_plan(prior_questions_func)

    def add_targeted_memory(
        self,
        focal_question: Union[QuestionBase, str],
        prior_question: Union[QuestionBase, str],
    ) -> Survey:
        """Configure the survey so a specific question has access to a prior question's answer.

        This method allows you to define memory relationships between specific questions.
        When an agent answers the focal_question, it will have access to the prior_question
        and its answer, regardless of other memory settings.

        Args:
            focal_question: The question for which to add memory, specified either as a
                QuestionBase object or its question_name string.
            prior_question: The prior question to remember, specified either as a
                QuestionBase object or its question_name string.

        Returns:
            Survey: The modified survey instance (allows for method chaining).

        Examples:
            When answering q2, remember the answer to q0:

            >>> s = Survey.example().add_targeted_memory("q2", "q0")
            >>> s.memory_plan
            {'q2': Memory(prior_questions=['q0'])}
        """
        return MemoryManagement(self).add_targeted_memory(
            focal_question, prior_question
        )

    def add_memory_collection(
        self,
        focal_question: Union[QuestionBase, str],
        prior_questions: List[Union[QuestionBase, str]],
    ) -> Survey:
        """Configure the survey so a specific question has access to multiple prior questions.

        This method allows you to define memory relationships between specific questions.
        When an agent answers the focal_question, it will have access to all the questions
        and answers specified in prior_questions.

        Args:
            focal_question: The question for which to add memory, specified either as a
                QuestionBase object or its question_name string.
            prior_questions: A list of prior questions to remember, each specified either
                as a QuestionBase object or its question_name string.

        Returns:
            Survey: The modified survey instance (allows for method chaining).

        Examples:
            When answering q2, remember the answers to both q0 and q1:

            >>> s = Survey.example().add_memory_collection("q2", ["q0", "q1"])
            >>> s.memory_plan
            {'q2': Memory(prior_questions=['q0', 'q1'])}
        """
        return MemoryManagement(self).add_memory_collection(
            focal_question, prior_questions
        )

    def add_question_group(
        self,
        start_question: Union[QuestionBase, str],
        end_question: Union[QuestionBase, str],
        group_name: str,
    ) -> Survey:
        """Create a logical group of questions within the survey.

        Question groups allow you to organize questions into meaningful sections,
        which can be useful for:
        - Analysis (analyzing responses by section)
        - Navigation (jumping between sections)
        - Presentation (displaying sections with headers)

        Groups are defined by a contiguous range of questions from start_question
        to end_question, inclusive. Groups cannot overlap with other groups.

        Args:
            start_question: The first question in the group, specified either as a
                QuestionBase object or its question_name string.
            end_question: The last question in the group, specified either as a
                QuestionBase object or its question_name string.
            group_name: A name for the group. Must be a valid Python identifier
                and must not conflict with existing group or question names.

        Returns:
            Survey: The modified survey instance (allows for method chaining).

        Raises:
            SurveyCreationError: If the group name is invalid, already exists,
                conflicts with a question name, if start comes after end,
                or if the group overlaps with an existing group.

        Examples:
            Create a group of questions for demographics:

            >>> s = Survey.example().add_question_group("q0", "q1", "group1")
            >>> s.question_groups
            {'group1': (0, 1)}

            Group names must be valid Python identifiers:

            >>> from edsl.surveys.exceptions import SurveyCreationError
            >>> # Example showing invalid group name error
            >>> try:
            ...     Survey.example().add_question_group("q0", "q2", "1group1")
            ... except SurveyCreationError:
            ...     print("Error: Invalid group name (as expected)")
            Error: Invalid group name (as expected)

            Group names can't conflict with question names:

            >>> # Example showing name conflict error
            >>> try:
            ...     Survey.example().add_question_group("q0", "q1", "q0")
            ... except SurveyCreationError:
            ...     print("Error: Group name conflicts with question name (as expected)")
            Error: Group name conflicts with question name (as expected)

            Start question must come before end question:

            >>> # Example showing index order error
            >>> try:
            ...     Survey.example().add_question_group("q1", "q0", "group1")
            ... except SurveyCreationError:
            ...     print("Error: Start index greater than end index (as expected)")
            Error: Start index greater than end index (as expected)
        """

        if not group_name.isidentifier():
            raise SurveyCreationError(
                f"Group name {group_name} is not a valid identifier."
            )

        if group_name in self.question_groups:
            raise SurveyCreationError(
                f"Group name {group_name} already exists in the survey."
            )

        if group_name in self.question_name_to_index:
            raise SurveyCreationError(
                f"Group name {group_name} already exists as a question name in the survey."
            )

        start_index = self._get_question_index(start_question)
        end_index = self._get_question_index(end_question)

        # Check if either index is the EndOfSurvey object
        if start_index is EndOfSurvey or end_index is EndOfSurvey:
            raise SurveyCreationError(
                "Cannot use EndOfSurvey as a boundary for question groups."
            )

        # Now we know both are integers
        assert isinstance(start_index, int) and isinstance(end_index, int)

        if start_index > end_index:
            raise SurveyCreationError(
                f"Start index {start_index} is greater than end index {end_index}."
            )

        # Check for overlaps with existing groups
        for existing_group_name, (
            exist_start,
            exist_end,
        ) in self.question_groups.items():
            # Ensure the existing indices are integers (they should be, but for type checking)
            assert isinstance(exist_start, int) and isinstance(exist_end, int)

            # Check containment and overlap cases
            if start_index < exist_start and end_index > exist_end:
                raise SurveyCreationError(
                    f"Group {existing_group_name} is contained within the new group."
                )
            if start_index > exist_start and end_index < exist_end:
                raise SurveyCreationError(
                    f"New group would be contained within existing group {existing_group_name}."
                )
            if start_index < exist_start and end_index > exist_start:
                raise SurveyCreationError(
                    f"New group overlaps with the start of existing group {existing_group_name}."
                )
            if start_index < exist_end and end_index > exist_end:
                raise SurveyCreationError(
                    f"New group overlaps with the end of existing group {existing_group_name}."
                )

        self.question_groups[group_name] = (start_index, end_index)
        return self

    def show_rules(self) -> None:
        """Print out the rules in the survey.

        >>> s = Survey.example()
        >>> s.show_rules()
        Dataset([{'current_q': [0, 0, 1, 2]}, {'expression': ['True', "{{ q0.answer }}== 'yes'", 'True', 'True']}, {'next_q': [1, 2, 2, 3]}, {'priority': [-1, 0, -1, -1]}, {'before_rule': [False, False, False, False]}])
        """
        return self.rule_collection.show_rules()

    def add_stop_rule(
        self, question: Union[QuestionBase, str], expression: str
    ) -> Survey:
        """Add a rule that stops the survey.
        The rule is evaluated *after* the question is answered. If the rule is true, the survey ends.

        :param question: The question to add the stop rule to.
        :param expression: The expression to evaluate.

        If this rule is true, the survey ends.

        Here, answering "yes" to q0 ends the survey:

        >>> s = Survey.example().add_stop_rule("q0", "{{ q0.answer }} == 'yes'")
        >>> s.next_question("q0", {"q0.answer": "yes"})
        EndOfSurvey

        By comparison, answering "no" to q0 does not end the survey:

        >>> s.next_question("q0", {"q0.answer": "no"}).question_name
        'q1'

        # Using invalid operators like '<>' would raise SurveyCreationError
        """
        return RuleManager(self).add_stop_rule(question, expression)

    def clear_non_default_rules(self) -> Survey:
        """Remove all non-default rules from the survey.

        >>> Survey.example().show_rules()
        Dataset([{'current_q': [0, 0, 1, 2]}, {'expression': ['True', "{{ q0.answer }}== 'yes'", 'True', 'True']}, {'next_q': [1, 2, 2, 3]}, {'priority': [-1, 0, -1, -1]}, {'before_rule': [False, False, False, False]}])
        >>> Survey.example().clear_non_default_rules().show_rules()
        Dataset([{'current_q': [0, 1, 2]}, {'expression': ['True', 'True', 'True']}, {'next_q': [1, 2, 3]}, {'priority': [-1, -1, -1]}, {'before_rule': [False, False, False]}])
        """
        s = Survey()
        for question in self.questions:
            s.add_question(question)
        return s

    def add_skip_rule(
        self, question: Union["QuestionBase", str], expression: str
    ) -> Survey:
        """Add a rule to skip a question based on a conditional expression.

        Skip rules are evaluated *before* the question is presented. If the expression
        evaluates to True, the question is skipped and the flow proceeds to the next
        question in sequence. This is different from jump rules which are evaluated
        *after* a question is answered.

        Args:
            question: The question to add the skip rule to, either as a QuestionBase object
                or its question_name string.
            expression: A string expression that will be evaluated to determine if the
                question should be skipped. Can reference previous questions' answers
                using the template syntax, e.g., "{{ q0.answer }} == 'yes'".

        Returns:
            Survey: The modified survey instance (allows for method chaining).

        Examples:
            Skip q0 unconditionally (always skip):

            >>> from edsl import QuestionFreeText
            >>> q0 = QuestionFreeText.example()
            >>> q0.question_name = "q0"
            >>> q1 = QuestionFreeText.example()
            >>> q1.question_name = "q1"
            >>> s = Survey([q0, q1]).add_skip_rule("q0", "True")
            >>> s.next_question("q0", {}).question_name
            'q1'

            Skip a question conditionally:

            >>> q2 = QuestionFreeText.example()
            >>> q2.question_name = "q2"
            >>> s = Survey([q0, q1, q2])
            >>> s = s.add_skip_rule("q1", "{{ q0.answer }} == 'skip next'")
        """
        question_index = self._get_question_index(question)

        # Only proceed if question_index is an integer (not EndOfSurvey)
        if isinstance(question_index, int):
            next_index = question_index + 1
            return RuleManager(self).add_rule(
                question, expression, next_index, before_rule=True
            )
        else:
            raise SurveyCreationError("Cannot add skip rule to EndOfSurvey")

    def add_rule(
        self,
        question: Union["QuestionBase", str],
        expression: str,
        next_question: Union["QuestionBase", str, int, EndOfSurveyParent],
        before_rule: bool = False,
    ) -> Survey:
        """Add a conditional rule for navigating between questions in the survey.

        Rules determine the flow of questions based on conditional expressions. When a rule's
        expression evaluates to True, the survey will navigate to the specified next question,
        potentially skipping questions or jumping to an earlier question.

        By default, rules are evaluated *after* a question is answered. When before_rule=True,
        the rule is evaluated before the question is presented (which is useful for skip logic).

        Args:
            question: The question this rule applies to, either as a QuestionBase object
                or its question_name string.
            expression: A string expression that will be evaluated to determine if the
                rule should trigger. Can reference previous questions' answers using
                the template syntax, e.g., "{{ q0.answer }} == 'yes'".
            next_question: The destination question to jump to if the expression is True.
                Can be specified as a QuestionBase object, a question_name string, an index,
                or the EndOfSurvey class to end the survey.
            before_rule: If True, the rule is evaluated before the question is presented.
                If False (default), the rule is evaluated after the question is answered.

        Returns:
            Survey: The modified survey instance (allows for method chaining).

        Examples:
            Add a rule that navigates to q2 if the answer to q0 is 'yes':

            >>> s = Survey.example().add_rule("q0", "{{ q0.answer }} == 'yes'", "q2")
            >>> s.next_question("q0", {"q0.answer": "yes"}).question_name
            'q2'

            Add a rule to end the survey conditionally:

            >>> from edsl.surveys.base import EndOfSurvey
            >>> s = Survey.example().add_rule("q0", "{{ q0.answer }} == 'end'", EndOfSurvey)
        """
        return RuleManager(self).add_rule(
            question, expression, next_question, before_rule=before_rule
        )

    def by(
        self,
        *args: Union[
            "Agent",
            "Scenario",
            "LanguageModel",
            "AgentList",
            "ScenarioList",
            "ModelList",
        ],
    ) -> "Jobs":
        """Add components to the survey and return a runnable Jobs object.

        This method is the primary way to prepare a survey for execution. It adds the
        necessary components (agents, scenarios, language models) to create a Jobs object
        that can be run to generate responses to the survey.

        The method can be chained to add multiple components in sequence.

        Args:
            *args: One or more components to add to the survey. Can include:
                - Agent: The persona that will answer the survey questions
                - Scenario: The context for the survey, with variables to substitute
                - LanguageModel: The model that will generate the agent's responses

        Returns:
            Jobs: A Jobs object that can be run to execute the survey.

        Examples:
            Create a runnable Jobs object with an agent and scenario:

            >>> s = Survey.example()
            >>> from edsl.agents import Agent
            >>> from edsl import Scenario
            >>> s.by(Agent.example()).by(Scenario.example())
            Jobs(...)

            Chain all components in a single call:

            >>> from edsl.language_models import LanguageModel
            >>> s.by(Agent.example(), Scenario.example(), LanguageModel.example())
            Jobs(...)
        """
        from edsl.jobs import Jobs

        return Jobs(survey=self).by(*args)

    def gold_standard(self, q_and_a_dict: dict[str, str]) -> "Result":
        """Run the survey with a gold standard agent and return the result object.

        Args:
            q_and_a_dict: A dictionary of question names and answers.
        """
        try:
            assert set(q_and_a_dict.keys()) == set(
                self.question_names
            ), "q_and_a_dict must have the same keys as the survey"
        except AssertionError:
            raise ValueError(
                "q_and_a_dict must have the same keys as the survey",
                set(q_and_a_dict.keys()),
                set(self.question_names),
            )
        from ..agents import Agent

        gold_agent = Agent()

        def f(self, question, scenario):
            return q_and_a_dict[question.question_name]

        gold_agent.add_direct_question_answering_method(f)
        return self.by(gold_agent).run(disable_remote_inference=True)[0]

    def to_jobs(self) -> "Jobs":
        """Convert the survey to a Jobs object without adding components.

        This method creates a Jobs object from the survey without adding any agents,
        scenarios, or language models. You'll need to add these components later
        using the `by()` method before running the job.

        Returns:
            Jobs: A Jobs object based on this survey.

        Examples:
            >>> s = Survey.example()
            >>> jobs = s.to_jobs()
            >>> jobs
            Jobs(...)
        """
        from edsl.jobs import Jobs

        return Jobs(survey=self)

    def show_prompts(self, all: bool = False) -> None:
        """Display the prompts that will be used when running the survey.

        This method converts the survey to a Jobs object and shows the prompts that
        would be sent to a language model. This is useful for debugging and understanding
        how the survey will be presented.

        Args:
            all: If True, show all prompt fields; if False (default), show only user_prompt and system_prompt.
        """
        self.to_jobs().show_prompts(all=all)

    def __call__(
        self,
        model=None,
        agent=None,
        cache=None,
        verbose=False,
        disable_remote_cache: bool = False,
        disable_remote_inference: bool = False,
        **kwargs,
    ) -> "Results":
        """Execute the survey with the given parameters and return results.

        This is a convenient shorthand for creating a Jobs object and running it immediately.
        Any keyword arguments are passed as scenario parameters.

        Args:
            model: The language model to use. If None, a default model is used.
            agent: The agent to use. If None, a default agent is used.
            cache: The cache to use for storing results. If None, no caching is used.
            verbose: If True, show detailed progress information.
            disable_remote_cache: If True, don't use remote cache even if available.
            disable_remote_inference: If True, don't use remote inference even if available.
            **kwargs: Key-value pairs to use as scenario parameters.

        Returns:
            Results: The results of running the survey.

        Examples:
            Run a survey with a functional question that uses scenario parameters:

            >>> from edsl.questions import QuestionFunctional
            >>> def f(scenario, agent_traits): return "yes" if scenario["period"] == "morning" else "no"
            >>> q = QuestionFunctional(question_name="q0", func=f)
            >>> s = Survey([q])
            >>> s(period="morning", cache=False, disable_remote_cache=True, disable_remote_inference=True).select("answer.q0").first()
            'yes'
            >>> s(period="evening", cache=False, disable_remote_cache=True, disable_remote_inference=True).select("answer.q0").first()
            'no'
        """
        return self.get_job(model, agent, **kwargs).run(
            cache=cache,
            verbose=verbose,
            disable_remote_cache=disable_remote_cache,
            disable_remote_inference=disable_remote_inference,
        )

    async def run_async(
        self,
        model: Optional["LanguageModel"] = None,
        agent: Optional["Agent"] = None,
        cache: Optional["Cache"] = None,
        **kwargs,
    ) -> "Results":
        """Execute the survey asynchronously and return results.

        This method provides an asynchronous way to run surveys, which is useful for
        concurrent execution or integration with other async code. It creates a Jobs
        object and runs it asynchronously.

        Args:
            model: The language model to use. If None, a default model is used.
            agent: The agent to use. If None, a default agent is used.
            cache: The cache to use for storing results. If provided, reuses cached results.
            **kwargs: Key-value pairs to use as scenario parameters. May include:
                - disable_remote_inference: If True, don't use remote inference even if available.
                - disable_remote_cache: If True, don't use remote cache even if available.

        Returns:
            Results: The results of running the survey.

        Examples:
            Run a survey asynchronously with morning parameter:

            >>> import asyncio
            >>> from edsl.questions import QuestionFunctional
            >>> def f(scenario, agent_traits): return "yes" if scenario["period"] == "morning" else "no"
            >>> q = QuestionFunctional(question_name="q0", func=f)
            >>> from edsl import Model
            >>> s = Survey([q])
            >>> async def test_run_async():
            ...     result = await s.run_async(period="morning", disable_remote_inference = True)
            ...     print(result.select("answer.q0").first())
            >>> asyncio.run(test_run_async())
            yes

            Run with evening parameter:

            >>> async def test_run_async2():
            ...     result = await s.run_async(period="evening", disable_remote_inference = True)
            ...     print(result.select("answer.q0").first())
            >>> asyncio.run(test_run_async2())
            no
        """
        # Create a cache if none provided
        if cache is None:
            from edsl.caching import Cache

            c = Cache()
        else:
            c = cache

        # Get scenario parameters, excluding any that will be passed to run_async
        scenario_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k not in ["disable_remote_inference", "disable_remote_cache"]
        }

        # Get the job options to pass to run_async
        job_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k in ["disable_remote_inference", "disable_remote_cache"]
        }

        jobs: "Jobs" = self.get_job(model=model, agent=agent, **scenario_kwargs).using(
            c
        )
        return await jobs.run_async(**job_kwargs)

    def run(self, *args, **kwargs) -> "Results":
        """Convert the survey to a Job and execute it with the provided parameters.

        This method creates a Jobs object from the survey and runs it immediately with
        the provided arguments. It's a convenient way to run a survey without explicitly
        creating a Jobs object first.

        Args:
            *args: Positional arguments passed to the Jobs.run() method.
            **kwargs: Keyword arguments passed to the Jobs.run() method, which can include:
                - cache: The cache to use for storing results
                - verbose: Whether to show detailed progress
                - disable_remote_cache: Whether to disable remote caching
                - disable_remote_inference: Whether to disable remote inference

        Returns:
            Results: The results of running the survey.

        Examples:
            Run a survey with a test language model:

            >>> from edsl import QuestionFreeText
            >>> s = Survey([QuestionFreeText.example()])
            >>> from edsl.language_models import LanguageModel
            >>> m = LanguageModel.example(test_model=True, canned_response="Great!")
            >>> results = s.by(m).run(cache=False, disable_remote_cache=True, disable_remote_inference=True)
            >>> results.select('answer.*')
            Dataset([{'answer.how_are_you': ['Great!']}])
        """
        from ..jobs import Jobs

        return Jobs(survey=self).run(*args, **kwargs)

    def using(self, obj: Union["Cache", "KeyLookup", "BucketCollection"]) -> "Jobs":
        """Turn the survey into a Job and appends the arguments to the Job."""
        from ..jobs.Jobs import Jobs

        return Jobs(survey=self).using(obj)

    def duplicate(self):
        """Duplicate the survey.

        >>> s = Survey.example()
        >>> s2 = s.duplicate()
        >>> s == s2
        True
        >>> s is s2
        False

        """
        return Survey.from_dict(self.to_dict())

    def next_question(
        self,
        current_question: Optional[Union[str, "QuestionBase"]] = None,
        answers: Optional[Dict[str, Any]] = None,
    ) -> Union["QuestionBase", EndOfSurveyParent]:
        """
        Return the next question in a survey.

        :param current_question: The current question in the survey.
        :param answers: The answers for the survey so far

        - If called with no arguments, it returns the first question in the survey.
        - If no answers are provided for a question with a rule, the next question is returned. If answers are provided, the next question is determined by the rules and the answers.
        - If the next question is the last question in the survey, an EndOfSurvey object is returned.

        >>> s = Survey.example()
        >>> s.next_question("q0", {"q0.answer": "yes"}).question_name
        'q2'
        >>> s.next_question("q0", {"q0.answer": "no"}).question_name
        'q1'

        """
        if current_question is None:
            return self.questions[0]

        if isinstance(current_question, str):
            current_question = self._get_question_by_name(current_question)

        question_index = self.question_name_to_index[current_question.question_name]
        # Ensure we have a non-None answers dict
        answer_dict = answers if answers is not None else {}
        next_question_object = self.rule_collection.next_question(
            question_index, answer_dict
        )

        if next_question_object.num_rules_found == 0:
            raise SurveyHasNoRulesError("No rules found for this question")

        if next_question_object.next_q == EndOfSurvey:
            return EndOfSurvey
        else:
            if next_question_object.next_q >= len(self.questions):
                return EndOfSurvey
            else:
                return self.questions[next_question_object.next_q]

    def next_question_with_instructions(
        self,
        current_item: Optional[Union[str, "QuestionBase", "Instruction"]] = None,
        answers: Optional[Dict[str, Any]] = None,
    ) -> Union["QuestionBase", "Instruction", EndOfSurveyParent]:
        """
        Return the next question or instruction in a survey, including instructions in sequence.

        This method extends the functionality of next_question to also handle Instructions
        that are interspersed between questions. It follows the proper sequence based on
        pseudo indices and respects survey rules for question flow.

        :param current_item: The current question or instruction in the survey.
        :param answers: The answers for the survey so far

        - If called with no arguments, it returns the first item (question or instruction) in the survey.
        - For instructions, it returns the next item in sequence since instructions don't have answers.
        - For questions, it uses the rule logic to determine the next question, then returns any
          instructions that come before that target question, or the target question itself.
        - If the next item would be past the end of the survey, an EndOfSurvey object is returned.

        Returns:
            Union["QuestionBase", "Instruction", EndOfSurveyParent]: The next question, instruction, or EndOfSurvey.

        Examples:
            With a survey that has instructions:

            >>> from edsl import Instruction
            >>> s = Survey.example(include_instructions=True)
            >>> # Get the first item (should be the instruction)
            >>> first_item = s.next_question_with_instructions()
            >>> hasattr(first_item, 'text')  # Instructions have text attribute
            True

            >>> # After an instruction, get the next item
            >>> next_item = s.next_question_with_instructions(first_item)
            >>> hasattr(next_item, 'question_name')  # Questions have question_name attribute
            True
        """
        # Get the combined and ordered list of questions and instructions
        combined_items = self._recombined_questions_and_instructions()

        if not combined_items:
            return EndOfSurvey

        # If no current item specified, return the first item
        if current_item is None:
            return combined_items[0]

        # Handle string input by finding the corresponding item
        if isinstance(current_item, str):
            # Look for it in questions first
            if current_item in self.question_name_to_index:
                current_item = self._get_question_by_name(current_item)
            # Then look for it in instructions
            elif current_item in self._instruction_names_to_instructions:
                current_item = self._instruction_names_to_instructions[current_item]
            else:
                raise SurveyError(f"Item name {current_item} not found in survey.")

        # Find the current item's position in the combined list
        try:
            current_position = combined_items.index(current_item)
        except ValueError:
            raise SurveyError("Current item not found in survey sequence.")

        # If this is an instruction, determine what comes next
        if hasattr(current_item, "text") and not hasattr(current_item, "question_name"):
            # This is an instruction
            if current_position + 1 >= len(combined_items):
                return EndOfSurvey

            # Check if this instruction is between questions that have rule-based navigation
            # We need to figure out what question would have led to this instruction
            prev_question = None
            for i in range(current_position - 1, -1, -1):
                item = combined_items[i]
                if hasattr(item, "question_name"):
                    prev_question = item
                    break

            if prev_question is not None:
                # Check if there are rules from this previous question that would jump over the next sequential question
                prev_q_index = self.question_name_to_index[prev_question.question_name]
                answer_dict = answers if answers is not None else {}

                try:
                    next_question_object = self.rule_collection.next_question(
                        prev_q_index, answer_dict
                    )
                    if (
                        next_question_object.num_rules_found > 0
                        and next_question_object.next_q != EndOfSurvey
                    ):
                        # There's a rule that determined the next question
                        target_question = self.questions[next_question_object.next_q]
                        target_position = combined_items.index(target_question)

                        # If the target is after this instruction, continue toward it
                        if target_position > current_position:
                            # Look for the next question that should be shown
                            next_position = current_position + 1
                            while next_position < target_position:
                                next_item = combined_items[next_position]
                                if hasattr(next_item, "text") and not hasattr(
                                    next_item, "question_name"
                                ):
                                    # Another instruction before target
                                    return next_item
                                next_position += 1
                            # No more instructions, return the target
                            return target_question
                except (SurveyHasNoRulesError, IndexError):
                    # No rules or error, fall back to sequential
                    pass

            # Default: return next item in sequence
            return combined_items[current_position + 1]

        # This is a question - use rule logic to determine the target next question
        if not hasattr(current_item, "question_name"):
            raise SurveyError("Current item is neither a question nor an instruction.")

        question_index = self.question_name_to_index[current_item.question_name]
        answer_dict = answers if answers is not None else {}

        next_question_object = self.rule_collection.next_question(
            question_index, answer_dict
        )

        if next_question_object.num_rules_found == 0:
            raise SurveyHasNoRulesError("No rules found for this question")

        # Handle end of survey case
        if next_question_object.next_q == EndOfSurvey:
            # Check if there are any instructions after the current question before ending
            next_position = current_position + 1
            if next_position < len(combined_items):
                next_item = combined_items[next_position]
                if hasattr(next_item, "text") and not hasattr(
                    next_item, "question_name"
                ):
                    return next_item
            return EndOfSurvey

        if next_question_object.next_q >= len(self.questions):
            # Check if there are any instructions after the current question before ending
            next_position = current_position + 1
            if next_position < len(combined_items):
                next_item = combined_items[next_position]
                if hasattr(next_item, "text") and not hasattr(
                    next_item, "question_name"
                ):
                    return next_item
            return EndOfSurvey

        # Find the target question in the combined list
        target_question = self.questions[next_question_object.next_q]
        try:
            target_position = combined_items.index(target_question)
        except ValueError:
            # This shouldn't happen, but handle gracefully
            return target_question

        # Look for any instructions between current position and target position
        # Start checking from the position after current
        next_position = current_position + 1

        # If we're already at or past the end, return EndOfSurvey
        if next_position >= len(combined_items):
            return EndOfSurvey

        # If the target question is the very next item, return it
        if next_position == target_position:
            return target_question

        # If there are items between current and target, check if any are instructions
        # that should be shown before reaching the target question
        while next_position < target_position:
            next_item = combined_items[next_position]
            # If it's an instruction, return it (caller should pass target when calling again)
            if hasattr(next_item, "text") and not hasattr(next_item, "question_name"):
                return next_item
            next_position += 1

        # If we've gone through all items between current and target without finding
        # an instruction, return the target question
        return target_question

    def gen_path_through_survey(self) -> Generator[QuestionBase, dict, None]:
        """Generate a coroutine that navigates through the survey based on answers.

        This method creates a Python generator that implements the survey flow logic.
        It yields questions and receives answers, handling the branching logic based
        on the rules defined in the survey. This generator is the core mechanism used
        by the Interview process to administer surveys.

        The generator follows these steps:
        1. Yields the first question (or skips it if skip rules apply)
        2. Receives an answer dictionary from the caller via .send()
        3. Updates the accumulated answers
        4. Determines the next question based on the survey rules
        5. Yields the next question
        6. Repeats steps 2-5 until the end of survey is reached

        Returns:
            Generator[QuestionBase, dict, None]: A generator that yields questions and
                receives answer dictionaries. The generator terminates when it reaches
                the end of the survey.

        Examples:
            For the example survey with conditional branching:

            >>> s = Survey.example()
            >>> s.show_rules()
            Dataset([{'current_q': [0, 0, 1, 2]}, {'expression': ['True', "{{ q0.answer }}== 'yes'", 'True', 'True']}, {'next_q': [1, 2, 2, 3]}, {'priority': [-1, 0, -1, -1]}, {'before_rule': [False, False, False, False]}])

            Path when answering "yes" to first question:

            >>> i = s.gen_path_through_survey()
            >>> next(i)  # Get first question
            Question('multiple_choice', question_name = \"""q0\""", question_text = \"""Do you like school?\""", question_options = ['yes', 'no'])
            >>> i.send({"q0.answer": "yes"})  # Answer "yes" and get next question
            Question('multiple_choice', question_name = \"""q2\""", question_text = \"""Why?\""", question_options = ['**lack*** of killer bees in cafeteria', 'other'])

            Path when answering "no" to first question:

            >>> i2 = s.gen_path_through_survey()
            >>> next(i2)  # Get first question
            Question('multiple_choice', question_name = \"""q0\""", question_text = \"""Do you like school?\""", question_options = ['yes', 'no'])
            >>> i2.send({"q0.answer": "no"})  # Answer "no" and get next question
            Question('multiple_choice', question_name = \"""q1\""", question_text = \"""Why not?\""", question_options = ['killer bees in cafeteria', 'other'])
        """
        # Initialize empty answers dictionary
        self.answers: Dict[str, Any] = {}

        # Start with the first question
        question = self.questions[0]

        # Check if the first question should be skipped based on skip rules
        if self.rule_collection.skip_question_before_running(0, self.answers):
            question = self.next_question(question, self.answers)

        # Continue through the survey until we reach the end
        while not question == EndOfSurvey:
            # Yield the current question and wait for an answer
            answer = yield question

            # Update the accumulated answers with the new answer
            self.answers.update(answer)

            # Determine the next question based on the rules and answers
            # TODO: This should also include survey and agent attributes
            question = self.next_question(question, self.answers)

    def dag(self, textify: bool = False) -> "DAG":
        """Return a Directed Acyclic Graph (DAG) representation of the survey flow.

        This method constructs a DAG that represents the possible paths through the survey,
        taking into account both skip logic and memory relationships. The DAG is useful
        for visualizing and analyzing the structure of the survey.

        Args:
            textify: If True, the DAG will use question names as nodes instead of indices.
                This makes the DAG more human-readable but less compact.

        Returns:
            DAG: A dictionary where keys are question indices (or names if textify=True)
                and values are sets of prerequisite questions. For example, {2: {0, 1}}
                means question 2 depends on questions 0 and 1.

        Examples:
            >>> s = Survey.example()
            >>> d = s.dag()
            >>> d
            {1: {0}, 2: {0}}

            With textify=True:

            >>> dag = s.dag(textify=True)
            >>> sorted([(k, sorted(list(v))) for k, v in dag.items()])
            [('q1', ['q0']), ('q2', ['q0'])]
        """
        from .dag import ConstructDAG

        return ConstructDAG(self).dag(textify)

    ###################
    # DUNDER METHODS
    ###################
    def __len__(self) -> int:
        """Return the number of questions in the survey.

        >>> s = Survey.example()
        >>> len(s)
        3
        """
        return len(self.questions)

    def _create_subsurvey(self, selected_questions: List["QuestionBase"]) -> "Survey":
        """Create a new Survey with the specified questions.

        This helper method creates a new Survey instance containing only the
        selected questions. The new survey inherits relevant attributes from
        the parent survey but gets fresh rule collections and memory plans
        appropriate for the subset of questions.

        :param selected_questions: List of question objects to include in the new survey
        :return: New Survey instance with the selected questions
        """
        # Create new survey with selected questions
        new_survey = Survey(questions=selected_questions)

        # Copy relevant attributes that make sense for a subsurvey
        if hasattr(self, "questions_to_randomize") and self.questions_to_randomize:
            # Only include randomization settings for questions that are in the subsurvey
            selected_names = {q.question_name for q in selected_questions}
            relevant_randomization = [
                name for name in self.questions_to_randomize if name in selected_names
            ]
            if relevant_randomization:
                new_survey.questions_to_randomize = relevant_randomization

        return new_survey

    def __getitem__(
        self, index: Union[int, str, slice, List[str]]
    ) -> Union["QuestionBase", "Survey"]:
        """Return question(s) or a new Survey based on the index type.

        :param index: The index of the question(s) to get. Can be:
            - int: return single question by position
            - str: return single question by name
            - slice: return new Survey with sliced questions
            - List[str]: return new Survey with questions selected by name

        Examples:
            >>> s = Survey.example()
            >>> s[0]  # Single question by index
            Question('multiple_choice', question_name = \"""q0\""", question_text = \"""Do you like school?\""", question_options = ['yes', 'no'])

            >>> sub = s[:2]  # First 2 questions as new Survey
            >>> len(sub) == 2
            True
            >>> sub.question_names == ['q0', 'q1']
            True

            >>> s['q0']  # Single question by name
            Question('multiple_choice', question_name = \"""q0\""", question_text = \"""Do you like school?\""", question_options = ['yes', 'no'])

            >>> sub2 = s[['q0', 'q2']]  # Questions by name list as new Survey
            >>> sub2.question_names == ['q0', 'q2']
            True
        """
        if isinstance(index, int):
            return self.questions[index]
        elif isinstance(index, str):
            # Return single question by name
            question_map = self.question_names_to_questions()
            if index not in question_map:
                raise KeyError(
                    f"Question '{index}' not found in survey. Available questions: {list(question_map.keys())}"
                )
            return question_map[index]
        elif isinstance(index, slice):
            # Return a new Survey with sliced questions
            selected_questions = self.questions[index]
            return self._create_subsurvey(selected_questions)
        elif isinstance(index, list) and all(isinstance(name, str) for name in index):
            # Return a new Survey with questions selected by name
            question_map = self.question_names_to_questions()
            selected_questions = []
            for name in index:
                if name not in question_map:
                    raise KeyError(
                        f"Question '{name}' not found in survey. Available questions: {list(question_map.keys())}"
                    )
                selected_questions.append(question_map[name])
            return self._create_subsurvey(selected_questions)
        else:
            raise TypeError(
                f"Survey indices must be int, str, slice, or List[str], not {type(index)}"
            )

    def select(self, *question_names: List[str]) -> "Survey":
        """Create a new Survey with questions selected by name."""
        if isinstance(question_names, str):
            question_names = [question_names]

        if not question_names:
            raise ValueError("At least one question name must be provided")

        kept_questions = [self.get(name) for name in question_names]
        assert all(kept_questions), f"Question(s) {question_names} not found in survey"
        return Survey(questions=kept_questions)

    def drop(self, *question_names) -> "Survey":
        """Create a new Survey with specified questions removed by name.

        This method creates a new Survey instance that contains all questions
        except those specified in the question_names parameter. It's the inverse
        of the select() method.

        Args:
            *question_names: Variable number of question names to remove from the survey.

        Returns:
            Survey: A new Survey instance with the specified questions removed.

        Raises:
            ValueError: If no question names are provided.
            KeyError: If any specified question name is not found in the survey.

        Examples:
            >>> s = Survey.example()
            >>> s.question_names
            ['q0', 'q1', 'q2']
            >>> s_dropped = s.drop('q1')
            >>> s_dropped.question_names
            ['q0', 'q2']
            >>> s_dropped2 = s.drop('q0', 'q2')
            >>> s_dropped2.question_names
            ['q1']
        """
        # Handle case where a single string is passed
        if isinstance(question_names, str):
            question_names = [question_names]

        if not question_names:
            raise ValueError("At least one question name must be provided")

        # Validate that all question names exist
        question_map = self.question_names_to_questions()
        for name in question_names:
            if name not in question_map:
                raise KeyError(
                    f"Question '{name}' not found in survey. Available questions: {list(question_map.keys())}"
                )

        # Get all questions except the ones to drop
        kept_questions = [
            q for q in self.questions if q.question_name not in question_names
        ]

        return self._create_subsurvey(kept_questions)

    def __repr__(self) -> str:
        """Return a string representation of the survey."""

        # questions_string = ", ".join([repr(q) for q in self._questions])
        questions_string = ", ".join([repr(q) for q in self.raw_passed_questions or []])
        # question_names_string = ", ".join([repr(name) for name in self.question_names])
        return f"Survey(questions=[{questions_string}], memory_plan={self.memory_plan}, rule_collection={self.rule_collection}, question_groups={self.question_groups}, questions_to_randomize={self.questions_to_randomize})"

    def _summary(self) -> dict:
        return {
            "# questions": len(self),
            "question_name list": self.question_names,
        }

    def tree(self, node_list: Optional[List[str]] = None):
        return self.to_scenario_list().tree(node_list=node_list)

    def table(self, *fields, tablefmt="rich") -> Table:
        return self.to_scenario_list().to_dataset().table(*fields, tablefmt=tablefmt)

    def codebook(self) -> Dict[str, str]:
        """Create a codebook for the survey, mapping question names to question text.

        >>> s = Survey.example()
        >>> s.codebook()
        {'q0': 'Do you like school?', 'q1': 'Why not?', 'q2': 'Why?'}
        """
        codebook = {}
        for question in self.questions:
            codebook[question.question_name] = question.question_text
        return codebook

    def with_edited_question(
        self,
        question_name: str,
        field_name_new_values: dict,
        pop_fields: Optional[List[str]] = None,
    ) -> "Survey":
        """Return a new Survey with the specified question edited.

        This method creates a new Survey instance with the specified question edited.
        The new survey inherits relevant attributes from the parent survey but gets
        fresh rule collections and memory plans appropriate for the subset of questions.
        """
        new_survey = self.duplicate()
        question = new_survey.get(question_name)
        from ..questions import Question

        old_dict = question.to_dict(add_edsl_version=False)
        old_dict.update(field_name_new_values)
        for field_name in pop_fields or []:
            _ = old_dict.pop(field_name)
        new_question = Question(**old_dict)
        new_survey.questions[new_survey.questions.index(question)] = new_question
        return new_survey

    def edit(self):
        import webbrowser
        import time

        info = self.push()
        print("Waiting for survey to be created on Coop...")
        time.sleep(5)
        url = f"https://www.expectedparrot.com/edit/survey/{info['uuid']}"
        webbrowser.open(url)
        print(f"Survey opened in web editor: {url}")

        # Wait for user to confirm editing is complete
        while True:
            user_input = input("Is editing complete [y/n]: ").strip().lower()
            if user_input in ["y", "yes"]:
                print("Waiting for changes to sync...")
                time.sleep(5)
                # Pull the updated survey and update current object
                updated_survey = Survey.pull(info["uuid"])
                # Update the current object's attributes with the pulled survey
                self.__dict__.update(updated_survey.__dict__)
                print("Survey updated with changes from web editor.")
                break
            elif user_input in ["n", "no"]:
                print("Editing session ended. Survey remains unchanged.")
                break
            else:
                print("Please enter 'y' for yes or 'n' for no.")

    @classmethod
    def example(
        cls,
        params: bool = False,
        randomize: bool = False,
        include_instructions: bool = False,
        custom_instructions: Optional[str] = None,
    ) -> Survey:
        """Create an example survey for testing and demonstration purposes.

        This method creates a simple branching survey about school preferences.
        The default survey contains three questions with conditional logic:
        - If the user answers "yes" to liking school, they are asked why they like it
        - If the user answers "no", they are asked why they don't like it

        Args:
            params: If True, adds a fourth question that demonstrates parameter substitution
                by referencing the question text and answer from the first question.
            randomize: If True, adds a random UUID to the first question text to ensure
                uniqueness across multiple instances.
            include_instructions: If True, adds an instruction to the beginning of the survey.
            custom_instructions: Custom instruction text to use if include_instructions is True.
                Defaults to "Please pay attention!" if not provided.

        Returns:
            Survey: A configured example survey instance.

        Examples:
            Create a basic example survey:

            >>> s = Survey.example()
            >>> [q.question_text for q in s.questions]
            ['Do you like school?', 'Why not?', 'Why?']

            Create an example with parameter substitution:

            >>> s = Survey.example(params=True)
            >>> s.questions[3].question_text
            "To the question '{{ q0.question_text}}', you said '{{ q0.answer }}'. Do you still feel this way?"
        """
        from ..questions import QuestionMultipleChoice

        # Add random UUID to question text if randomization is requested
        addition = "" if not randomize else str(uuid4())

        # Create the basic questions
        q0 = QuestionMultipleChoice(
            question_text=f"Do you like school?{addition}",
            question_options=["yes", "no"],
            question_name="q0",
        )
        q1 = QuestionMultipleChoice(
            question_text="Why not?",
            question_options=["killer bees in cafeteria", "other"],
            question_name="q1",
        )
        q2 = QuestionMultipleChoice(
            question_text="Why?",
            question_options=["**lack*** of killer bees in cafeteria", "other"],
            question_name="q2",
        )

        # Add parameter demonstration question if requested
        if params:
            q3 = QuestionMultipleChoice(
                question_text="To the question '{{ q0.question_text}}', you said '{{ q0.answer }}'. Do you still feel this way?",
                question_options=["yes", "no"],
                question_name="q3",
            )
            s = cls(questions=[q0, q1, q2, q3])
            return s

        # Add instruction if requested
        if include_instructions:
            from edsl import Instruction

            custom_instructions = (
                custom_instructions if custom_instructions else "Please pay attention!"
            )

            i = Instruction(text=custom_instructions, name="attention")
            s = cls(questions=[i, q0, q1, q2])
            return s

        # Create the basic survey with branching logic
        s = cls(questions=[q0, q1, q2])
        s = s.add_rule(q0, "{{ q0.answer }}== 'yes'", q2)
        return s

    def get_job(self, model=None, agent=None, **kwargs):
        if model is None:
            from edsl.language_models.model import Model

            model = Model()

        from edsl.scenarios import Scenario

        s = Scenario(kwargs)

        if not agent:
            from edsl.agents import Agent

            agent = Agent()

        return self.by(s).by(agent).by(model)

    ###################
    # COOP METHODS
    ###################
    def humanize(
        self,
        project_name: str = "Project",
        survey_description: Optional[str] = None,
        survey_alias: Optional[str] = None,
        survey_visibility: Optional["VisibilityType"] = "unlisted",
    ) -> dict:
        """
        Send the survey to Coop.

        Then, create a project on Coop so you can share the survey with human respondents.
        """
        from edsl.coop import Coop

        c = Coop()
        project_details = c.create_project(
            self,
            project_name=project_name,
            survey_description=survey_description,
            survey_alias=survey_alias,
            survey_visibility=survey_visibility,
        )
        return project_details

    # Add export method delegations
    def css(self):
        """Return the default CSS style for the survey."""
        return self._exporter.css()

    # def get_description(self) -> str:
    #     """Return the description of the survey."""
    #     return self._exporter.get_description()

    # NEW PREFERRED METHOD NAMES
    def to_docx(
        self,
        filename: Optional[str] = None,
    ) -> FileStore:
        """Generate a docx document for the survey.

        This is the preferred alias for the deprecated ``docx`` method.
        """
        return self._exporter.docx(filename)

    def to_html(
        self,
        scenario: Optional[dict] = None,
        filename: Optional[str] = None,
        return_link: bool = False,
        css: Optional[str] = None,
        cta: str = "Open HTML file",
        include_question_name: bool = False,
    ) -> FileStore:
        """Generate HTML representation of the survey.

        This is the preferred alias for the deprecated ``html`` method.
        """
        return self._exporter.html(
            scenario, filename, return_link, css, cta, include_question_name
        )

    # Deprecated aliases – keep for backward compatibility
    def docx(
        self,
        filename: Optional[str] = None,
    ) -> FileStore:
        """DEPRECATED: Use :py:meth:`to_docx` instead."""
        import warnings

        warnings.warn(
            "Survey.docx is deprecated and will be removed in a future release. Use Survey.to_docx instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.to_docx(filename)

    def show(self):
        """Display the survey in a rich format."""
        return self._exporter.show()

    def to_scenario_list(
        self, questions_only: bool = True, rename=False
    ) -> "ScenarioList":
        """Convert the survey to a scenario list."""
        return self._exporter.to_scenario_list(questions_only, rename)

    def code(self, filename: str = "", survey_var_name: str = "survey") -> list[str]:
        """Create the Python code representation of a survey."""
        return self._exporter.code(filename, survey_var_name)

    def html(
        self,
        scenario: Optional[dict] = None,
        filename: Optional[str] = None,
        return_link=False,
        css: Optional[str] = None,
        cta: str = "Open HTML file",
        include_question_name=False,
    ) -> FileStore:
        """DEPRECATED: Use :py:meth:`to_html` instead."""
        import warnings

        warnings.warn(
            "Survey.html is deprecated and will be removed in a future release. Use Survey.to_html instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.to_html(
            scenario,
            filename,
            return_link=return_link,
            css=css,
            cta=cta,
            include_question_name=include_question_name,
        )

    def latex(
        self,
        filename: Optional[str] = None,
        include_question_name: bool = False,
        standalone: bool = True,
    ) -> "FileStore":
        """Generate a LaTeX (.tex) representation of the survey.

        Parameters
        ----------
        filename : Optional[str]
            The filename to write to. If not provided, a temporary file is created
            in the current working directory with a ``.tex`` suffix.
        include_question_name : bool
            If True, includes the internal ``question_name`` of each question. Default False.
        standalone : bool
            If True, the LaTeX file is standalone. Default True.
        """
        return self._exporter.latex(filename, include_question_name, standalone)

    def copy(self) -> "Survey":
        """Create a deep copy of the survey using serialization.

        This method creates a completely independent copy of the survey by serializing
        and then deserializing it. This ensures all components are properly copied
        and maintains consistency with the survey's serialization format.

        Returns:
            Survey: A new Survey instance that is a deep copy of the original.

        Examples:
            >>> s = Survey.example()
            >>> s2 = s.copy()
            >>> s == s2
            True
            >>> s is s2
            False
            >>> s.questions[0] is s2.questions[0]
            False
        """
        return Survey.from_dict(self.to_dict())

    def with_renamed_question(self, old_name: str, new_name: str) -> "Survey":
        """Return a new survey with a question renamed and all references updated.

        This method creates a new survey with the specified question renamed. It also
        updates all references to the old question name in:
        - Rules and expressions (both old format 'q1' and new format '{{ q1.answer }}')
        - Memory plans (focal questions and prior questions)
        - Question text piping (e.g., {{ old_name.answer }})
        - Question options that use piping
        - Instructions that reference the question
        - Question groups (keys only, not ranges since those use indices)

        Args:
            old_name: The current name of the question to rename
            new_name: The new name for the question

        Returns:
            Survey: A new survey with the question renamed and all references updated

        Raises:
            SurveyError: If old_name doesn't exist, new_name already exists, or new_name is invalid

        Examples:
            >>> s = Survey.example()
            >>> s_renamed = s.with_renamed_question("q0", "school_preference")
            >>> s_renamed.get("school_preference").question_name
            'school_preference'

            >>> # Rules are also updated
            >>> s_renamed.show_rules()  # doctest: +SKIP
        """
        import re
        from .exceptions import SurveyError

        # Validate inputs
        if old_name not in self.question_name_to_index:
            raise SurveyError(f"Question '{old_name}' not found in survey.")

        if new_name in self.question_name_to_index:
            raise SurveyError(f"Question name '{new_name}' already exists in survey.")

        if not new_name.isidentifier():
            raise SurveyError(
                f"New question name '{new_name}' is not a valid Python identifier."
            )

        # Create a copy of the survey to work with
        new_survey = self.duplicate()

        # 1. Update the question name itself
        question_index = new_survey.question_name_to_index[old_name]
        target_question = new_survey.questions[question_index]
        target_question.question_name = new_name

        # 2. Update all rules that reference the old question name
        for rule in new_survey.rule_collection:
            # Update expressions - handle both old format (q1) and new format ({{ q1.answer }})
            # Old format: 'q1' or 'q1.answer' (standalone references)
            rule.expression = re.sub(
                rf"\b{re.escape(old_name)}\.answer\b",
                f"{new_name}.answer",
                rule.expression,
            )
            rule.expression = re.sub(
                rf"\b{re.escape(old_name)}\b(?!\.)", new_name, rule.expression
            )

            # New format: {{ q1.answer }} (Jinja2 template references)
            rule.expression = re.sub(
                rf"\{{\{{\s*{re.escape(old_name)}\.answer\s*\}}\}}",
                f"{{{{ {new_name}.answer }}}}",
                rule.expression,
            )
            rule.expression = re.sub(
                rf"\{{\{{\s*{re.escape(old_name)}\s*\}}\}}",
                f"{{{{ {new_name} }}}}",
                rule.expression,
            )

            # Update the question_name_to_index mapping in the rule
            if old_name in rule.question_name_to_index:
                index = rule.question_name_to_index.pop(old_name)
                rule.question_name_to_index[new_name] = index

        # 3. Update memory plans
        new_memory_plan_data = {}
        for focal_question, memory in new_survey.memory_plan.data.items():
            # Update focal question name if it matches
            new_focal = new_name if focal_question == old_name else focal_question

            # Update prior questions list (Memory class stores questions in data attribute)
            if hasattr(memory, "data"):
                new_prior_questions = [
                    new_name if prior_q == old_name else prior_q
                    for prior_q in memory.data
                ]
                # Create new memory object with updated prior questions
                from .memory.memory import Memory

                new_memory = Memory(prior_questions=new_prior_questions)
                new_memory_plan_data[new_focal] = new_memory
            else:
                new_memory_plan_data[new_focal] = memory

        new_survey.memory_plan.data = new_memory_plan_data

        # Update the memory plan's internal question name list
        if hasattr(new_survey.memory_plan, "survey_question_names"):
            new_survey.memory_plan.survey_question_names = [
                new_name if q_name == old_name else q_name
                for q_name in new_survey.memory_plan.survey_question_names
            ]

        # 4. Update piping references in all questions
        def update_piping_in_text(text: str) -> str:
            """Update piping references in text strings."""
            # Handle {{ old_name.answer }} format
            text = re.sub(
                rf"\{{\{{\s*{re.escape(old_name)}\.answer\s*\}}\}}",
                f"{{{{ {new_name}.answer }}}}",
                text,
            )
            # Handle {{ old_name }} format
            text = re.sub(
                rf"\{{\{{\s*{re.escape(old_name)}\s*\}}\}}",
                f"{{{{ {new_name} }}}}",
                text,
            )
            return text

        for question in new_survey.questions:
            # Update question text
            question.question_text = update_piping_in_text(question.question_text)

            # Update question options if they exist
            if hasattr(question, "question_options") and question.question_options:
                question.question_options = [
                    update_piping_in_text(option) if isinstance(option, str) else option
                    for option in question.question_options
                ]

        # 5. Update instructions
        for (
            instruction_name,
            instruction,
        ) in new_survey._instruction_names_to_instructions.items():
            if hasattr(instruction, "text"):
                instruction.text = update_piping_in_text(instruction.text)

        # 6. Update question groups - only if the renamed question is a key (not just in ranges)
        # Question groups use indices for ranges, so we don't need to update those
        # But if someone created a group with the same name as a question, we should handle that
        if old_name in new_survey.question_groups:
            group_range = new_survey.question_groups.pop(old_name)
            new_survey.question_groups[new_name] = group_range

        # 7. Update pseudo indices
        if old_name in new_survey._pseudo_indices:
            pseudo_index = new_survey._pseudo_indices.pop(old_name)
            new_survey._pseudo_indices[new_name] = pseudo_index

        return new_survey

    def inspect(self):
        """Create an interactive inspector widget for this survey.

        This method creates a SurveyInspectorWidget that provides an interactive
        interface for exploring the survey structure, questions, and flow logic.

        Returns:
            SurveyInspectorWidget instance: Interactive widget for inspecting this survey

        Raises:
            ImportError: If the widgets module cannot be imported
        """
        try:
            from ..widgets.survey_inspector import SurveyInspectorWidget
        except ImportError as e:
            raise ImportError(
                "Survey inspector widget is not available. Make sure the widgets module is installed."
            ) from e

        return SurveyInspectorWidget(self)


def main():
    """Run the example survey."""

    def example_survey():
        """Return an example survey."""
        from edsl import QuestionMultipleChoice, QuestionList, QuestionNumerical, Survey

        q0 = QuestionMultipleChoice(
            question_name="q0",
            question_text="What is the capital of France?",
            question_options=["London", "Paris", "Rome", "Boston", "I don't know"],
        )
        q1 = QuestionList(
            question_name="q1",
            question_text="Name some cities in France.",
            max_list_items=5,
        )
        q2 = QuestionNumerical(
            question_name="q2",
            question_text="What is the population of {{ q0.answer }}?",
        )
        s = Survey(questions=[q0, q1, q2])
        s = s.add_rule(q0, "q0 == 'Paris'", q2)
        return s

    s = example_survey()
    survey_dict = s.to_dict()
    s2 = Survey.from_dict(survey_dict)
    results = s2.run()
    print(results)


if __name__ == "__main__":
    import doctest

    # doctest.testmod(optionflags=doctest.ELLIPSIS | doctest.SKIP)
    doctest.testmod(optionflags=doctest.ELLIPSIS)
