"""
Base module for all question types in the EDSL framework.

The question_base module defines the QuestionBase abstract base class, which serves as
the foundation for all question types in EDSL. This module establishes the core
functionality, interface, and behavior that all questions must implement.

Key features of this module include:
- Abstract base class that defines the question interface
- Core validation and serialization capabilities
- Integration with language models and agents
- Support for template-based question generation
- Connection to response validation and answer processing

This module is one of the most important in EDSL as it establishes the contract that
all question types must follow, enabling consistent behavior across different types
of questions while allowing for specialized functionality in derived classes.

Technical Details:
-----------------
1. Question Architecture:
   - QuestionBase is an abstract base class that cannot be instantiated directly
   - It uses multiple inheritance from several mixins to provide different capabilities
   - The RegisterQuestionsMeta metaclass enables automatic registration of question types
   - Each concrete question type must define specific class attributes and methods

2. Inheritance Hierarchy:
   - PersistenceMixin: Provides serialization and deserialization via to_dict/from_dict
   - RepresentationMixin: Provides string representation via __repr__
   - SimpleAskMixin: Provides the basic asking functionality to interact with models
   - QuestionBasePromptsMixin: Handles template-based prompt generation
   - QuestionBaseGenMixin: Connects questions to language models for response generation
   - AnswerValidatorMixin: Handles validation of answers using response validators

3. Common Workflow:
   - User creates a question instance with specific parameters
   - Question is connected to a language model via the `by()` method
   - The question generates prompts using templates and scenario variables
   - The language model generates a response which is parsed and validated
   - The validated response is returned to the user

4. Extension Points:
   - New question types inherit from QuestionBase and define specialized behavior
   - Custom template files can be defined for specialized prompt generation
   - Response validators can be customized for different validation requirements
   - Integration with the survey system using question_name as a key identifier
"""

from __future__ import annotations
from abc import ABC
from typing import (
    Any,
    Type,
    Optional,
    Union,
    TypedDict,
    TYPE_CHECKING,
    Literal,
    Callable,
)

from .descriptors import QuestionNameDescriptor, QuestionTextDescriptor
from .answer_validator_mixin import AnswerValidatorMixin
from .register_questions_meta import RegisterQuestionsMeta
from .simple_ask_mixin import SimpleAskMixin
from .question_base_prompts_mixin import QuestionBasePromptsMixin
from .question_base_gen_mixin import QuestionBaseGenMixin
from .exceptions import QuestionSerializationError

from ..base import PersistenceMixin, RepresentationMixin, BaseDiff, BaseDiffCollection
from ..utilities import remove_edsl_version, is_valid_variable_name

if TYPE_CHECKING:
    from ..results import Result

# Define VisibilityType for type annotations
VisibilityType = Literal["private", "public", "unlisted"]

if TYPE_CHECKING:
    from ..agents import Agent
    from ..scenarios import Scenario
    from ..surveys import Survey

if TYPE_CHECKING:
    from rich.text import Text
    from .response_validator_abc import ResponseValidatorABC
    from ..language_models import LanguageModel
    from ..results import Results
    from ..jobs import Jobs


class QuestionBase(
    PersistenceMixin,
    RepresentationMixin,
    SimpleAskMixin,
    QuestionBasePromptsMixin,
    QuestionBaseGenMixin,
    ABC,
    AnswerValidatorMixin,
    metaclass=RegisterQuestionsMeta,
):
    """
    Abstract base class for all question types in EDSL.

    QuestionBase defines the core interface and behavior that all question types must
    implement. It provides the foundation for asking questions to agents, validating
    responses, generating prompts, and integrating with the rest of the EDSL framework.

    The class inherits from multiple mixins to provide different capabilities:
    - PersistenceMixin: Serialization and deserialization
    - RepresentationMixin: String representation
    - SimpleAskMixin: Basic asking functionality
    - QuestionBasePromptsMixin: Template-based prompt generation
    - QuestionBaseGenMixin: Generate responses with language models
    - AnswerValidatorMixin: Response validation

    It also uses the RegisterQuestionsMeta metaclass to enforce constraints on child classes
    and automatically register them for serialization and runtime use.

    Class attributes:
        question_name (str): Name of the question, used as an identifier
        question_text (str): The actual text of the question to be asked

    Required attributes in derived classes:
        question_type (str): String identifier for the question type
        _response_model (Type): Pydantic model class for validating responses
        response_validator_class (Type): Validator class for responses

    Key Methods:
        by(model): Connect this question to a language model for answering
        run(): Execute the question with the connected language model
        duplicate(): Create an exact copy of this question
        is_valid_question_name(): Verify the question_name is valid

    Lifecycle:
        1. Instantiation: A question is created with specific parameters
        2. Connection: The question is connected to a language model via by()
        3. Execution: The question is run to generate a response
        4. Validation: The response is validated based on the question type
        5. Result: The validated response is returned for analysis

    Template System:
        Questions use Jinja2 templates for generating prompts. Each question type
        has associated template files:
        - answering_instructions.jinja: Instructions for how the model should answer
        - question_presentation.jinja: Format for how the question is presented
        Templates support variable substitution using scenario variables.

    Response Validation:
        Each question type has a dedicated response validator that:
        - Enforces the expected response structure
        - Ensures the response is valid for the question type
        - Attempts to fix invalid responses when possible
        - Uses Pydantic models for schema validation

    Example:
        Derived classes must define the required attributes:

        ```python
        class FreeTextQuestion(QuestionBase):
            question_type = "free_text"
            _response_model = FreeTextResponse
            response_validator_class = FreeTextResponseValidator

            def __init__(self, question_name, question_text, **kwargs):
                self.question_name = question_name
                self.question_text = question_text
                # Additional initialization as needed
        ```

        Using a question:

        ```python
        # Create a question
        question = FreeTextQuestion(
            question_name="opinion",
            question_text="What do you think about AI?"
        )

        # Connect to a language model and run
        from edsl.language_models import Model
        model = Model()
        result = question.by(model).run()

        # Access the answer
        answer = result.select("answer.opinion").to_list()[0]
        print(f"The model's opinion: {answer}")
        ```

    Notes:
        - QuestionBase is abstract and cannot be instantiated directly
        - Child classes must implement required methods and attributes
        - The RegisterQuestionsMeta metaclass handles registration of question types
        - Questions can be serialized to and from dictionaries for storage
        - Questions can be used independently or as part of surveys
    """

    question_name: str = QuestionNameDescriptor()  # type: ignore[assignment]
    question_text: str = QuestionTextDescriptor()  # type: ignore[assignment]

    _store_class_name = "QuestionBase"

    from edsl.base.store_accessor import StoreDescriptor
    store = StoreDescriptor()

    _answering_instructions = None
    _question_presentation = None

    def comment(
        self,
        comment: str,
        func: Optional[Callable] = None,
        log_format: Optional[str] = None,
    ):
        """Comment on this question."""
        if func is None:
            func = print
        if log_format is None:
            log_format = "{comment}"
        comment = log_format.format(comment=comment)
        func(comment)
        return self

    def is_valid_question_name(self) -> bool:
        """
        Check if the question name is a valid Python identifier.

        This method validates that the question_name attribute is a valid Python
        variable name according to Python's syntax rules. This is important because
        question names are often used as identifiers in various parts of the system.

        Returns:
            bool: True if the question name is a valid Python identifier, False otherwise.

        Examples:
            >>> from edsl.questions import QuestionFreeText
            >>> q = QuestionFreeText(question_name="valid_name", question_text="Text")
            >>> q.is_valid_question_name()
            True
        """
        return is_valid_variable_name(self.question_name)

    @property
    def response_validator(self) -> "ResponseValidatorABC":
        """
        Get the appropriate validator for this question type.

        This property lazily creates and returns a response validator instance specific
        to this question type. The validator is created using the ResponseValidatorFactory,
        which selects the appropriate validator class based on the question's type.

        Returns:
            ResponseValidatorABC: An instance of the appropriate validator for this question.

        Notes:
            - Each question type has its own validator class defined in the class attribute
              response_validator_class
            - The validator is responsible for ensuring responses conform to the expected
              format and constraints for this question type
        """
        from .response_validator_factory import ResponseValidatorFactory

        rvf = ResponseValidatorFactory(self)
        return rvf.response_validator

    def duplicate(self) -> "QuestionBase":
        """
        Create an exact copy of this question instance.

        This method creates a new instance of the question with identical attributes
        by serializing the current instance to a dictionary and then deserializing
        it back into a new instance.

        Returns:
            QuestionBase: A new instance of the same question type with identical attributes.

        Examples:
            >>> from edsl.questions import QuestionFreeText
            >>> original = QuestionFreeText(question_name="q1", question_text="Hello?")
            >>> copy = original.duplicate()
            >>> original.question_name == copy.question_name
            True
            >>> original is copy
            False
        """
        data = self.to_dict()
        duplicated = self.from_dict(data)

        # Preserve testing attributes that aren't serialized
        if hasattr(self, "exception_to_throw"):
            duplicated.exception_to_throw = self.exception_to_throw
        if hasattr(self, "override_answer"):
            duplicated.override_answer = self.override_answer

        return duplicated

    def _simulate_answer(self, human_readable: bool = False) -> dict:
        """
        Generate a simulated valid answer for this question.

        Examples:
            >>> from edsl import QuestionFreeText as Q
            >>> answer = Q.example()._simulate_answer()
            >>> "answer" in answer and "generated_tokens" in answer
            True
        """
        import random

        if self.question_type == "free_text":
            return {
                "answer": "Hello, how are you?",
                "generated_tokens": "Hello, how are you?",
            }

        if hasattr(self, "question_options") and self.question_options:
            if self.use_code:
                answer = random.randint(0, len(self.question_options) - 1)
                if human_readable:
                    answer = self.question_options[answer]
            else:
                answer = random.choice(self.question_options)
            return {"answer": answer, "comment": "Simulated answer"}

        return {"answer": "Simulated answer", "comment": "Simulated answer"}

    class ValidatedAnswer(TypedDict):
        """
        Type definition for a validated answer to a question.

        This TypedDict defines the structure of a validated answer, which includes
        the actual answer value, an optional comment, and optional generated tokens
        information for tracking LLM token usage.

        Attributes:
            answer: The validated answer value, type depends on question type
            comment: Optional string comment or explanation for the answer
            generated_tokens: Optional string containing raw LLM output for token tracking
        """

        answer: Any
        comment: Optional[str]
        generated_tokens: Optional[str]

    def _validate_answer(
        self, answer: dict, replacement_dict: Optional[dict] = None
    ) -> ValidatedAnswer:
        """
        Validate a raw answer against this question's constraints.

        This method applies the appropriate validator for this question type to the
        provided answer dictionary, ensuring it conforms to the expected structure
        and constraints.

        Args:
            answer: Dictionary containing the raw answer to validate.
            replacement_dict: Optional dictionary of replacements to apply during
                             validation for template variables.

        Returns:
            ValidatedAnswer: A dictionary containing the validated answer with the
                            structure defined by ValidatedAnswer TypedDict.

        Raises:
            QuestionAnswerValidationError: If the answer fails validation.

        Examples:
            >>> from edsl.questions import QuestionFreeText as Q
            >>> Q.example()._validate_answer({'answer': 'Hello', 'generated_tokens': 'Hello'})
            {'answer': 'Hello', 'generated_tokens': 'Hello'}
        """
        try:
            return self.response_validator.validate(answer, replacement_dict)
        except Exception as e:
            # Ensure all validation errors are raised as QuestionAnswerValidationError
            from .exceptions import QuestionAnswerValidationError

            if not isinstance(e, QuestionAnswerValidationError):
                raise QuestionAnswerValidationError(
                    message=f"Invalid response: {e}",
                    data=answer,
                    model=getattr(self, "response_model", None),
                    pydantic_error=e if hasattr(e, "errors") else None,
                ) from e
            raise

    @property
    def name(self) -> str:
        """
        Get the question name.

        This property is a simple alias for question_name that provides a consistent
        interface shared with other EDSL components like Instructions.

        Returns:
            str: The question name.
        """
        return self.question_name

    def __hash__(self) -> int:
        """
        Calculate a hash value for this question instance.

        This method returns a deterministic hash based on the serialized dictionary
        representation of the question. This allows questions to be used in sets and
        as dictionary keys.

        Returns:
            int: A hash value for this question.

        Examples:
            >>> from edsl import QuestionFreeText as Q
            >>> q1 = Q.example()
            >>> q2 = q1.duplicate()
            >>> hash(q1) == hash(q2)
            True
        """
        from ..utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False))

    @property
    def data(self) -> dict:
        """Return a dictionary of question attributes **except** for question_type.

        >>> from edsl.questions import QuestionFreeText as Q
        >>> Q.example().data
        {'question_name': 'how_are_you', 'question_text': 'How are you?'}
        """
        exclude_list = [
            "question_type",
            # "_include_comment",
            # "_use_code",
            "_model_instructions",
            "_store_accessor",
        ]
        only_if_not_na_list = ["_answering_instructions", "_question_presentation"]

        only_if_not_default_list = {"_include_comment": True, "_use_code": False, "_enumeration": "none"}

        def ok(key, value):
            if not key.startswith("_"):
                return False
            if key in exclude_list:
                return False
            if key in only_if_not_na_list and value is None:
                return False
            if (
                key in only_if_not_default_list
                and value == only_if_not_default_list[key]
            ):
                return False

            return True

        candidate_data = {
            k.replace("_", "", 1): v for k, v in self.__dict__.items() if ok(k, v)
        }

        if "func" in candidate_data:
            func = candidate_data.pop("func")
            import inspect

            candidate_data["function_source_code"] = inspect.getsource(func)

        return candidate_data

    def to_jobs(self):
        return self.to_survey().to_jobs()

    def gold_standard(self, q_and_a_dict: dict[str, str]) -> "Result":
        """Run the question with a gold standard agent and return the result."""
        return self.to_survey().gold_standard(q_and_a_dict)

    def to_dict(self, add_edsl_version: bool = True):
        """Convert the question to a dictionary that includes the question type (used in deserialization).

        >>> from edsl.questions import QuestionFreeText as Q; Q.example().to_dict(add_edsl_version = False)
        {'question_name': 'how_are_you', 'question_text': 'How are you?', 'question_type': 'free_text'}
        """
        candidate_data = self.data.copy()
        candidate_data["question_type"] = self.question_type
        d = {key: value for key, value in candidate_data.items() if value is not None}
        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "QuestionBase"

        return d

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict) -> "QuestionBase":
        """
        Create a question instance from a dictionary representation.

        This class method deserializes a question from a dictionary representation,
        typically created by the to_dict method. It looks up the appropriate question
        class based on the question_type field and constructs an instance of that class.

        Args:
            data: Dictionary representation of a question, must contain a 'question_type' field.

        Returns:
            QuestionBase: An instance of the appropriate question subclass.

        Raises:
            QuestionSerializationError: If the data is missing the question_type field or
                                      if no question class is registered for the given type.

        Examples:
            >>> from edsl.questions import QuestionFreeText
            >>> original = QuestionFreeText.example()
            >>> serialized = original.to_dict()
            >>> deserialized = QuestionBase.from_dict(serialized)
            >>> original.question_text == deserialized.question_text
            True
            >>> isinstance(deserialized, QuestionFreeText)
            True

        Notes:
            - The @remove_edsl_version decorator removes EDSL version information from the
              dictionary before processing
            - Special handling is implemented for certain question types like linear_scale
            - Model instructions, if present, are handled separately to ensure proper initialization
        """
        local_data = data.copy()

        try:
            question_type = local_data.pop("question_type")
            if question_type == "linear_scale":
                # This is a fix for issue https://github.com/expectedparrot/edsl/issues/165
                options_labels = local_data.get("option_labels", None)
                if options_labels:
                    options_labels = {
                        int(key): value for key, value in options_labels.items()
                    }
                    local_data["option_labels"] = options_labels
        except Exception as e:
            raise QuestionSerializationError(
                f"Error in deserialization: {str(e)}. Data does not have a 'question_type' field (got {data})."
            )
        from .question_registry import get_question_class

        try:
            question_class = get_question_class(question_type)
        except ValueError:
            raise QuestionSerializationError(
                f"No question registered with question_type {question_type}. The passed in dictionary was: {data}",
            )
        except Exception as e:
            raise QuestionSerializationError(
                f"Error in deserialization: {str(e)}. The passed in dictionary was: {data}"
            )

        if "model_instructions" in local_data:
            model_instructions = local_data.pop("model_instructions")
            new_q = question_class(**local_data)
            new_q.model_instructions = model_instructions
            return new_q

        return question_class(**local_data)

    def to_jsonl(self, blob_writer=None, **kwargs) -> str:
        """Serialize to JSONL with one line per field (header + one line per field).

        The first line is a header with edsl_class_name, question_type, and edsl_version.
        Subsequent lines are ``{"field": ..., "value": ...}`` pairs.

        >>> from edsl.questions import QuestionFreeText
        >>> jsonl = QuestionFreeText.example().to_jsonl()
        >>> lines = jsonl.splitlines()
        >>> import json; json.loads(lines[0])["__header__"]
        True
        """
        import json
        import edsl

        d = self.to_dict(add_edsl_version=False)
        question_type = d.pop("question_type")
        header = {
            "__header__": True,
            "edsl_class_name": type(self).__name__,
            "question_type": question_type,
            "edsl_version": edsl.__version__,
        }
        lines = [json.dumps(header)]
        for field, value in d.items():
            lines.append(json.dumps({"field": field, "value": value}))
        return "\n".join(lines)

    def to_jsonl_rows(self, blob_writer=None):
        return iter(self.to_jsonl().splitlines())

    @classmethod
    def from_jsonl(cls, source, blob_reader=None, **kwargs) -> "QuestionBase":
        """Deserialize from JSONL produced by :meth:`to_jsonl`.

        *source* may be a JSONL string or an iterable of lines.

        >>> from edsl.questions import QuestionFreeText
        >>> q = QuestionFreeText.example()
        >>> q2 = QuestionFreeText.from_jsonl(q.to_jsonl())
        >>> q.question_text == q2.question_text
        True
        """
        import json
        from .register_questions_meta import RegisterQuestionsMeta

        if isinstance(source, str):
            lines = source.strip().splitlines()
        else:
            lines = list(source)
        header = json.loads(lines[0])
        question_type = header["question_type"]
        registry = RegisterQuestionsMeta.question_types_to_classes()
        target_cls = registry[question_type]
        fields = {}
        for line in lines[1:]:
            row = json.loads(line)
            fields[row["field"]] = row["value"]
        return target_cls(**fields)

    @classmethod
    def _get_test_model(cls, canned_response: str = "Hello world") -> "LanguageModel":
        """
        Create a test language model with optional predefined response.

        This helper method creates a test language model that can be used for testing
        questions without making actual API calls to language model providers.

        Args:
            canned_response: Optional predefined response the model will return for any prompt.

        Returns:
            LanguageModel: A test language model instance.

        Notes:
            - The test model does not make external API calls
            - When canned_response is provided, the model will always return that response
            - Used primarily for testing, demonstrations, and examples
        """
        from ..language_models import LanguageModel

        return LanguageModel.example(canned_response=canned_response, test_model=True)

    @classmethod
    def run_example(
        cls,
        show_answer: bool = True,
        model: Optional["LanguageModel"] = None,
        cache: bool = False,
        disable_remote_cache: bool = False,
        disable_remote_inference: bool = False,
        **kwargs,
    ) -> "Results":
        """
        Run the example question with a language model and return results.

        This class method creates an example instance of the question, asks it using
        the provided language model, and returns the results. It's primarily used for
        demonstrations, documentation, and testing.

        Args:
            show_answer: If True, returns only the answer portion of the results.
                        If False, returns the full results.
            model: Language model to use for answering. If None, creates a default model.
            cache: Whether to use local caching for the model call.
            disable_remote_cache: Whether to disable remote caching.
            disable_remote_inference: Whether to disable remote inference.
            **kwargs: Additional keyword arguments to pass to the example method.

        Returns:
            Results: Either the full results or just the answer portion, depending on show_answer.

        Examples:
            >>> from edsl.language_models import LanguageModel
            >>> from edsl import QuestionFreeText as Q
            >>> m = Q._get_test_model(canned_response="Yo, what's up?")
            >>> results = Q.run_example(show_answer=True, model=m,
            ...                       disable_remote_cache=True, disable_remote_inference=True)
            >>> "answer" in str(results)
            True

        Notes:
            - This method is useful for quick demonstrations of question behavior
            - The disable_remote_* parameters are useful for offline testing
            - Additional parameters to customize the example can be passed via kwargs
        """
        if model is None:
            from ..language_models import Model

            model = Model()  # type: ignore[assignment]
        results = (
            cls.example(**kwargs)
            .by(model)
            .run(
                cache=cache,
                disable_remote_cache=disable_remote_cache,
                disable_remote_inference=disable_remote_inference,
            )
        )
        if show_answer:
            return results.select("answer.*")
        else:
            return results

    def __call__(
        self,
        just_answer: bool = True,
        model: Optional["LanguageModel"] = None,
        agent: Optional["Agent"] = None,
        disable_remote_cache: bool = False,
        disable_remote_inference: bool = False,
        verbose: bool = False,
        **kwargs,
    ) -> Union[Any, "Results"]:
        """Call the question.


        >>> from edsl import QuestionFreeText as Q
        >>> from edsl import Model
        >>> m = Model("test", canned_response = "Yo, what's up?")
        >>> q = Q(question_name = "color", question_text = "What is your favorite color?")
        >>> q(model = m, disable_remote_cache = True, disable_remote_inference = True, cache = False)
        "Yo, what's up?"

        """
        survey = self.to_survey()
        results = survey(
            model=model,
            agent=agent,
            **kwargs,
            verbose=verbose,
            disable_remote_cache=disable_remote_cache,
            disable_remote_inference=disable_remote_inference,
        )
        if just_answer:
            return results.select(f"answer.{self.question_name}").first()
        else:
            return results

    def run(self, *args, **kwargs) -> "Results":
        """Turn a single question into a survey and runs it."""
        return self.to_survey().run(*args, **kwargs)

    def using(self, *args, **kwargs) -> "Jobs":
        """Turn a single question into a survey and then a Job."""
        return self.to_survey().to_jobs().using(*args, **kwargs)

    async def run_async(
        self,
        just_answer: bool = True,
        model: Optional["LanguageModel"] = None,
        agent: Optional["Agent"] = None,
        disable_remote_inference: bool = False,
        **kwargs,
    ) -> Union[Any, "Results"]:
        """Call the question asynchronously.

        >>> import asyncio
        >>> from edsl.questions import QuestionFreeText as Q
        >>> m = Q._get_test_model(canned_response = "Blue")
        >>> q = Q(question_name = "color", question_text = "What is your favorite color?")
        >>> async def test_run_async(): result = await q.run_async(model=m, disable_remote_inference = True, disable_remote_cache = True); print(result)
        >>> asyncio.run(test_run_async())
        Blue
        """
        survey = self.to_survey()
        results = await survey.run_async(
            model=model,
            agent=agent,
            disable_remote_inference=disable_remote_inference,
            **kwargs,
        )
        if just_answer:
            return results.select(f"answer.{self.question_name}").first()
        else:
            return results

    def __getitem__(self, key: str) -> Any:
        """Get an attribute of the question so it can be treated like a dictionary.

        >>> from edsl.questions import QuestionFreeText as Q
        >>> Q.example()['question_text']
        'How are you?'
        """
        try:
            return getattr(self, key)
        except TypeError:
            from .exceptions import QuestionKeyError

            raise QuestionKeyError(
                f"Question has no attribute {key} of type {type(key)}"
            )

    # def __repr__(self) -> str:
    #     """Return a string representation of the question.

    #     Uses traditional repr format when running doctests, otherwise uses
    #     rich-based display for better readability.

    #     >>> from edsl import QuestionFreeText as Q
    #     >>> repr(Q.example())
    #     'Question(\\'free_text\\', question_name = \"""how_are_you\""", question_text = \"""How are you?\""")'
    #     """
    #     import os

    #     if os.environ.get("EDSL_RUNNING_DOCTESTS") == "True":
    #         return self._eval_repr_()
    #     else:
    #         return self._summary_repr()

    def __str__(self) -> str:
        """
        Return a string representation of the question.
        """
        return self._eval_repr_()

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the question.

        This representation can be used to reconstruct the question.
        Used primarily for doctests and debugging.
        """
        import os

        items = [
            f'{k} = """{v}"""' if isinstance(v, str) else f"{k} = {v}"
            for k, v in self.data.items()
            if k != "question_type"
        ]
        question_type = self.to_dict().get("question_type", "None")

        if not items:
            return f"Question('{question_type}')"

        # Check if we're running doctests to determine format
        if os.environ.get("EDSL_RUNNING_DOCTESTS") == "True":
            # Single-line format for doctests
            formatted_items = ", ".join(items)
            return f"Question('{question_type}', {formatted_items})"
        else:
            # Multi-line format for regular use
            formatted_items = ",\n\t".join(items)
            return f"Question('{question_type}',\n\t{formatted_items}\n)"

    @staticmethod
    def _highlight_template(text: str) -> "Text":
        """Return a ``rich.text.Text`` with ``{{ }}`` and ``< >`` spans highlighted."""
        import re
        from rich.text import Text

        styled = Text()
        parts = re.split(r"(\{\{.*?\}\}|<[^>]+>)", text)
        for part in parts:
            if not part:
                continue
            if part.startswith("{{") and part.endswith("}}"):
                styled.append(part.replace(" ", "\u00a0"), style="bold blue")
            elif part.startswith("<") and part.endswith(">"):
                styled.append(part.replace(" ", "\u00a0"), style="bold green")
            else:
                styled.append(part)
        return styled

    def info(self) -> list:
        """Return display sections as (title, Dataset) pairs.

        Uses the question's ``to_dict()`` fields as columns, same approach
        as Survey.info() but for a single question.
        """
        from edsl.dataset import Dataset

        d = self.to_dict(add_edsl_version=False)
        keys = list(d.keys())
        values = []
        for v in d.values():
            if v is None:
                values.append("")
            elif isinstance(v, list):
                values.append(", ".join(str(o) for o in v))
            elif isinstance(v, dict):
                values.append(", ".join(f"{k}: {val}" for k, val in v.items()))
            else:
                values.append(str(v))
        return [("Question", Dataset([{"field": keys}, {"value": values}]))]

    def _summary_repr(self) -> str:
        """Generate a summary representation of the Question as a Rich table."""
        from ..utilities.summary_table import ColumnDef, render_summary_table

        q_dict = self.to_dict(add_edsl_version=False)
        question_type = q_dict.get("question_type", "unknown")
        title = f"Question ({question_type})"

        columns = [
            ColumnDef("Attribute", style="bold green", no_wrap=True),
            ColumnDef("Value"),
        ]

        rows: list[tuple] = [
            ("question_name", repr(self.question_name)),
            ("question_text", self._highlight_template(self.question_text)),
        ]

        if hasattr(self, "question_options") and self.question_options:
            rows.append(("question_options", ", ".join(str(o) for o in self.question_options)))

        if hasattr(self, "option_labels") and self.option_labels:
            labels = ", ".join(f"{k}: {v!r}" for k, v in self.option_labels.items())
            rows.append(("option_labels", f"{{{labels}}}"))

        for attr in ("min_value", "max_value", "min_selections", "max_selections",
                      "num_selections", "max_list_items", "weight"):
            if hasattr(self, attr) and getattr(self, attr) is not None:
                rows.append((attr, repr(getattr(self, attr))))

        data_dict = self.data
        if data_dict.get("use_code"):
            rows.append(("use_code", "True"))
        if hasattr(self, "permissive") and self.permissive:
            rows.append(("permissive", "True"))
        if "include_comment" in data_dict and not data_dict["include_comment"]:
            rows.append(("include_comment", "False"))

        return render_summary_table(title=title, columns=columns, rows=rows)

    def __eq__(self, other: Union[Any, Type[QuestionBase]]) -> bool:
        """Check if two questions are equal. Equality is defined as having the .to_dict().

        >>> from edsl import QuestionFreeText as Q
        >>> q1 = Q.example()
        >>> q2 = Q.example()
        >>> q1 == q2
        True
        >>> q1.question_text = "How are you John?"
        >>> q1 == q2
        False

        """
        return hash(self) == hash(other)

    def __sub__(self, other) -> BaseDiff:
        """Return the difference between two objects.
        >>> from edsl import QuestionFreeText as Q
        >>> q1 = Q.example()
        >>> q2 = q1.copy()
        >>> q2.question_text = "How are you John?"
        >>> diff = q1 - q2
        """

        return BaseDiff(other, self)

    # TODO: Throws an error that should be addressed at QuestionFunctional
    def __add__(self, other_question_or_diff):
        """
        Compose two questions into a single question.
        """
        if isinstance(other_question_or_diff, BaseDiff) or isinstance(
            other_question_or_diff, BaseDiffCollection
        ):
            return other_question_or_diff.apply(self)

    def _translate_answer_code_to_answer(
        self, answer, scenario: Optional["Scenario"] = None
    ):
        """There is over-ridden by child classes that ask for codes."""
        return answer

    def add_question(self, other: QuestionBase) -> "Survey":
        """Add a question to this question by turning them into a survey with two questions.

        >>> from edsl.questions import QuestionFreeText as Q
        >>> from edsl.questions import QuestionMultipleChoice as QMC
        >>> s = Q.example().add_question(QMC.example())
        >>> len(s.questions)
        2
        """
        return self.to_survey().add_question(other)

    def to_survey(self) -> "Survey":
        """Turn a single question into a survey.
        >>> from edsl import QuestionFreeText as Q
        >>> Q.example().to_survey().questions[0].question_name
        'how_are_you'
        """
        from ..surveys import Survey

        return Survey([self])

    def humanize(
        self,
        human_survey_name: str = "New survey",
        survey_description: Optional[str] = None,
        survey_alias: Optional[str] = None,
        survey_visibility: Optional["VisibilityType"] = "private",
    ) -> dict:
        """
        Turn a single question into a survey and send the survey to Coop.

        Then, create a project on Coop so you can share the survey with human respondents.
        """
        s = self.to_survey()
        human_survey_details = s.humanize(
            human_survey_name, survey_description, survey_alias, survey_visibility
        )
        return human_survey_details

    def by(self, *args) -> "Jobs":
        """Turn a single question into a survey and then a Job."""
        from ..surveys import Survey

        s = Survey([self])
        return s.by(*args)

    def human_readable(self) -> str:
        """Print the question in a human readable format.

        >>> from edsl.questions import QuestionFreeText
        >>> QuestionFreeText.example().human_readable()
        'Question Type: free_text\\nQuestion: How are you?'
        """
        lines = []
        lines.append(f"Question Type: {self.question_type}")
        lines.append(f"Question: {self.question_text}")
        if hasattr(self, "question_options"):
            lines.append("Please name the option you choose from the following.:")
            for index, option in enumerate(self.question_options):
                lines.append(f"{option}")
        return "\n".join(lines)

    def html(
        self,
        scenario: Optional[dict] = None,
        agent: Optional[dict] = {},
        answers: Optional[dict] = None,
        include_question_name: bool = False,
        height: Optional[int] = None,
        width: Optional[int] = None,
        iframe=False,
    ):
        from ..questions.HTMLQuestion import HTMLQuestion

        return HTMLQuestion(self).html(
            scenario, agent, answers, include_question_name, height, width, iframe
        )

    @classmethod
    def example_model(cls):
        from ..language_models import Model

        q = cls.example()
        m = Model("test", canned_response=q._simulate_answer()["answer"])

        return m

    @classmethod
    def example_results(cls):
        m = cls.example_model()
        q = cls.example()
        return q.by(m).run(cache=False, disable_remote_inference=True)

    def rich_print(self):
        """Print the question in a rich format."""
        from rich.table import Table

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Question Name", style="dim")
        table.add_column("Question Type")
        table.add_column("Question Text")
        table.add_column("Options")

        question = self
        if hasattr(question, "question_options"):
            options = ", ".join([str(o) for o in question.question_options])
        else:
            options = "None"
        table.add_row(
            question.question_name,
            question.question_type,
            question.question_text,
            options,
        )
        return table

    def code(self):
        """Display the code representation of this question with syntax highlighting and copy button.

        In notebook environments, this method displays the eval-able string representation
        from _eval_repr_() with Python syntax highlighting and a click-to-copy button.
        In non-notebook environments, it returns the plain string.

        Returns:
            In notebooks: IPython.display.HTML object with formatted code
            Otherwise: str from _eval_repr_()

        Examples:
            >>> from edsl import QuestionFreeText as Q
            >>> q = Q.example()
            >>> code_str = q.code()  # Returns string in non-notebook environment
        """
        code_string = self._eval_repr_()

        # Check if we're in a notebook environment
        try:
            from IPython import get_ipython

            if get_ipython() is None:
                return code_string
        except ImportError:
            return code_string

        # Format code with pygments
        try:
            from pygments import highlight
            from pygments.lexers import PythonLexer
            from pygments.formatters import HtmlFormatter
            from IPython.display import HTML

            # Generate syntax-highlighted HTML
            formatter = HtmlFormatter(style="default", noclasses=True)
            highlighted = highlight(code_string, PythonLexer(), formatter)

            # Create HTML with copy button
            html = f"""
            <div style="position: relative; margin: 10px 0;">
                <button onclick="
                    var textarea = this.parentElement.querySelector('textarea');
                    navigator.clipboard.writeText(textarea.value);
                    this.textContent = 'Copied!';
                    setTimeout(() => {{ this.textContent = 'Copy to clipboard'; }}, 2000);
                " style="
                    position: absolute;
                    right: 10px;
                    top: 10px;
                    padding: 5px 10px;
                    background-color: #f0f0f0;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    cursor: pointer;
                    font-size: 12px;
                    z-index: 10;
                ">Copy to clipboard</button>
                <div style="padding-top: 10px;">
                    {highlighted}
                </div>
                <textarea style="position: absolute; left: -9999px;" readonly>{code_string}</textarea>
            </div>
            """

            return HTML(html)
        except ImportError:
            # If pygments isn't available, return plain string
            return code_string

    # endregion


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
