"""
This module contains the Result class, which captures the result of one interview.

The Result class is a fundamental building block in EDSL that stores all the data
associated with a single agent interview. Each Result object contains:

1. The agent that was interviewed
2. The scenario that was presented to the agent
3. The language model that was used to generate the agent's responses
4. The answers provided to the questions
5. The prompts used to generate those answers
6. Raw model responses and token usage statistics
7. Metadata about the questions and caching behavior

Results are typically created automatically when running interviews through the
Jobs system, and multiple Result objects are collected into a Results collection
for analysis.

The Result class inherits from both Base (for serialization) and UserDict (for
dictionary-like behavior), allowing it to be accessed like a dictionary while
maintaining a rich object model.
"""

from __future__ import annotations
import inspect
from collections import UserDict
from typing import Any, Callable, Optional, TYPE_CHECKING, Union, List

from ..base import Base

if TYPE_CHECKING:
    from ..agents import Agent
    from ..scenarios import Scenario, ScenarioList
    from ..language_models import LanguageModel
    from ..surveys import Survey
    from .result_transcript import Transcript

QuestionName = str
AnswerValue = Any


class Result(Base, UserDict):
    """The Result class captures the complete data from one agent interview.

    A Result object stores the agent, scenario, language model, and all answers
    provided during an interview, along with metadata such as token usage,
    caching information, and raw model responses. It provides a rich interface
    for accessing this data and supports serialization for storage and retrieval.

    The Result class inherits from both Base (for serialization) and UserDict (for
    dictionary-like behavior), allowing it to be accessed like a dictionary while
    maintaining a rich object model.

    Attributes:
        agent: The Agent object that was interviewed.
        scenario: The Scenario object that was presented to the agent.
        model: The LanguageModel object that was used to generate responses.
        answer: Dictionary mapping question names to answer values.
        sub_dicts: Organized sub-dictionaries for different data types.
        combined_dict: Flattened dictionary combining all sub-dictionaries.
        problem_keys: List of keys that have naming conflicts.

    Note:
        Results are typically created by the Jobs system when running interviews and
        collected into a Results collection for analysis. You rarely need to create
        Result objects manually.

    Examples:
        >>> result = Result.example()
        >>> result['answer']['how_feeling']
        'OK'
    """

    def __init__(
        self,
        agent: "Agent",
        scenario: "Scenario",
        model: "LanguageModel",
        iteration: int,
        answer: dict[QuestionName, AnswerValue],
        prompt: dict[QuestionName, str] = None,
        raw_model_response: Optional[dict] = None,
        survey: Optional["Survey"] = None,
        question_to_attributes: Optional[dict[QuestionName, Any]] = None,
        generated_tokens: Optional[dict] = None,
        comments_dict: Optional[dict] = None,
        reasoning_summaries_dict: Optional[dict] = None,
        cache_used_dict: Optional[dict[QuestionName, bool]] = None,
        indices: Optional[dict] = None,
        cache_keys: Optional[dict[QuestionName, str]] = None,
        validated_dict: Optional[dict[QuestionName, bool]] = None,
    ):
        """Initialize a Result object.

        Args:
            agent: The Agent object that was interviewed.
            scenario: The Scenario object that was presented.
            model: The LanguageModel object that generated responses.
            iteration: The iteration number for this result.
            answer: Dictionary mapping question names to answer values.
            prompt: Dictionary of prompts used for each question. Defaults to None.
            raw_model_response: The raw response from the language model. Defaults to None.
            survey: The Survey object containing the questions. Defaults to None.
            question_to_attributes: Dictionary of question attributes. Defaults to None.
            generated_tokens: Dictionary of token usage statistics. Defaults to None.
            comments_dict: Dictionary of comments for each question. Defaults to None.
            reasoning_summaries_dict: Dictionary of reasoning summaries. Defaults to None.
            cache_used_dict: Dictionary indicating cache usage for each question. Defaults to None.
            indices: Dictionary of indices for data organization. Defaults to None.
            cache_keys: Dictionary of cache keys for each question. Defaults to None.
            validated_dict: Dictionary indicating validation status for each question. Defaults to None.
        """
        if not question_to_attributes:
            if survey:
                question_to_attributes = survey.question_to_attributes()
            else:
                question_to_attributes = {}

        data = {
            "agent": agent,
            "scenario": scenario,
            "model": model,
            "iteration": iteration,
            "answer": answer,
            "prompt": prompt or {},  # keyed dictionaries
            "raw_model_response": raw_model_response or {},
            "question_to_attributes": question_to_attributes,
            "generated_tokens": generated_tokens or {},
            "comments_dict": comments_dict or {},
            "reasoning_summaries_dict": reasoning_summaries_dict or {},
            "cache_used_dict": cache_used_dict or {},
            "cache_keys": cache_keys or {},
            "validated_dict": validated_dict or {},
        }
        super().__init__(**data)
        self.indices = indices

        self._rb = None
        self._transformer = None

    @property
    def answers(self) -> "ScenarioList":
        from ..scenarios import Scenario, ScenarioList

        return ScenarioList(
            [
                Scenario(question_name=k, answer=v)
                for k, v in self.sub_dicts["answer"].items()
            ]
        )

    def get_question_text(self, question_name: QuestionName) -> str:
        return (
            self.data["question_to_attributes"]
            .get(question_name, {})
            .get("question_text", question_name)
        )

    def get_question_type(self, question_name: QuestionName) -> str:
        return (
            self.data["question_to_attributes"]
            .get(question_name, {})
            .get("question_type", "text")
        )

    def get_question_options(self, question_name: QuestionName) -> List[str]:
        return (
            self.data["question_to_attributes"]
            .get(question_name, {})
            .get("question_options", [])
        )

    def select(self, *question_names: QuestionName) -> "Result":
        """Return a new Result with only the specified questions included.

        This method creates a new Result object that contains only the answers and
        related metadata for the specified question names. All other data (agent,
        scenario, model) is preserved. This is useful when you want to focus on a
        subset of questions from a larger interview.

        Args:
            *question_names: Variable number of question names to include in the result.

        Returns:
            A new Result object containing only the specified questions.

        Examples:
            >>> result = Result.example()
            >>> result.answer
            {'how_feeling': 'OK', 'how_feeling_yesterday': 'Great'}
            >>> selected = result.select('how_feeling')
            >>> selected.answer
            {'how_feeling': 'OK'}
            >>> selected2 = result.select('how_feeling', 'how_feeling_yesterday')
            >>> selected2.answer
            {'how_feeling': 'OK', 'how_feeling_yesterday': 'Great'}
        """
        question_names_set = set(question_names)

        def filter_keys(d: dict, handle_prefixes: bool = False) -> dict:
            """Helper to filter keys in a dictionary to only include specified questions.

            Args:
                d: Dictionary to filter
                handle_prefixes: If True, also includes keys where question names are prefixes
            """
            if not d:
                return d

            if not handle_prefixes:
                # Simple case: exact key match
                return {k: v for k, v in d.items() if k in question_names_set}

            # Complex case: handle keys where question name is a prefix
            result = {}
            for k, v in d.items():
                # Check if key matches a question name exactly or starts with it
                if k in question_names_set:
                    result[k] = v
                else:
                    # Check if key starts with any question name followed by underscore
                    for q_name in question_names_set:
                        if k.startswith(q_name + "_"):
                            result[k] = v
                            break
            return result

        # Create new data with filtered keys in all relevant dictionaries
        new_data = {
            "agent": self.data["agent"],
            "scenario": self.data["scenario"],
            "model": self.data["model"],
            "iteration": self.data["iteration"],
            "answer": filter_keys(self.data["answer"]),
            "prompt": filter_keys(self.data.get("prompt", {}), handle_prefixes=True),
            "raw_model_response": self.data.get("raw_model_response", {}),
            "question_to_attributes": filter_keys(
                self.data.get("question_to_attributes", {})
            ),
            "generated_tokens": filter_keys(
                self.data.get("generated_tokens", {}), handle_prefixes=True
            ),
            "comments_dict": filter_keys(
                self.data.get("comments_dict", {}), handle_prefixes=True
            ),
            "reasoning_summaries_dict": filter_keys(
                self.data.get("reasoning_summaries_dict", {}), handle_prefixes=True
            ),
            "cache_used_dict": filter_keys(self.data.get("cache_used_dict", {})),
            "cache_keys": filter_keys(self.data.get("cache_keys", {})),
            "validated_dict": filter_keys(
                self.data.get("validated_dict", {}), handle_prefixes=True
            ),
        }

        return Result(**new_data, indices=self.indices)

    def rename(self, rename_dict: dict[QuestionName, QuestionName]) -> "Result":
        """Return a new Result with question names renamed according to rename_dict.

        This method creates a new Result object where all occurrences of question names
        (used as keys in various dictionaries) are replaced with their new names as
        specified in the rename_dict. This is useful when you want to standardize
        question naming or align multiple Results with different naming conventions.

        The method handles both exact key matches and composite keys where the question
        name is used as a prefix (e.g., 'question_name_user_prompt').

        Args:
            rename_dict: A dictionary mapping old question names to new question names.
                Only the questions specified in this dict will be renamed; others remain unchanged.

        Returns:
            A new Result object with renamed question keys throughout all sub-dictionaries.

        Examples:
            >>> result = Result.example()
            >>> result.answer
            {'how_feeling': 'OK', 'how_feeling_yesterday': 'Great'}
            >>> renamed = result.rename({'how_feeling': 'mood', 'how_feeling_yesterday': 'mood_yesterday'})
            >>> renamed.answer
            {'mood': 'OK', 'mood_yesterday': 'Great'}
        """

        def rename_keys(d: dict, handle_prefixes: bool = False) -> dict:
            """Helper to rename keys in a dictionary.

            Args:
                d: Dictionary to process
                handle_prefixes: If True, also handles keys where question names are prefixes
            """
            if not d:
                return d

            if not handle_prefixes:
                # Simple case: exact key match
                return {rename_dict.get(k, k): v for k, v in d.items()}

            # Complex case: handle keys where question name is a prefix
            result = {}
            for k, v in d.items():
                new_key = k
                # Check each question name to see if it's a prefix of this key
                for old_name, new_name in rename_dict.items():
                    # Check if key starts with old_name followed by underscore or is exact match
                    if k == old_name:
                        new_key = new_name
                        break
                    elif k.startswith(old_name + "_"):
                        # Replace the prefix
                        new_key = new_name + k[len(old_name) :]
                        break
                result[new_key] = v
            return result

        # Create new data with renamed keys in all relevant dictionaries
        new_data = {
            "agent": self.data["agent"],
            "scenario": self.data["scenario"],
            "model": self.data["model"],
            "iteration": self.data["iteration"],
            "answer": rename_keys(self.data["answer"]),
            "prompt": rename_keys(self.data.get("prompt", {}), handle_prefixes=True),
            "raw_model_response": self.data.get("raw_model_response", {}),
            "question_to_attributes": rename_keys(
                self.data.get("question_to_attributes", {})
            ),
            "generated_tokens": rename_keys(
                self.data.get("generated_tokens", {}), handle_prefixes=True
            ),
            "comments_dict": rename_keys(
                self.data.get("comments_dict", {}), handle_prefixes=True
            ),
            "reasoning_summaries_dict": rename_keys(
                self.data.get("reasoning_summaries_dict", {}), handle_prefixes=True
            ),
            "cache_used_dict": rename_keys(self.data.get("cache_used_dict", {})),
            "cache_keys": rename_keys(self.data.get("cache_keys", {})),
            "validated_dict": rename_keys(
                self.data.get("validated_dict", {}), handle_prefixes=True
            ),
        }

        return Result(**new_data, indices=self.indices)

    @property
    def transformer(self):
        """Get the ResultTransformer instance for this Result."""
        if self._transformer is None:
            from .result_transformer import ResultTransformer

            self._transformer = ResultTransformer(self.data)
        return self._transformer

    def by_question_data(
        self, flatten_nested_dicts: bool = False, separator: str = "_"
    ):
        """Organize result data by question with optional flattening of nested dictionaries.

        This method reorganizes the result data structure to be organized by question name,
        making it easier to analyze answers and related metadata on a per-question basis.

        Args:
            flatten_nested_dicts: Whether to flatten nested dictionaries using the separator.
                Defaults to False.
            separator: The separator to use when flattening nested dictionaries.
                Defaults to "_".

        Returns:
            A dictionary organized by question name, with each question containing
            its associated data (answer, prompt, metadata, etc.).
        """
        return self.transformer.by_question_data(flatten_nested_dicts, separator)

    def to_dataset(self, flatten_nested_dicts: bool = False, separator: str = "_"):
        """Convert the result to a dataset format.

        This method transforms the result data into a Dataset object suitable for
        analysis and data manipulation.

        Args:
            flatten_nested_dicts: Whether to flatten nested dictionaries using the separator.
                Defaults to False.
            separator: The separator to use when flattening nested dictionaries.
                Defaults to "_".

        Returns:
            A Dataset object containing the result data organized for analysis.
        """
        return self.transformer.to_dataset(flatten_nested_dicts, separator)

    @property
    def rb(self):
        if self._rb is None:
            from .result_builder import ResultBuilder

            rb = ResultBuilder(self.data, self.indices)
            self._rb = rb
        return self._rb

    @property
    def sub_dicts(self):
        return self.rb.sub_dicts

    @property
    def key_to_data_type(self):
        return self.rb.keys_to_data_types

    @property
    def combined_dict(self):
        return self.rb.combined_dict

    @property
    def problem_keys(self):
        return self.rb.problem_keys

    @property
    def agent(self) -> "Agent":
        """Return the Agent object."""
        # return self.data["agent"]
        return self.data["agent"]

    @agent.setter
    def agent(self, agent: "Agent"):
        self.data["agent"] = agent

    @property
    def scenario(self) -> "Scenario":
        """Return the Scenario object."""
        return self.data["scenario"]

    @scenario.setter
    def scenario(self, scenario: "Scenario"):
        self.data["scenario"] = scenario

    @property
    def model(self) -> "LanguageModel":
        """Return the LanguageModel object."""
        return self.data["model"]

    @model.setter
    def model(self, model: "LanguageModel"):
        self.data["model"] = model

    @property
    def answer(self) -> dict[QuestionName, AnswerValue]:
        """Return the answers."""
        return self.data["answer"]

    def check_expression(self, expression: str) -> None:
        """Check if an expression references a problematic key.

        Args:
            expression: The expression string to check for problematic keys.

        Raises:
            ResultsColumnNotFoundError: If the expression contains a problematic key
                that should use the full qualified name instead.
        """
        for key in self.problem_keys:
            if key in expression and key + "." not in expression:
                from .exceptions import ResultsColumnNotFoundError

                raise ResultsColumnNotFoundError(
                    f"Key by itself {key} is problematic. Use the full key {key + '.' + key} name instead."
                )
        return None

    def transcript(
        self, show_comments: bool = True, carousel: bool = True
    ) -> "Transcript":
        """Return a Transcript object that displays questions and answers.

        The returned Transcript object provides intelligent display formatting:
        - In terminal/console: Rich formatted output with colored panels
        - In Jupyter notebooks: HTML formatted carousel with styled cards and copy button
        - When converted to string: Simple plain-text format

        Args:
            show_comments: Whether to include respondent comments in the transcript.
                Defaults to True.
            carousel: Whether to display as a carousel in HTML (one Q&A at a time with navigation).
                Defaults to True. Set to False to show all Q&As at once. Only affects HTML display.

        Returns:
            A Transcript object that adapts its display to the environment.

        Examples:
            >>> result = Result.example()
            >>> transcript = result.transcript()
            >>> # Will display with Rich formatting in terminal
            >>> # Will display as carousel in Jupyter with navigation
            >>> # Can convert to string for plain text
            >>> str(transcript)  # doctest: +ELLIPSIS
            'QUESTION: ...'

            >>> # Exclude comments
            >>> transcript_no_comments = result.transcript(show_comments=False)

            >>> # Display as list (all questions at once)
            >>> transcript_list = result.transcript(carousel=False)

            >>> # Explicitly get specific formats
            >>> transcript.to_simple()  # doctest: +ELLIPSIS
            'QUESTION: ...'
            >>> transcript.to_html()  # doctest: +ELLIPSIS
            '...<div...'
        """
        from .result_transcript import Transcript

        return Transcript(self, show_comments=show_comments, carousel=carousel)

    def q_and_a(self, include_scenario: bool = False) -> "ScenarioList":
        """Return a ScenarioList with one row per question containing text, answer, and comment.

        Each Scenario in the returned ScenarioList has these keys:
        - "question_name": The internal question name/identifier
        - "question_text": The rendered question text
        - "answer": The recorded answer value
        - "comment": The recorded comment for the question (if any)

        If ``include_scenario`` is True, all scenario fields are also included in each row.

        Examples:
            >>> r = Result.example()
            >>> sl = r.q_and_a()
            >>> {"question_name", "question_text", "answer", "comment"}.issubset(set(sl.parameters))
            True
            >>> len(sl) == len(r.answer)
            True
            >>> sl2 = r.q_and_a(include_scenario=True)
            >>> set(r.sub_dicts["scenario"].keys()).issubset(set(sl2.parameters))
            True
        """
        from ..scenarios import Scenario, ScenarioList

        scenarios = []
        qt_attrs = self.data.get("question_to_attributes", {})
        comments_direct = self.data.get("comments_dict", {})
        comments_sub = self.sub_dicts.get("comment", {})

        # Normalize comments so they can be accessed by base question key
        # e.g., "question_0_comment" -> key "question_0"
        comments_by_question = {}
        comments_by_question.update(comments_direct)
        for ck, cv in comments_sub.items():
            if isinstance(ck, str) and ck.endswith("_comment"):
                comments_by_question[ck[:-8]] = cv
            else:
                comments_by_question[ck] = cv

        scenario_fields = self.sub_dicts.get("scenario", {}) if include_scenario else {}

        for question_name, answer_value in self.answer.items():
            q_meta = qt_attrs.get(question_name, {})
            q_text = q_meta.get("question_text", question_name)

            row = {
                "question_name": question_name,
                "question_text": q_text,
                "answer": answer_value,
                "comment": comments_by_question.get(question_name),
            }

            if include_scenario and scenario_fields:
                row.update(scenario_fields)

            scenarios.append(Scenario(row))

        return ScenarioList(scenarios)

    def code(self):
        """Return a string of code that can be used to recreate the Result object.

        Raises:
            ResultsError: This method is not implemented for Result objects.
        """
        from .exceptions import ResultsError

        raise ResultsError("The code() method is not implemented for Result objects")

    def get_answer(self, question_name: QuestionName) -> AnswerValue:
        """Return the answer for a given question name."""
        return self.data["answer"].get(question_name)

    def get_question_names(self) -> List[QuestionName]:
        """Return the names of all questions in the result."""
        return list[str](self.data["answer"].keys())

    def get_value(self, data_type: str, key: str) -> Any:
        """Return the value for a given data type and key.

        This method provides a consistent way to access values across different
        sub-dictionaries in the Result object. It's particularly useful when you
        need to programmatically access values without knowing which data type
        a particular key belongs to.

        Args:
            data_type: The category of data to retrieve from. Valid options include:
                "agent", "scenario", "model", "answer", "prompt", "comment",
                "generated_tokens", "raw_model_response", "question_text",
                "question_options", "question_type", "cache_used", "cache_keys".
            key: The specific attribute name within that data type.

        Returns:
            The value associated with the key in the specified data type.

        Examples:
            >>> r = Result.example()
            >>> r.get_value("answer", "how_feeling")
            'OK'
            >>> r.get_value("scenario", "period")
            'morning'
        """
        return self.sub_dicts[data_type][key]

    def copy(self) -> Result:
        """Return a copy of the Result object.

        Returns:
            A new Result object that is a copy of this one.

        Examples:
            >>> r = Result.example()
            >>> r2 = r.copy()
            >>> r == r2
            True
            >>> id(r) == id(r2)
            False
        """
        return Result.from_dict(self.to_dict())

    def __eq__(self, other) -> bool:
        """Return True if the Result object is equal to another Result object.

        Args:
            other: Another object to compare with this Result.

        Returns:
            True if the objects are equal based on their hash values, False otherwise.

        Examples:
            >>> r = Result.example()
            >>> r == r
            True
        """
        return hash(self) == hash(other)

    def to_dict(
        self,
        add_edsl_version: bool = True,
        include_cache_info: bool = False,
        full_dict: bool = False,
    ) -> dict[str, Any]:
        """Return a dictionary representation of the Result object.

        Args:
            add_edsl_version: Whether to include EDSL version information in the output.
                Defaults to True.
            include_cache_info: Whether to include cache information in the output.
                Defaults to False.

        Returns:
            A dictionary representation of the Result object containing all relevant data.

        Examples:
            >>> r = Result.example()
            >>> data = r.to_dict()
            >>> data['scenario']['period']
            'morning'
        """
        from .result_serializer import ResultSerializer

        return ResultSerializer.to_dict(self, add_edsl_version, include_cache_info)

    def __hash__(self):
        """Return a hash of the Result object.

        Returns:
            An integer hash value based on the dictionary representation of the Result.
        """
        from ..utilities.utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False, include_cache_info=False))

    @classmethod
    def from_dict(cls, data: dict) -> Result:
        """Return a Result object from a dictionary representation.

        Args:
            json_dict: Dictionary containing Result data.

        Returns:
            A new Result object created from the dictionary data.
        """
        from .result_serializer import ResultSerializer

        return ResultSerializer.from_dict(data)

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the Result object.

        This representation can be used with eval() to recreate the Result object.
        Used primarily for doctests and debugging.
        """
        params = ", ".join(f"{key}={repr(value)}" for key, value in self.data.items())
        return f"{self.__class__.__name__}({params})"

    def _summary_repr(self, max_answers: int = 5) -> str:
        """Generate a summary representation of the Result with Rich formatting.

        Args:
            max_answers: Maximum number of answers to show before truncating
        """
        from rich.console import Console
        from rich.text import Text
        import io
        from edsl.config import RICH_STYLES

        # Build the Rich text
        output = Text()
        output.append("Result(\n", style=RICH_STYLES["primary"])

        # Agent information
        if self.agent:
            agent_traits = getattr(self.agent, "traits", {})
            if agent_traits:
                trait_str = ", ".join(
                    f"{k}={repr(v)}" for k, v in list(agent_traits.items())[:3]
                )
                if len(agent_traits) > 3:
                    trait_str += f", ... ({len(agent_traits) - 3} more)"
                output.append(
                    f"    agent: {{{trait_str}}},\n", style=RICH_STYLES["key"]
                )
            else:
                output.append("    agent: Agent(),\n", style=RICH_STYLES["key"])

        # Scenario information
        if self.scenario:
            scenario_dict = dict(self.scenario)
            if scenario_dict:
                scenario_str = ", ".join(
                    f"{k}={repr(v)}" for k, v in list(scenario_dict.items())[:3]
                )
                if len(scenario_dict) > 3:
                    scenario_str += f", ... ({len(scenario_dict) - 3} more)"
                output.append(
                    f"    scenario: {{{scenario_str}}},\n", style=RICH_STYLES["key"]
                )
            else:
                output.append("    scenario: Scenario(),\n", style=RICH_STYLES["key"])

        # Model information
        if self.model:
            model_name = getattr(
                self.model, "model", getattr(self.model, "_model_", "unknown")
            )
            service_name = getattr(self.model, "_inference_service_", "unknown")
            output.append(
                f"    model: {model_name} ({service_name}),\n", style=RICH_STYLES["key"]
            )

        # Iteration
        iteration = self.data.get("iteration", 0)
        output.append(f"    iteration: {iteration},\n", style=RICH_STYLES["default"])

        # Answers
        answers = self.answer
        if answers:
            output.append(
                f"    answers: {len(answers)} question{'s' if len(answers) != 1 else ''},\n",
                style=RICH_STYLES["secondary"],
            )
            output.append("        {\n", style=RICH_STYLES["default"])

            for i, (q_name, q_answer) in enumerate(list(answers.items())[:max_answers]):
                answer_repr = repr(q_answer)
                if len(answer_repr) > 50:
                    answer_repr = answer_repr[:47] + "..."
                output.append("            ", style=RICH_STYLES["default"])
                output.append(f"'{q_name}'", style=RICH_STYLES["secondary"])
                output.append(f": {answer_repr},\n", style=RICH_STYLES["default"])

            if len(answers) > max_answers:
                output.append(
                    f"            ... ({len(answers) - max_answers} more)\n",
                    style=RICH_STYLES["dim"],
                )

            output.append("        },\n", style=RICH_STYLES["default"])
        else:
            output.append("    answers: {},\n", style=RICH_STYLES["dim"])

        output.append(")", style=RICH_STYLES["primary"])

        # Render to string
        console = Console(file=io.StringIO(), force_terminal=True, width=120)
        console.print(output, end="")
        return console.file.getvalue()

    @classmethod
    def example(cls) -> "Result":
        """Return an example Result object.

        Returns:
            A sample Result object for testing and demonstration purposes.

        Examples:
            >>> result = Result.example()
            >>> type(result)
            <class 'edsl.results.result.Result'>
            >>> isinstance(result, Result)
            True
        """
        from .results import Results

        return Results.example()[0]

    def score_with_answer_key(self, answer_key: dict) -> dict[str, int]:
        """Score the result against a reference answer key.

        This method evaluates the correctness of answers by comparing them to a
        provided answer key. It returns a dictionary with counts of correct,
        incorrect, and missing answers.

        The answer key can contain either single values or lists of acceptable values.
        If a list is provided, the answer is considered correct if it matches any
        value in the list.

        Args:
            answer_key: A dictionary mapping question names to expected answers.
                Values can be single items or lists of acceptable answers.

        Returns:
            A dictionary with keys 'correct', 'incorrect', and 'missing', indicating
            the counts of each answer type.

        Examples:
            >>> result = Result.example()
            >>> result.answer
            {'how_feeling': 'OK', 'how_feeling_yesterday': 'Great'}

            >>> # Using exact match answer key
            >>> answer_key = {'how_feeling': 'OK', 'how_feeling_yesterday': 'Great'}
            >>> result.score_with_answer_key(answer_key)
            {'correct': 2, 'incorrect': 0, 'missing': 0}

            >>> # Using answer key with multiple acceptable answers
            >>> answer_key = {'how_feeling': 'OK', 'how_feeling_yesterday': ['Great', 'Good']}
            >>> result.score_with_answer_key(answer_key)
            {'correct': 2, 'incorrect': 0, 'missing': 0}
        """
        final_scores = {"correct": 0, "incorrect": 0, "missing": 0}
        for question_name, answer in self.answer.items():
            if question_name in answer_key:
                if (
                    answer == answer_key[question_name]
                    or answer in answer_key[question_name]
                ):
                    final_scores["correct"] += 1
                else:
                    final_scores["incorrect"] += 1
            else:
                final_scores["missing"] += 1

        return final_scores

    def score(self, scoring_function: Callable) -> Union[int, float]:
        """Score the result using a passed-in scoring function.

        Args:
            scoring_function: A callable that takes parameters from the Result's combined_dict
                and returns a numeric score.

        Returns:
            The numeric score returned by the scoring function.

        Raises:
            ResultsError: If a required parameter for the scoring function is not found
                in the Result object.

        Examples:
            >>> def f(status): return 1 if status == 'Joyful' else 0
            >>> result = Result.example()
            >>> result.score(f)
            1
        """
        signature = inspect.signature(scoring_function)
        params = {}
        for k, v in signature.parameters.items():
            if k in self.combined_dict:
                params[k] = self.combined_dict[k]
            elif v.default is not v.empty:
                params[k] = v.default
            else:
                from .exceptions import ResultsError

                raise ResultsError(f"Parameter {k} not found in Result object")
        return scoring_function(**params)

    def display_transcript(
        self, show_options: bool = True, show_agent_info: bool = True
    ) -> None:
        """Display a rich-formatted chat transcript of the interview.

        This method creates a ChatTranscript object and displays the conversation
        between questions and agent responses in a beautiful, chat-like format
        using the Rich library.

        Args:
            show_options: Whether to display question options if available. Defaults to True.
            show_agent_info: Whether to show agent information at the top. Defaults to True.

        """
        from .chat_transcript import ChatTranscript

        chat_transcript = ChatTranscript(self)
        chat_transcript.view(show_options=show_options, show_agent_info=show_agent_info)

    @classmethod
    def from_interview(cls, interview) -> Result:
        """Return a Result object from an interview dictionary.

        This method ensures no reference to the original interview is maintained,
        creating a clean Result object from the interview data.

        Args:
            interview: An interview dictionary containing the raw interview data.

        Returns:
            A new Result object created from the interview data.
        """
        from .result_from_interview import ResultFromInterview

        converter = ResultFromInterview(interview)
        return converter.convert()


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
