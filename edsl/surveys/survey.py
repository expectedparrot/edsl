"""A Survey is a collection of questions that can be administered to an Agent or a Human.

This module defines the Survey class, which is the central data structure for creating
and managing surveys. A Survey consists of questions, instructions, and rules that
determine the flow of questions based on previous answers.

Surveys can include skip logic, memory management, and question groups.
"""

from __future__ import annotations
import re
import random
from uuid import uuid4
from pathlib import Path

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
    from ..dataset import Dataset
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
from .descriptors import QuestionsDescriptor, QuestionsToRandomizeDescriptor
from .memory import MemoryPlan
from ..instructions import InstructionHandler
from .edit_survey import EditSurvey
from .memory import MemoryManagement
from .rules import RuleManager, RuleCollection
from .survey_export import SurveyExport
from .pseudo_indices import PseudoIndices
from .survey_navigator import SurveyNavigator
from .question_group_manager import QuestionGroupManager
from .exceptions import (
    SurveyCreationError,
    SurveyError,
)



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

    questions_to_randomize = QuestionsToRandomizeDescriptor()
    """A descriptor that manages the list of question names to randomize.
    
    This descriptor validates that all question names in the list are strings
    and exist in the survey. When set to None, it defaults to an empty list.
    
    The underlying list is stored in the protected `_questions_to_randomize` attribute,
    while this property provides the public interface for accessing it.
    
    Notes:
        - All question names must exist in the survey
        - Only string values are allowed
        - Defaults to an empty list if not specified
    """

    def __init__(
        self,
        questions: Optional[List["QuestionType"] | str] = None,
        memory_plan: Optional["MemoryPlan"] = None,
        rule_collection: Optional["RuleCollection"] = None,
        question_groups: Optional["QuestionGroupType"] = None,
        name: Optional[str] = None,
        questions_to_randomize: Optional[List[str]] = None,
        options_to_pin: Optional[Dict[str, List]] = None,
        _internal_copy: bool = False,
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
        if questions is not None and isinstance(questions, str):
            pulled_survey = Survey.pull(questions)
            self.__dict__.update(pulled_survey.__dict__)
            return

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

        self.name = name

        # Set through descriptor (handles validation and None -> [] conversion)
        self.questions_to_randomize = questions_to_randomize

        self.options_to_pin: Dict[str, List] = options_to_pin or {}

        self._seed: Optional[int] = None

        # Cache the InstructionCollection
        self._cached_instruction_collection: Optional[InstructionCollection] = None

        self._exporter = SurveyExport(self)
        self._navigator = SurveyNavigator(self)
        self._editor = EditSurvey(self)
        self._group_manager = QuestionGroupManager(self)

        if not _internal_copy:
            # Validate survey structure (e.g., check for forward piping references)
            # This will raise SurveyPipingReferenceError if questions are in wrong order
            self.dag()

    def clipboard_data(self) -> str:
        """Return a human-readable string of all questions for clipboard use.

        Returns:
            A newline-separated string of each question's human-readable form.

        Example:
            >>> s = Survey.example()
            >>> 'Do you like school?' in s.clipboard_data()
            True
        """
        text = []
        for question in self.questions:
            text.append(question.human_readable())
        return "\n\n".join(text)

    def question_names_valid(self) -> bool:
        """Check whether every question name in the survey is valid.

        Returns:
            True if all question names pass validation, False otherwise.

        Example:
            >>> Survey.example().question_names_valid()
            True
        """
        return all(q.is_valid_question_name() for q in self.questions)

    def question_to_attributes(self) -> dict:
        """Return a mapping of question names to their core attributes.

        Returns:
            A dict keyed by question_name, each value a dict with
            ``question_text``, ``question_type``, and ``question_options``.

        Example:
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
        """Return a new survey with randomly permuted options for randomized questions.

        Returns:
            A new Survey with independently duplicated questions, where
            questions in ``questions_to_randomize`` have shuffled options.

        Example:
            >>> s = Survey.example()
            >>> drawn = s.draw()
            >>> drawn.question_names == s.question_names
            True
            >>> drawn is not s
            True
        """
        if self._seed is None:  # only set once
            self._seed = hash(self)
            random.seed(self._seed)

        # Always create new questions to avoid sharing state between interviews
        # This is necessary even when there's no randomization because:
        # 1. Piping might require each interview to have its own survey instance
        # 2. Different agents/scenarios need independent survey instances
        new_questions = []
        for question in self.questions:
            if question.question_name in self.questions_to_randomize:
                pin = self.options_to_pin.get(question.question_name, None)
                new_questions.append(question.draw(pin_options=pin))
            else:
                new_questions.append(question.duplicate())

        d = self.to_dict()
        d["questions"] = [q.to_dict() for q in new_questions]
        new_survey = Survey.from_dict(d, _internal_copy=True)

        # Preserve any non-serialized attributes from the new_questions
        for i, new_question in enumerate(new_questions):
            survey_question = new_survey.questions[i]
            if hasattr(new_question, "exception_to_throw"):
                survey_question.exception_to_throw = new_question.exception_to_throw
            if hasattr(new_question, "override_answer"):
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
            self._instruction_names_to_instructions = result.instruction_names_to_instructions
            self._pseudo_indices = PseudoIndices(result.pseudo_indices)
            return result.true_questions
        else:
            # For older versions that return a tuple
            # This is a hacky way to get mypy to allow tuple unpacking of an Any type
            result_list = list(result)
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

    def show_flow(self, filename: Optional[str] = None, renderer: Optional[str] = None):
        """Show the flow of the survey.

        Args:
            filename: Optional path to save the output.
            renderer: "mermaid" or "pydot" (default: auto-detect).
        """
        from edsl.surveys.extras.survey_flow_visualization import (
            SurveyFlowVisualization,
        )

        return SurveyFlowVisualization(self).show_flow(
            filename=filename, renderer=renderer
        )

    def add_instruction(
        self, instruction: Union["Instruction", "ChangeInstruction"]
    ) -> Survey:
        """Add an instruction to the survey.

        Args:
            instruction: The instruction to add to the survey.

        Returns:
            The modified survey instance (supports chaining).

        Example:
            >>> from edsl import Instruction
            >>> i = Instruction(text="Pay attention to the following questions.", name="intro")
            >>> s = Survey().add_instruction(i)
            >>> s._instruction_names_to_instructions
            {'intro': Instruction(name="intro", text="Pay attention to the following questions.")}
            >>> s._pseudo_indices
            {'intro': -0.5}
        """
        return self._editor.add_instruction(instruction)

    def _get_question_index(
        self, q: Union["QuestionBase", str, EndOfSurveyParent]
    ) -> Union[int, EndOfSurveyParent]:
        """Return the index of a question, or EndOfSurvey if appropriate.

        Accepts a question name string, a QuestionBase object, or the
        EndOfSurvey sentinel.

        Args:
            q: The question (name, object, or EndOfSurvey) to look up.

        Returns:
            The integer index of the question, or EndOfSurvey.

        Raises:
            SurveyError: If the question name is not found in the survey.

        Example:
            >>> s = Survey.example()
            >>> s._get_question_index("q0")
            0
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
        """Return the question object for the given name.

        Args:
            question_name: The name of the question to retrieve.

        Returns:
            The matching QuestionBase instance.

        Raises:
            SurveyError: If the question name is not found.

        Example:
            >>> s = Survey.example()
            >>> s._get_question_by_name("q0")
            Question('multiple_choice', question_name = \"""q0\""", question_text = \"""Do you like school?\""", question_options = ['yes', 'no'])
        """
        if question_name not in self.question_name_to_index:
            raise SurveyError(f"Question name {question_name} not found in survey.")
        return self.questions[self.question_name_to_index[question_name]]

    def get(self, question_name: str) -> QuestionBase:
        """Return the question object for the given name.

        Args:
            question_name: The name of the question to retrieve.

        Returns:
            The matching QuestionBase instance.

        Raises:
            SurveyError: If the question name is not found.

        Example:
            >>> s = Survey.example()
            >>> s.get('q0').question_text
            'Do you like school?'
        """
        return self._get_question_by_name(question_name)

    def question_names_to_questions(self) -> dict:
        """Return a dictionary mapping question names to question objects.

        Returns:
            A dict keyed by question_name with QuestionBase values.

        Example:
            >>> s = Survey.example()
            >>> list(s.question_names_to_questions().keys())
            ['q0', 'q1', 'q2']
        """
        if not hasattr(self, "_cached_qname_to_q"):
            self._cached_qname_to_q = {q.question_name: q for q in self.questions}
        return self._cached_qname_to_q

    @property
    def question_names(self) -> list[str]:
        """Return a list of question names in the survey.

        Example:

        >>> s = Survey.example()
        >>> s.question_names
        ['q0', 'q1', 'q2']
        """
        if not hasattr(self, "_cached_question_names"):
            self._cached_question_names = [q.question_name for q in self.questions]
        return self._cached_question_names

    @property
    def question_name_to_index(self) -> dict[str, int]:
        """Return a dictionary mapping question names to question indices.

        Example:

        >>> s = Survey.example()
        >>> s.question_name_to_index
        {'q0': 0, 'q1': 1, 'q2': 2}
        """
        if not hasattr(self, "_cached_qname_to_index"):
            self._cached_qname_to_index = {
                q.question_name: i for i, q in enumerate(self.questions)
            }
        return self._cached_qname_to_index

    def to_long_format(
        self, scenario_list: "ScenarioList"
    ) -> Tuple[List[QuestionBase], ScenarioList]:
        """Expand loop templates into per-scenario questions (long format).

        Args:
            scenario_list: The scenarios to expand against.

        Returns:
            A tuple of (expanded questions list, expanded ScenarioList).
        """

        from ..questions.loop_processor import LongSurveyLoopProcessor

        lp = LongSurveyLoopProcessor(self, scenario_list)
        return lp.process_templates_for_all_questions()

    def to_dict(self, add_edsl_version: bool = True) -> dict[str, Any]:
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

        # Include pinned options if present
        if self.options_to_pin:
            d["options_to_pin"] = self.options_to_pin

        # Add version information if requested
        if add_edsl_version:
            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Survey"

        return d

    def to_jsonl(self, filename=None, **kwargs):
        """Export the Survey as JSONL.

        >>> sv = Survey.example()
        >>> sv2 = Survey.from_jsonl(sv.to_jsonl())
        >>> sv == sv2
        True
        """
        from .survey_serializer import SurveySerializer

        return SurveySerializer(self).to_jsonl(filename=filename)

    def to_jsonl_rows(self, blob_writer=None):
        """Return the survey as a list of JSONL row dicts for serialization."""
        from .survey_serializer import SurveySerializer
        return SurveySerializer(self).to_jsonl_rows()

    @classmethod
    def from_jsonl(cls, source, **kwargs):
        """Create a Survey from a JSONL source (file path, string, or iterable)."""
        from .survey_serializer import SurveySerializer

        return SurveySerializer.from_jsonl(source)

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict, _internal_copy: bool = False) -> Survey:
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
        questions = []
        question_dicts = data.get("questions", None)
        if question_dicts is None:
            raise SurveyError(
                f"No questions found in the survey dictionary. The keys are {data.keys()}"
            )
        for q_dict in data["questions"]:
            cls_type = get_class(q_dict)
            questions.append(cls_type.from_dict(q_dict))

        # Deserialize the memory plan
        memory_plan = MemoryPlan.from_dict(data["memory_plan"])

        # Get the list of questions to randomize if present
        if "questions_to_randomize" in data:
            questions_to_randomize = data["questions_to_randomize"]
        else:
            questions_to_randomize = None

        # Get the pinned options if present
        options_to_pin = data.get("options_to_pin", None)

        if "name" in data:
            name = data["name"]
        else:
            name = None

        # Inject question_name_to_index into rule_collection dict if missing or empty
        # This provides backwards compatibility for older serialized formats
        rule_collection_data = data["rule_collection"]
        if not rule_collection_data.get("question_name_to_index"):
            rule_collection_data["question_name_to_index"] = {
                q.question_name: i for i, q in enumerate(questions)
            }

        # Create and return the reconstructed survey
        rule_collection = RuleCollection.from_dict(rule_collection_data)

        survey = cls(
            questions=questions,
            memory_plan=memory_plan,
            rule_collection=rule_collection,
            question_groups=data["question_groups"],
            questions_to_randomize=questions_to_randomize,
            name=name,
            options_to_pin=options_to_pin,
            _internal_copy=_internal_copy,
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
        >>> q = QuestionFreeText(question_name = "example", question_text = "What is the capital of {{ country }}?")
        >>> s = Survey([q])
        >>> s.parameters_by_question
        {'example': {'country'}}
        """
        return {q.question_name: q.parameters for q in self.questions}

    def __add__(self, other: Survey) -> Survey:
        """Combine two surveys into one by concatenating their questions.

        Both surveys must have only default rules (no skip/jump logic).

        Args:
            other: The survey to append after this one.

        Returns:
            A new Survey containing questions from both surveys.

        Raises:
            SurveyCreationError: If either survey has non-default rules.

        Example:
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
        """Move a question to a new position in the survey.

        Args:
            identifier: The question name or current index to move.
            new_index: The target position index.

        Returns:
            The modified survey instance.

        Example:
            >>> from edsl import QuestionMultipleChoice, Survey
            >>> s = Survey.example()
            >>> s.question_names
            ['q0', 'q1', 'q2']
            >>> s.move_question("q0", 2).question_names
            ['q1', 'q2', 'q0']
        """
        return self._editor.move_question(identifier, new_index)

    def delete_question(self, identifier: Union[str, int]) -> Survey:
        """Delete a question from the survey.

        Args:
            identifier: The name or index of the question to delete.

        Returns:
            The updated Survey object.

        Example:
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
        return self._editor.delete_question(identifier)

    def add_question(
        self, question: QuestionBase, index: Optional[int] = None
    ) -> Survey:
        return self._editor.add_question(question, index)

    add_question.__doc__ = EditSurvey.add_question.__doc__

    def combine_multiple_choice_to_matrix(
        self,
        question_names: List[str],
        matrix_question_name: str,
        matrix_question_text: Optional[str] = None,
        use_question_text_as_items: bool = True,
        remove_original_questions: bool = True,
        index: Optional[int] = None,
        **kwargs,
    ) -> "Survey":
        """
        Combine multiple choice questions into a single matrix question.

        This is useful when importing surveys from platforms like Qualtrics or SurveyMonkey
        where matrix questions are sometimes broken down into separate multiple choice questions.

        Args:
            question_names: List of question names to combine into a matrix
            matrix_question_name: Name for the new matrix question
            matrix_question_text: Text for the new matrix question. If None, will attempt to
                                  infer from the common prefix of existing question texts.
            use_question_text_as_items: If True, uses question_text as matrix items.
                                       If False, uses question_name as matrix items.
                                       When matrix_question_text is None and this is True,
                                       the items will be auto-extracted from question texts.
            remove_original_questions: If True, removes the original questions after combining
            index: Position to insert the matrix question. If None, adds at the end.
            **kwargs: Additional arguments to pass to QuestionMatrix constructor

        Returns:
            Survey: A new Survey object with the matrix question

        Raises:
            ValueError: If questions don't exist, aren't multiple choice, or have incompatible options

        Examples:
            >>> from edsl import Survey, QuestionMultipleChoice

            # Example 1: Explicit matrix question text
            >>> q1 = QuestionMultipleChoice("satisfaction_work", "How satisfied are you with work?", ["Very satisfied", "Somewhat satisfied", "Not satisfied"])
            >>> q2 = QuestionMultipleChoice("satisfaction_pay", "How satisfied are you with pay?", ["Very satisfied", "Somewhat satisfied", "Not satisfied"])
            >>> survey = Survey().add_question(q1).add_question(q2)
            >>> new_survey = survey.combine_multiple_choice_to_matrix(
            ...     question_names=["satisfaction_work", "satisfaction_pay"],
            ...     matrix_question_name="satisfaction_matrix",
            ...     matrix_question_text="How satisfied are you with each aspect?"
            ... )

            # Example 2: Auto-inferred matrix question text
            >>> q1 = QuestionMultipleChoice("trust1", "Overall, how much would you trust: - A freelancer without AI", ["High", "Medium", "Low"])
            >>> q2 = QuestionMultipleChoice("trust2", "Overall, how much would you trust: - A freelancer with AI", ["High", "Medium", "Low"])
            >>> survey = Survey().add_question(q1).add_question(q2)
            >>> new_survey = survey.combine_multiple_choice_to_matrix(
            ...     question_names=["trust1", "trust2"],
            ...     matrix_question_name="trust_matrix"
            ...     # matrix_question_text will be inferred as "Overall, how much would you trust"
            ...     # matrix items will be ["A freelancer without AI", "A freelancer with AI"]
            ... )
        """
        from .matrix_combiner import combine_multiple_choice_to_matrix

        return combine_multiple_choice_to_matrix(
            survey=self,
            question_names=question_names,
            matrix_question_name=matrix_question_name,
            matrix_question_text=matrix_question_text,
            use_question_text_as_items=use_question_text_as_items,
            remove_original_questions=remove_original_questions,
            index=index,
            **kwargs,
        )

    def _resolve_and_validate_questions(
        self,
        include: Optional[List[Union[str, "QuestionBase"]]],
        allowed_types: tuple,
        empty_error: str,
        *,
        extra_validators: Optional[List[Callable]] = None,
        auto_filter: Optional[Callable] = None,
    ) -> List["QuestionBase"]:
        """Resolve and validate a list of questions by name or object.

        Args:
            include: Question names or objects to include, or None to auto-select.
            allowed_types: Tuple of allowed question_type strings.
            empty_error: Error message when no questions match.
            extra_validators: Optional callables that take a question and raise
                SurveyCreationError if invalid.
            auto_filter: Optional callable to filter self.questions when include
                is None. If not provided, filters by allowed_types.

        Returns:
            A list of validated QuestionBase objects.
        """
        if include is None:
            if auto_filter is not None:
                included_questions = [q for q in self.questions if auto_filter(q)]
            else:
                included_questions = [
                    q
                    for q in self.questions
                    if getattr(q, "question_type", None) in allowed_types
                ]
        else:
            name_to_q = self.question_names_to_questions()
            included_questions = []
            for item in include:
                if isinstance(item, str):
                    if item not in name_to_q:
                        raise SurveyCreationError(
                            f"Question '{item}' not found in survey."
                        )
                    q_obj = name_to_q[item]
                else:
                    q_obj = item

                if getattr(q_obj, "question_type", None) not in allowed_types:
                    type_desc = "' or '".join(allowed_types)
                    raise SurveyCreationError(
                        f"Question '{q_obj.question_name}' must be of type '{type_desc}'."
                    )
                for validator in extra_validators or []:
                    validator(q_obj)
                included_questions.append(q_obj)

        if not included_questions:
            raise SurveyCreationError(empty_error)

        return included_questions

    def add_summation_question(
        self,
        question_name: str = "total_score",
        include: Optional[List[Union[str, "QuestionBase"]]] = None,
    ) -> "Survey":
        """Add a compute question that sums answers from prior numeric questions.

        This convenience method appends a `compute` question that renders the sum of
        answers from all previous questions of type `numerical` or `linear_scale`.
        Optionally, pass a subset to include. Prior answers are available automatically
        to the compute template; no extra memory wiring is required.

        Args:
            question_name: Name for the new compute question.
            include: Optional list of question names or question objects to include;
                if omitted, all prior `numerical` and `linear_scale` questions are used.

        Returns:
            Survey: The updated survey (supports chaining).

        Raises:
            SurveyCreationError: If any included question is not of an
                allowed type, or if none are available.

        Example:
            Adds a `total_score` question that sums prior numeric answers.
        """
        included_questions = self._resolve_and_validate_questions(
            include,
            allowed_types=("numerical", "linear_scale"),
            empty_error="No prior 'numerical' or 'linear_scale' questions available to sum.",
        )

        answers_expr = ", ".join(
            f"{q.question_name}.answer" for q in included_questions
        )
        question_text = (
            f"{{% set numbers = [{answers_expr}] %}}\n"
            "{{ numbers | sum }}"
        )

        from ..questions import QuestionCompute

        compute_q = QuestionCompute(
            question_name=question_name, question_text=question_text
        )
        return self.add_question(compute_q)

    def add_weighted_linear_scale_sum(
        self,
        question_name: str = "weighted_score",
        include: Optional[List[Union[str, "QuestionBase"]]] = None,
    ) -> "Survey":
        """Add a compute question that sums weighted answers from linear_scale questions.

        This method creates a QuestionCompute that iterates through all linear_scale
        questions (or a specified subset), multiplying each answer by its weight
        (if provided) and summing the results. Questions without a weight are skipped.

        Args:
            question_name: Name for the new compute question.
            include: Optional list of question names or question objects to include;
                if omitted, all prior `linear_scale` questions with weights are used.

        Returns:
            Survey: The updated survey (supports chaining).

        Raises:
            SurveyCreationError: If any included question is not of type linear_scale,
                or if none with weights are available.

        Example:
            >>> from edsl import Survey
            >>> from edsl.questions import QuestionLinearScale
            >>> s = Survey()
            >>> s = s.add_question(QuestionLinearScale(
            ...     question_name="q1",
            ...     question_text="Quality?",
            ...     question_options=[1, 2, 3, 4, 5],
            ...     weight=2.0
            ... ))
            >>> s = s.add_question(QuestionLinearScale(
            ...     question_name="q2",
            ...     question_text="Speed?",
            ...     question_options=[1, 2, 3, 4, 5],
            ...     weight=1.5
            ... ))
            >>> s = s.add_weighted_linear_scale_sum()
        """
        def _require_weight(q_obj):
            if getattr(q_obj, "_weight", None) is None:
                raise SurveyCreationError(
                    f"Question '{q_obj.question_name}' must have a weight."
                )

        included_questions = self._resolve_and_validate_questions(
            include,
            allowed_types=("linear_scale",),
            empty_error="No prior 'linear_scale' questions with weights available.",
            extra_validators=[_require_weight],
            auto_filter=lambda q: (
                getattr(q, "question_type", None) == "linear_scale"
                and getattr(q, "_weight", None) is not None
            ),
        )

        weighted_values = []
        for q in included_questions:
            weight = getattr(q, "_weight")
            weighted_values.append(f"({q.question_name}.answer * {weight})")

        question_text = (
            f"{{% set weighted_values = [{', '.join(weighted_values)}] %}}\n"
            "{{ weighted_values | sum }}"
        )

        from ..questions import QuestionCompute

        compute_q = QuestionCompute(
            question_name=question_name, question_text=question_text
        )
        return self.add_question(compute_q)

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

    # Keep as internal-only — only called from within edsl/surveys/
    recombined_questions_and_instructions = _recombined_questions_and_instructions

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

            >>> from edsl.questions import QuestionMultipleChoice
            >>> q0 = QuestionMultipleChoice(question_name="q0", question_text="Age?", question_options=["18-30", "31-50", "50+"])
            >>> q1 = QuestionMultipleChoice(question_name="q1", question_text="Gender?", question_options=["Male", "Female", "Other"])
            >>> s = Survey(questions=[q0, q1]).add_question_group("q0", "q1", "demographics")
            >>> s.question_groups
            {'demographics': (0, 1)}

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
        return self._group_manager.add_question_group(
            start_question, end_question, group_name
        )

    def _suggest_dependency_aware_groups(self, group_name_prefix: str = "group") -> dict:
        """Suggest valid question groups that respect dependency constraints.

        This method analyzes the survey's dependency graph to suggest question groups
        where every question in a group can be fully rendered without depending on
        any other question in the same group.

        Args:
            group_name_prefix: Prefix for suggested group names.

        Returns:
            dict: A dictionary mapping suggested group names to (start_idx, end_idx) tuples.

        Examples:
            >>> from edsl import Survey, QuestionFreeText
            >>> q1 = QuestionFreeText(question_text="What's your name?", question_name="q1")
            >>> q2 = QuestionFreeText(question_text="What's your age?", question_name="q2")
            >>> q3 = QuestionFreeText(question_text="Hi {{q1}}, based on your age {{q2}}, ...", question_name="q3")
            >>> s = Survey([q1, q2, q3])
            >>> suggestions = s._suggest_dependency_aware_groups("section")
            >>> # Might return: {"section_0": (0, 1), "section_1": (2, 2)}
        """
        return self._group_manager.suggest_dependency_aware_groups(group_name_prefix)

    # Keep public alias for backward compatibility
    suggest_dependency_aware_groups = _suggest_dependency_aware_groups

    def create_allowable_groups(
        self, group_name_prefix: str = "group", max_group_size: Optional[int] = None
    ) -> Survey:
        """Create and apply allowable question groups that respect dependency constraints.

        This method automatically creates and applies question groups to the survey,
        ensuring that every question in a group can be fully rendered without depending
        on any other question in the same group. Optionally limits the maximum size of
        each group.

        Args:
            group_name_prefix: Prefix for automatically generated group names.
                Groups will be named as "{prefix}_0", "{prefix}_1", etc.
            max_group_size: Maximum number of questions allowed in each group.
                If None, groups can be any size that respects dependencies.
                If specified, groups will be split when they exceed this size.

        Returns:
            Survey: The modified survey instance with new dependency-aware groups applied.

        Examples:
            Create groups with no size limit:
            >>> from edsl.questions import QuestionMultipleChoice
            >>> q1 = QuestionMultipleChoice(question_name="q1", question_text="Age?", question_options=["18-30", "31-50", "50+"])
            >>> q2 = QuestionMultipleChoice(question_name="q2", question_text="Gender?", question_options=["Male", "Female", "Other"])
            >>> q3 = QuestionMultipleChoice(question_name="q3", question_text="Income?", question_options=["Low", "Medium", "High"])
            >>> q4 = QuestionMultipleChoice(question_name="q4", question_text="Location?", question_options=["Urban", "Suburban", "Rural"])
            >>> survey = Survey([q1, q2, q3, q4])
            >>> survey.create_allowable_groups("section") # doctest: +ELLIPSIS
            Survey(...)

            Create groups with maximum 2 questions each:
            >>> survey = Survey([q1, q2, q3, q4])
            >>> survey.create_allowable_groups("part", max_group_size=2) # doctest: +ELLIPSIS
            Survey(...)

            Create single-question groups only:
            >>> survey = Survey([q1, q2, q3, q4])
            >>> survey.create_allowable_groups("individual", max_group_size=1) # doctest: +ELLIPSIS
            Survey(...)
        """
        return self._group_manager.create_allowable_groups(
            group_name_prefix, max_group_size
        )

    def show_rules(self) -> None:
        """Print the rule collection as a Dataset.

        Example:
            >>> s = Survey.example()
        >>> s.show_rules()
        Dataset([{'current_q': [0, 0, 1, 2]}, {'expression': ['True', "{{ q0.answer }}== 'yes'", 'True', 'True']}, {'next_q': [1, 2, 2, 3]}, {'priority': [-1, 0, -1, -1]}, {'before_rule': [False, False, False, False]}])
        """
        return self.rule_collection.show_rules()

    def add_stop_rule(
        self, question: Union[QuestionBase, str], expression: str
    ) -> Survey:
        """Add a rule that ends the survey when the expression is true.

        The rule is evaluated *after* the question is answered.

        Args:
            question: The question to attach the stop rule to.
            expression: A conditional expression; if it evaluates to True
                the survey ends.

        Returns:
            The modified survey instance (supports chaining).

        Example:
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
        """Return a new survey with all non-default (skip/jump) rules removed.

        Returns:
            A new Survey with the same questions but only default sequential rules.

        Example:
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

    def add_followup_questions(
        self,
        reference_question: Union["QuestionBase", str],
        followup_template: "QuestionBase",
        answer_template_var: str = "answer",
    ) -> "Survey":
        """Add follow-up questions for each option in a reference question with skip logic.

        This method provides syntactical sugar for creating conditional follow-up questions
        based on a multiple choice or checkbox question's options. For each option in the
        reference question, it creates a follow-up question and adds the appropriate skip
        logic to show it only when that option is selected.

        The method automatically:
        1. Creates one follow-up question per option in the reference question
        2. Substitutes the template variable with each option value
        3. Adds skip logic so each follow-up only appears for its corresponding option
        4. Maintains proper survey flow after all follow-ups

        Args:
            reference_question: The question with options (must be MultipleChoice or CheckBox type).
                Can be specified as a QuestionBase object or its question_name string.
            followup_template: A template question to use for follow-ups. The question text
                can include `{{ <ref_name>.<template_var> }}` which will be replaced with
                each option value. For example, `{{ restaurants.answer }}` will be replaced
                with "Italian", "Chinese", etc.
            answer_template_var: The template variable name to replace in the followup text
                (default: "answer"). This is the part after the dot in the template syntax.

        Returns:
            Survey: The modified survey with follow-up questions added.

        Raises:
            ValueError: If the reference question doesn't have options (not MultipleChoice
                or CheckBox type).

        Examples:
            Basic usage with multiple choice question:

            >>> from edsl import QuestionMultipleChoice, QuestionFreeText, Survey
            >>> q_rest = QuestionMultipleChoice(
            ...     question_name="restaurants",
            ...     question_text="Which restaurant do you prefer?",
            ...     question_options=["Italian", "Chinese", "Mexican"]
            ... )
            >>> q_followup = QuestionFreeText(
            ...     question_name="why_restaurant",
            ...     question_text="Why do you like {{ restaurants.answer }}?"
            ... )
            >>> s = Survey([q_rest]).add_followup_questions("restaurants", q_followup)
            >>> len(s.questions)
            4

            The survey will now have 4 questions:
            - restaurants (the original multiple choice)
            - why_restaurant_restaurants_0 (shown only if "Italian" selected)
            - why_restaurant_restaurants_1 (shown only if "Chinese" selected)
            - why_restaurant_restaurants_2 (shown only if "Mexican" selected)

            Each follow-up will have the option value substituted in its text:
            - "Why do you like Italian?"
            - "Why do you like Chinese?"
            - "Why do you like Mexican?"
        """
        from .followup_questions import FollowupQuestionAdder

        return FollowupQuestionAdder.add_followup_questions(
            self, reference_question, followup_template, answer_template_var
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
            Create a runnable Jobs object with an agent:

            >>> s = Survey.example()
            >>> from edsl.agents import Agent
            >>> s.by(Agent.example())
            Jobs(...)

            Chain all components in a single call:

            >>> from edsl.language_models import LanguageModel
            >>> s.by(Agent.example(), LanguageModel.example())
            Jobs(...)
        """
        from edsl.jobs import Jobs

        return Jobs(survey=self).by(*args)

    def gold_standard(self, q_and_a_dict: dict[str, str]) -> "Result":
        """Run the survey with predetermined answers and return the result.

        Args:
            q_and_a_dict: A mapping of question names to their expected answers.
                Must contain exactly the same keys as ``self.question_names``.

        Returns:
            A single Result object produced by the gold-standard agent.

        Raises:
            ValueError: If the keys of q_and_a_dict don't match the survey's
                question names.
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

        gold_agent.add_direct_question_answering_method(f)  # type: ignore[arg-type]
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

            >>> from edsl.questions import QuestionFunctional  # doctest: +SKIP
            >>> def f(scenario, agent_traits): return "yes" if scenario["period"] == "morning" else "no"  # doctest: +SKIP
            >>> q = QuestionFunctional(question_name="q0", func=f)  # doctest: +SKIP
            >>> s = Survey([q])  # doctest: +SKIP
            >>> s(period="morning", cache=False, disable_remote_cache=True, disable_remote_inference=True).select("answer.q0").first()  # doctest: +SKIP
            'yes'
            >>> s(period="evening", cache=False, disable_remote_cache=True, disable_remote_inference=True).select("answer.q0").first()  # doctest: +SKIP
            'no'
        """
        return self._get_job(model, agent, **kwargs).run(
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

        jobs: "Jobs" = self._get_job(model=model, agent=agent, **scenario_kwargs).using(
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
        """Convert to a Jobs object and attach the given resource.

        Args:
            obj: A Cache, KeyLookup, or BucketCollection to attach.

        Returns:
            A Jobs object configured with the provided resource.
        """
        from ..jobs.Jobs import Jobs

        return Jobs(survey=self).using(obj)

    def duplicate(self, add_edsl_version=False):
        """Create an independent copy of the survey via serialization round-trip.

        Returns:
            A new Survey instance equal to but not identical to this one.

        Example:
            >>> s = Survey.example()
        >>> s2 = s.duplicate()
        >>> s == s2
        True
        >>> s is s2
        False

        """
        return self.copy()

    def next_question(
        self,
        current_question: Optional[Union[str, "QuestionBase"]] = None,
        answers: Optional[Dict[str, Any]] = None,
    ) -> Union["QuestionBase", EndOfSurveyParent]:
        """Return the next question in the survey based on rules and answers.

        If called with no arguments, returns the first question. When answers
        are provided, skip/jump rules are evaluated to determine the next
        question. Returns EndOfSurvey when no more questions remain.

        Args:
            current_question: The current question (name or object). If None,
                returns the first question.
            answers: Accumulated answers so far, used to evaluate rules.

        Returns:
            The next QuestionBase, or EndOfSurvey if the survey is complete.

        Example:
            >>> s = Survey.example()
        >>> s.next_question("q0", {"q0.answer": "yes"}).question_name
        'q2'
        >>> s.next_question("q0", {"q0.answer": "no"}).question_name
        'q1'

        """
        return self._navigator.next_question(current_question, answers)

    def next_question_group(
        self,
        current_question: Optional[Union[str, "QuestionBase"]] = None,
        answers: Optional[Dict[str, Any]] = None,
    ) -> Optional[Tuple[str, List[Union["QuestionBase", EndOfSurveyParent]]]]:
        """
        Find the next question group and return its name along with all renderable questions in it.

        This method handles the complexity that even if questions within a group have no internal
        dependencies, some questions in the group might be skipped due to rules based on answers
        from previous groups. It returns all non-skipped questions in the group so the UI can
        render them all at once.

        Args:
            current_question: The current question in the survey. If None, finds the first group.
            answers: The answers for the survey so far, used to evaluate skip rules.

        Returns:
            A tuple of (group_name, list_of_renderable_questions) or None if no more groups.
            The list contains all questions in the group that would not be skipped, in order.
            If the entire group is skipped, returns (group_name, [EndOfSurvey]).

        Examples:
            >>> from edsl.questions import QuestionMultipleChoice
            >>> q1 = QuestionMultipleChoice(question_name="q1", question_text="Age?", question_options=["18-30", "31-50", "50+"])
            >>> q2 = QuestionMultipleChoice(question_name="q2", question_text="Gender?", question_options=["Male", "Female", "Other"])
            >>> survey = Survey([q1, q2])
            >>> _ = survey.create_allowable_groups("section", max_group_size=2)
            >>> result = survey.next_question_group(None, {})  # Get first group
            >>> result[0]  # Group name
            'section_0'
        """
        return self._navigator.next_question_group(current_question, answers)

    def get_question_group(self, question: Union[str, "QuestionBase"]) -> Optional[str]:
        """
        Get the group name that contains the specified question.

        Args:
            question: The question to find the group for, either as a question name string
                     or a QuestionBase object.

        Returns:
            The name of the group containing the question, or None if the question
            is not in any group.

        Examples:
            >>> from edsl.questions import QuestionMultipleChoice
            >>> q1 = QuestionMultipleChoice(question_name="q1", question_text="Age?", question_options=["18-30", "31-50", "50+"])
            >>> q2 = QuestionMultipleChoice(question_name="q2", question_text="Gender?", question_options=["Male", "Female", "Other"])
            >>> q3 = QuestionMultipleChoice(question_name="q3", question_text="Income?", question_options=["Low", "Medium", "High"])
            >>> q4 = QuestionMultipleChoice(question_name="q4", question_text="Location?", question_options=["Urban", "Suburban", "Rural"])
            >>> survey = Survey([q1, q2, q3, q4])
            >>> _ = survey.create_allowable_groups("section", max_group_size=2)
            >>> survey.get_question_group("q1")
            'section_0'
            >>> survey.get_question_group("q3")
            'section_1'
        """
        return self._navigator.get_question_group(question)

    def next_question_with_instructions(
        self,
        current_item: Optional[Union[str, "QuestionBase", "Instruction"]] = None,
        answers: Optional[Dict[str, Any]] = None,
    ) -> Union["QuestionBase", "Instruction", EndOfSurveyParent]:
        """Return the next question or instruction in sequence.

        Extends ``next_question`` to also yield Instruction objects interspersed
        between questions. Follows pseudo-index ordering and respects survey rules.

        Args:
            current_item: The current question or instruction. If None, returns
                the first item in the survey.
            answers: Accumulated answers so far, used to evaluate rules.

        Returns:
            The next QuestionBase, Instruction, or EndOfSurvey.

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
        return self._navigator.next_question_with_instructions(current_item, answers)

    def next_question_group_with_instructions(
        self,
        current_item: Optional[Union[str, "QuestionBase", "Instruction"]] = None,
        answers: Optional[Dict[str, Any]] = None,
    ) -> Optional[Tuple[str, List[Union["QuestionBase", EndOfSurveyParent]]]]:
        """
        Find the next question group, handling both questions and instructions.

        This method extends next_question_group to handle instructions as current items.
        If the current item is an instruction, it finds the next question group that comes
        after that instruction in the survey sequence.

        Args:
            current_item: The current question or instruction in the survey. If None, finds the first group.
            answers: The answers for the survey so far, used to evaluate skip rules.

        Returns:
            A tuple of (group_name, list_of_renderable_questions) or None if no more groups.
            The list contains all questions in the group that would not be skipped, in order.
            If the entire group is skipped, returns (group_name, [EndOfSurvey]).

        Examples:
            >>> from edsl import Survey, Instruction
            >>> from edsl.questions import QuestionMultipleChoice
            >>> i = Instruction(name="intro", text="Please answer.")
            >>> q1 = QuestionMultipleChoice(question_name="q1", question_text="Age?", question_options=["18-30", "31-50"])
            >>> q2 = QuestionMultipleChoice(question_name="q2", question_text="Gender?", question_options=["Male", "Female"])
            >>> survey = Survey([i, q1, q2])
            >>> _ = survey.create_allowable_groups("section", max_group_size=2)
            >>> result = survey.next_question_group_with_instructions(i, {})
            >>> result[0]  # Group name
            'section_0'
        """
        return self._navigator.next_question_group_with_instructions(
            current_item, answers
        )

    def next_questions_with_instructions(
        self,
        current_item: Optional[Union[str, "QuestionBase", "Instruction"]] = None,
        answers: Optional[Dict[str, Any]] = None,
    ) -> List[Union["QuestionBase", "Instruction", EndOfSurveyParent]]:
        """
        Return a list of questions and instructions from the next question group, or the next question/instruction.

        This method first checks for the next question group. If a group exists, it returns all
        questions and instructions (in order) that fall within that group's range. If no group
        exists, it falls back to returning the next single question or instruction.

        Args:
            current_item: The current question or instruction in the survey. If None, finds the first group or item.
            answers: The answers for the survey so far, used to evaluate skip rules.

        Returns:
            A list of QuestionBase and/or Instruction objects from the next question group,
            or a list containing the next single question/instruction if no group exists.
            The list will contain [EndOfSurvey] if the survey has ended.

        Examples:
            >>> from edsl import Survey, Instruction
            >>> from edsl.questions import QuestionMultipleChoice
            >>> q1 = QuestionMultipleChoice(question_name="q1", question_text="Age?", question_options=["18-30", "31-50", "50+"])
            >>> q2 = QuestionMultipleChoice(question_name="q2", question_text="Gender?", question_options=["Male", "Female", "Other"])
            >>> i = Instruction(name="intro", text="Please answer the following questions.")
            >>> survey = Survey([i, q1, q2])
            >>> _ = survey.create_allowable_groups("section", max_group_size=2)
            >>> result = survey.next_questions_with_instructions(None, {})  # Get first group
            >>> len(result)  # Should include instruction and questions from the group
            3
        """
        return self._navigator.next_questions_with_instructions(current_item, answers)

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
        return self._navigator.gen_path_through_survey()

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
        """Create a new Survey containing only the specified questions.

        Args:
            selected_questions: Question objects to include in the sub-survey.

        Returns:
            A new Survey with fresh rules/memory appropriate for the subset.
        """
        # Create new survey with selected questions
        new_survey = Survey(questions=selected_questions)  # type: ignore[arg-type]

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
        """Return question(s) or a sub-survey by index, name, slice, or name list.

        Args:
            index: An int (position), str (name), slice, or list of name strings.

        Returns:
            A single QuestionBase for int/str, or a new Survey for slice/list.

        Raises:
            KeyError: If a question name is not found.
            TypeError: If the index type is unsupported.

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

    def select(self, *args, **kwargs) -> "Dataset":
        """Select columns from the survey's info Dataset.

        Returns:
            A filtered Dataset with the selected columns.

        Example:
            >>> s = Survey.example()
            >>> ds = s.select('question_name')
            >>> ds
            Dataset([{'question_name': ['q0', 'q1', 'q2']}])
        """
        return self.info()[0][1].select(*args, **kwargs)

    def subset(self, *question_names: str) -> "Survey":
        """Create a new Survey containing only the named questions.

        Args:
            *question_names: One or more question names to keep.

        Returns:
            A new Survey with only the specified questions.

        Raises:
            ValueError: If no question names are provided.

        Example:
            >>> s = Survey.example()
            >>> s.subset('q0', 'q2').question_names
            ['q0', 'q2']
        """
        if not question_names:
            raise ValueError("At least one question name must be provided")

        kept_questions = [self.get(name) for name in question_names]
        assert all(kept_questions), f"Question(s) {question_names} not found in survey"
        return Survey(questions=kept_questions)  # type: ignore[arg-type]

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

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the survey.

        This representation can be used with eval() to recreate the Survey object.
        Used primarily for doctests and debugging.
        """
        if self.raw_passed_questions is None:
            questions_string = ", ".join([repr(q) for q in self.questions])
        else:
            questions_string = ", ".join(
                [repr(q) for q in self.raw_passed_questions or []]
            )
        return f"Survey(questions=[{questions_string}], memory_plan={self.memory_plan}, rule_collection={self.rule_collection}, question_groups={self.question_groups}, questions_to_randomize={self.questions_to_randomize})"

    def to_dataset(self):
        """Convert the survey to a Dataset with one row per question.

        Returns a tabular Dataset with columns for question_name,
        question_type, question_text, question_options, and skip_logic
        (when any non-default rules exist).

        Example:
            >>> from edsl.dataset import Dataset
            >>> ds = Survey.example().to_dataset()
            >>> isinstance(ds, Dataset)
            True
        """
        _, dataset = self.info()[0]
        return dataset

    def _summary_repr(self, max_text_preview: int = 60, max_items: int = 50) -> str:
        """Generate a summary representation of the Survey with Rich formatting.

        Args:
            max_text_preview: Maximum characters to show for question text previews
            max_items: Maximum number of items to show in lists before truncating
        """
        from .survey_repr import generate_summary_repr

        return generate_summary_repr(self, max_text_preview, max_items)

    def _summary(self) -> dict:
        """Return a compact summary dict with question count and names."""
        return {
            "# questions": len(self),
            "question_name list": self.question_names,
        }

    def info(self) -> list:
        """Return display sections as (title, Dataset) pairs.

        Builds one section with a column per question field (using the
        actual field names from each question's ``to_dict()``).  Fields
        that don't apply to a given question are shown as blank strings.
        A ``skip_logic`` column is appended when any non-default rules
        exist.

        Example:
            >>> s = Survey.example()
            >>> sections = s.info()
            >>> sections[0][0]
            'Questions'
        """
        from edsl.dataset import Dataset
        from collections import defaultdict, OrderedDict
        from .base import EndOfSurvey

        num_questions = len(self.questions)

        # Collect dicts and discover the union of all field names.
        q_dicts: list[dict] = []
        # Use ordered priority list so common fields come first.
        priority = [
            "question_name",
            "question_type",
            "question_text",
            "question_options",
        ]
        all_keys: OrderedDict[str, None] = OrderedDict()
        for key in priority:
            all_keys[key] = None

        for question in self.questions:
            d = question.to_dict(add_edsl_version=False)
            q_dicts.append(d)
            for key in d:
                if key not in all_keys:
                    all_keys[key] = None

        # Build column lists — blank string for missing / None values.
        columns: dict[str, list] = {k: [] for k in all_keys}
        for d in q_dicts:
            for key in all_keys:
                val = d.get(key)
                if val is None:
                    columns[key].append("")
                elif isinstance(val, list):
                    columns[key].append(", ".join(str(o) for o in val))
                elif isinstance(val, dict):
                    columns[key].append(
                        ", ".join(f"{k}: {v}" for k, v in val.items())
                    )
                else:
                    columns[key].append(str(val))

        # Skip logic column (only if any rules exist).
        rules_by_q: dict[int, list] = defaultdict(list)
        for rule in self.rule_collection.non_default_rules:
            rules_by_q[rule.current_q].append(rule)

        if rules_by_q:
            skip_logic: list[str] = []
            for idx in range(num_questions):
                if idx in rules_by_q:
                    lines = []
                    for rule in rules_by_q[idx]:
                        if rule.next_q == EndOfSurvey or rule.next_q >= num_questions:
                            target = "END"
                        else:
                            target = self.questions[rule.next_q].question_name
                        lines.append(f"if {rule.expression} → {target}")
                    skip_logic.append("\n".join(lines))
                else:
                    skip_logic.append("")
            columns["skip_logic"] = skip_logic

        # Drop columns that are entirely blank.
        data = []
        for key, values in columns.items():
            if any(v != "" for v in values):
                data.append({key: values})

        return [("Questions", Dataset(data))]

    def tree(self, node_list: Optional[List[str]] = None):
        """Display the survey as a tree structure."""
        return self.to_scenario_list().tree(node_list=node_list)

    def table(self, *fields, tablefmt="rich") -> Table:
        """Render the survey as a table.

        Args:
            *fields: Column names to include. If omitted, all columns are shown.
            tablefmt: Table format (default ``"rich"``).
        """
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

    def rename(self, rename_dict: Dict[str, str]) -> "Survey":
        """Return a new Survey with the specified questions renamed.

        Args:
            rename_dict: A dictionary mapping old question names to new question names.

        Returns:
            A new Survey instance with the renamed questions.

        Raises:
            ValueError: If any key in rename_dict does not correspond to an existing question name.

        Examples:
            >>> s = Survey.example()
            >>> s.question_names
            ['q0', 'q1', 'q2']
            >>> s_renamed = s.rename({'q0': 'likes_school', 'q1': 'reason_no'})
            >>> s_renamed.question_names
            ['likes_school', 'reason_no', 'q2']

            Attempting to rename a non-existent question raises an error:

            >>> s.rename({'q0': 'new_name', 'nonexistent': 'another_name'})
            Traceback (most recent call last):
            ...
            ValueError: The following question names in rename_dict do not exist in the survey: {'nonexistent'}
        """
        # Validate that all keys in rename_dict exist in the survey
        existing_question_names = set(self.question_names)
        rename_keys = set(rename_dict.keys())
        invalid_keys = rename_keys - existing_question_names

        if invalid_keys:
            raise ValueError(
                f"The following question names in rename_dict do not exist in the survey: {invalid_keys}"
            )

        new_questions = []
        for question in self.questions:
            new_question = question.duplicate()
            if question.question_name in rename_dict:
                new_question.question_name = rename_dict[question.question_name]
            new_questions.append(new_question)
        return Survey(questions=new_questions)

    def with_edited_question(
        self,
        question_name: str,
        field_name_new_values: dict,
        pop_fields: Optional[List[str]] = None,
    ) -> "Survey":
        """Return a new Survey with the specified question's fields updated.

        Args:
            question_name: Name of the question to edit.
            field_name_new_values: Dict of field names to new values.
            pop_fields: Optional list of field names to remove from the question.

        Returns:
            A new Survey with the edited question.

        Example:
            >>> s = Survey.example()
            >>> s2 = s.with_edited_question('q0', {'question_text': 'Do you enjoy school?'})
            >>> s2.get('q0').question_text
            'Do you enjoy school?'
        """
        new_survey = self.duplicate()
        question = new_survey.get(question_name)
        from ..questions import Question

        old_dict = question.to_dict(add_edsl_version=False)
        old_dict.update(field_name_new_values)
        for field_name in pop_fields or []:
            _ = old_dict.pop(field_name)
        new_question = Question(**old_dict)  # type: ignore[missing-argument]
        new_survey.questions[new_survey.questions.index(question)] = new_question
        return new_survey

    # Could add back, but work with Polly instead
    # def edit(self):
    #     import webbrowser
    #     import time

    #     info = self.push()
    #     print("Waiting for survey to be created on Coop...")
    #     time.sleep(5)
    #     url = f"https://chick.expectedparrot.com/edit/survey/{info['uuid']}"
    #     webbrowser.open(url)
    #     print(f"Survey opened in web editor: {url}")

    #     # Wait for user to confirm editing is complete
    #     while True:
    #         user_input = input("Is editing complete [y/n]: ").strip().lower()
    #         if user_input in ["y", "yes"]:
    #             print("Waiting for changes to sync...")
    #             time.sleep(5)
    #             # Pull the updated survey and update current object
    #             updated_survey = Survey.pull(info["uuid"])
    #             # Update the current object's attributes with the pulled survey
    #             self.__dict__.update(updated_survey.__dict__)
    #             print("Survey updated with changes from web editor.")
    #             break
    #         elif user_input in ["n", "no"]:
    #             print("Editing session ended. Survey remains unchanged.")
    #             break
    #         else:
    #             print("Please enter 'y' for yes or 'n' for no.")

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

    def _get_job(self, model=None, agent=None, **kwargs):
        """Build a Jobs object with the given model, agent, and scenario kwargs.

        Args:
            model: Language model to use. Defaults to ``Model()``.
            agent: Agent to use. Defaults to ``Agent()``.
            **kwargs: Key-value pairs passed as a Scenario.

        Returns:
            A configured Jobs object ready to run.
        """
        if model is None:
            from edsl.language_models.model import Model

            model = Model()

        from edsl.scenarios import Scenario

        s = Scenario(kwargs)

        if not agent:
            from edsl.agents import Agent

            agent = Agent()

        return self.by(s).by(agent).by(model)  # type: ignore[arg-type]

    ###################
    # COOP METHODS
    ###################
    def humanize(
        self,
        human_survey_name: str = "New survey",
        survey_description: Optional[str] = None,
        survey_alias: Optional[str] = None,
        survey_visibility: Optional["VisibilityType"] = "private",
        humanize_schema: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """
        Send the survey to Coop.

        Args:
            human_survey_name: Display name for the survey on Coop.
            survey_description: Optional description text.
            survey_alias: Optional URL-friendly alias.
            survey_visibility: One of ``"private"``, ``"public"``, or ``"unlisted"``.

        Returns:
            A Scenario containing the human-survey project details.
        """
        from ..coop import Coop
        from ..scenarios import Scenario

        c = Coop()
        human_survey_details = c.create_human_survey(
            self,
            human_survey_name=human_survey_name,
            survey_description=survey_description,
            survey_alias=survey_alias,
            survey_visibility=survey_visibility,
            humanize_schema=humanize_schema,
        )
        return Scenario(human_survey_details)

    def preview(
        self,
        humanize_schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Returns a link to preview the humanize survey on Coop.
        """
        from ..coop import Coop

        c = Coop()
        return c.get_survey_preview_url(self, humanize_schema=humanize_schema)

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

    def to_markdown(self) -> str:
        """Generate a markdown string representation of the survey.

        Converts Jinja2 braces ({{ }}) to << >> to indicate piping.

        Returns:
            str: Markdown formatted string representation of the survey.

        Example:
            >>> md = Survey.example().to_markdown()
            >>> 'Do you like school?' in md
            True
        """
        text = self.table().to_markdown_table()
        # Replace Jinja2 braces with << >> to indicate piping
        text = re.sub(r"\{\{", "<<", text)
        text = re.sub(r"\}\}", ">>", text)
        return text

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
        self,
        questions_only: bool = True,
        rename=False,
        remove_jinja2_syntax: bool = False,
    ) -> "ScenarioList":
        """Convert the survey to a scenario list.

        Args:
            questions_only: If True, only include questions (not instructions).
            rename: If True, rename keys for display (e.g., 'question_name' to 'identifier').
            remove_jinja2_syntax: If True, remove Jinja2 template syntax ({{ }}) from question text.

        Returns:
            ScenarioList: A scenario list containing survey data.

        Example:
            >>> s = Survey.example()
            >>> sl = s.to_scenario_list()
            >>> len(sl) == len(s)
            True
        """
        return self._exporter.to_scenario_list(
            questions_only, rename, remove_jinja2_syntax
        )

    def code(self, filename: str = "", survey_var_name: str = "survey") -> list[str]:
        """Generate Python source code that recreates this survey.

        Args:
            filename: If provided, write the code to this file path.
            survey_var_name: Variable name to use in the generated code.

        Returns:
            A list of code lines.
        """
        return self._exporter.code(filename, survey_var_name)

    # def html(
    #     self,
    #     scenario: Optional[dict] = None,
    #     filename: Optional[str] = None,
    #     return_link=False,
    #     css: Optional[str] = None,
    #     cta: str = "Open HTML file",
    #     include_question_name=False,
    # ) -> FileStore:
    #     """DEPRECATED: Use :py:meth:`to_html` instead."""
    #     import warnings

    #     warnings.warn(
    #         "Survey.html is deprecated and will be removed in a future release. Use Survey.to_html instead.",
    #         DeprecationWarning,
    #         stacklevel=2,
    #     )
    #     return self.to_html(
    #         scenario,
    #         filename,
    #         return_link=return_link,
    #         css=css,
    #         cta=cta,
    #         include_question_name=include_question_name,
    #     )

    # def latex(
    #     self,
    #     filename: Optional[str] = None,
    #     include_question_name: bool = False,
    #     standalone: bool = True,
    # ) -> "FileStore":
    #     """Generate a LaTeX (.tex) representation of the survey.

    #     Parameters
    #     ----------
    #     filename : Optional[str]
    #         The filename to write to. If not provided, a temporary file is created
    #         in the current working directory with a ``.tex`` suffix.
    #     include_question_name : bool
    #         If True, includes the internal ``question_name`` of each question. Default False.
    #     standalone : bool
    #         If True, the LaTeX file is standalone. Default True.
    #     """
    #     return self._exporter.latex(filename, include_question_name, standalone)

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
            >>> s = Survey.example()  # doctest: +SKIP
            >>> s_renamed = s.with_renamed_question("q0", "school_preference")  # doctest: +SKIP
            >>> s_renamed.get("school_preference").question_name  # doctest: +SKIP
            'school_preference'

            >>> # Rules are also updated
            >>> s_renamed.show_rules()  # doctest: +SKIP
        """
        from .question_renamer import QuestionRenamer

        return QuestionRenamer.with_renamed_question(self, old_name, new_name)



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
