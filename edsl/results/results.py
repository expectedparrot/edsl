"""The Results module provides tools for working with collections of Result objects.

The Results class is the primary container for analyzing and manipulating data obtained
from running surveys with language models. It implements a powerful data analysis interface
with methods for filtering, selecting, mutating, and visualizing your results, similar to
data manipulation libraries like dplyr or pandas.

Key components:

1. Results - A collection of Result objects with methods for data analysis and manipulation
2. Report - A flexible reporting system for generating formatted output from Results
3. Selectors - Tools for efficiently extracting specific data from Results

The Results class is not typically instantiated directly; instead, it's returned by the
run() method of a Job object. Once you have a Results object, you can use its methods
to analyze and extract insights from your survey data.

Example workflow:
```python
# Run a job and get results
results = job.run()

# Filter to a subset of results
filtered = results.filter("how_feeling == 'Great'")

# Select specific columns for analysis
data = filtered.select("how_feeling", "agent.status")

# Create a new derived column
with_sentiment = results.mutate("sentiment = 1 if how_feeling == 'Great' else 0")

# Generate a report
report = Report(results, fields=["answer.how_feeling", "answer.sentiment"])
print(report.generate())
```
"""

from __future__ import annotations
import json
import warnings
from functools import wraps
from typing import Optional, Callable, Any, Union, List, TYPE_CHECKING
from collections.abc import MutableSequence

from ..base import Base

if TYPE_CHECKING:
    from ..interviews import Interview
    from ..surveys import Survey
    from ..agents import AgentList
    from ..scenarios import ScenarioList
    from ..results import Result
    from ..tasks import TaskHistory
    from ..language_models import ModelList
    from ..dataset import Dataset
    from ..caching import Cache
    from .results_transcript import Transcripts


from ..utilities import dict_hash
from ..dataset import ResultsOperationsMixin

from .result import Result
from .results_filter import ResultsFilter
from .results_serializer import ResultsSerializer
from .utilities import ensure_ready
from .job_cost_calculator import JobCostCalculator
from .results_sampler import ResultsSampler
from .data_type_cache_manager import DataTypeCacheManager
from .results_remote_fetcher import ResultsRemoteFetcher
from .results_transformer import ResultsTransformer
from .results_properties import ResultsProperties
from .results_representation import ResultsRepresentation
from .results_container import ResultsContainer
from .results_grouper import ResultsGrouper
from .results_transcript_generator import TranscriptsGenerator
from .exceptions import (
    ResultsError,
    ResultsColumnNotFoundError,
    ResultsInvalidNameError,
)


class Results(MutableSequence, ResultsOperationsMixin, Base):
    """A collection of Result objects with powerful data analysis capabilities.

    The Results class is the primary container for working with data from EDSL surveys.
    It provides a rich set of methods for data analysis, transformation, and visualization
    inspired by data manipulation libraries like dplyr and pandas. The Results class
    implements a functional, fluent interface for data manipulation where each method
    returns a new Results object, allowing method chaining.

    Attributes:
        survey: The Survey object containing the questions used to generate results.
        data: A list of Result objects containing the responses.
        created_columns: A list of column names created through transformations.
        cache: A Cache object for storing model responses.
        completed: Whether the Results object is ready for use.
        task_history: A TaskHistory object containing information about the tasks.
        known_data_types: List of valid data type strings for accessing data.

    Key features:
        - List-like interface for accessing individual Result objects
        - Selection of specific data columns with `select()`
        - Filtering results with boolean expressions using `filter()`
        - Creating new derived columns with `mutate()`
        - Recoding values with `recode()` and `answer_truncate()`
        - Sorting results with `order_by()`
        - Converting to other formats (dataset, table, pandas DataFrame)
        - Serialization for storage and retrieval
        - Support for remote execution and result retrieval

    Results objects have a hierarchical structure with the following components:
        1. Each Results object contains multiple Result objects
        2. Each Result object contains data organized by type (agent, scenario, model, answer, etc.)
        3. Each data type contains multiple attributes (e.g., "how_feeling" in the answer type)

    You can access data in a Results object using dot notation (`answer.how_feeling`) or
    using just the attribute name if it's not ambiguous (`how_feeling`).

    The Results class also tracks "created columns" - new derived values that aren't
    part of the original data but were created through transformations.

    Examples:
        >>> # Create a simple Results object from example data
        >>> r = Results.example()
        >>> len(r) > 0  # Contains Result objects
        True
        >>> # Filter and transform data
        >>> filtered = r.filter("how_feeling == 'Great'")
        >>> # Access hierarchical data
        >>> 'agent' in r.known_data_types
        True
    """

    __documentation__ = "https://docs.expectedparrot.com/en/latest/results.html"

    known_data_types = [
        "answer",
        "scenario",
        "agent",
        "model",
        "prompt",
        "raw_model_response",
        "iteration",
        "question_text",
        "question_options",
        "question_type",
        "comment",
        "generated_tokens",
        "cache_used",
        "cache_keys",
        "reasoning_summary",
        "validated",
    ]

    def __init__(
        self,
        survey: Optional["Survey" | str] = None,
        data: Optional[list["Result"]] = None,
        name: Optional[str] = None,
        created_columns: Optional[list[str]] = None,
        cache: Optional["Cache"] = None,
        job_uuid: Optional[str] = None,
        total_results: Optional[int] = None,
        task_history: Optional["TaskHistory"] = None,
        sort_by_iteration: bool = False,
    ):
        """Instantiate a Results object with a survey and a list of Result objects.

        Args:
            survey: A Survey object containing the questions used to generate results.
            data: A list of Result objects containing the responses.
            created_columns: A list of column names created through transformations.
            cache: A Cache object for storing model responses.
            job_uuid: A string representing the job UUID.
            total_results: An integer representing the total number of results.
            task_history: A TaskHistory object containing information about the tasks.
            sort_by_iteration: Whether to sort data by iteration before initializing.
        """
        if survey is not None and isinstance(survey, str):
            pulled_results = Results.pull(survey)
            self.__dict__.update(pulled_results.__dict__)
            return

        self.completed = True
        self._fetching = False

        self._data_class = list

        # Sort data appropriately before initialization if needed
        if data and sort_by_iteration:
            # First try to sort by order attribute if present on any result
            has_order = any(hasattr(item, "order") for item in data)
            if has_order:

                def get_order(item):
                    if hasattr(item, "order"):
                        return item.order
                    return item.data.get("iteration", 0) * 1000

                data = sorted(data, key=get_order)
            else:
                data = sorted(data, key=lambda x: x.data.get("iteration", 0))

        # Initialize data with the appropriate class
        self.data = self._data_class(data or [])

        from ..caching import Cache
        from ..tasks import TaskHistory
        self.survey = survey
        self.created_columns = created_columns or []
        self._job_uuid = job_uuid
        self._total_results = total_results
        self.cache = cache or Cache()

        self.task_history = task_history or TaskHistory(interviews=[])

        # Initialize cache manager for expensive operations
        self._cache_manager = DataTypeCacheManager(self)

        # Initialize properties handler
        self._properties = ResultsProperties(self)

        # Initialize container handler
        self._container = ResultsContainer(self)

        # Initialize grouper handler
        self._grouper = ResultsGrouper(self)

        # Initialize representation handler
        self._representation = ResultsRepresentation(self)

        # Initialize filter handler
        self._results_filter = ResultsFilter(self)

        # Initialize transcripts generator
        self._transcripts_generator = TranscriptsGenerator(self)

        # Initialize serializer
        self._results_serializer = ResultsSerializer(self)

        if name is not None:
            self.name = name
        else:
            self.name = None

        if hasattr(self, "_add_output_functions"):
            self._add_output_functions()

    @wraps(TranscriptsGenerator.transcripts)
    def transcripts(self, show_comments: bool = True) -> "Transcripts":
        return self._transcripts_generator.transcripts(show_comments=show_comments)

    @classmethod
    def from_job_info(cls, job_info: dict) -> "Results":
        """Instantiate a Results object from a job info dictionary.

        This method creates a Results object in a not-ready state that will
        fetch its data from a remote source when methods are called on it.

        Args:
            job_info: Dictionary containing information about a remote job.

        Returns:
            Results: A new Results instance with completed=False that will
                fetch remote data when needed.

        Examples:
            >>> # Create a job info dictionary
            >>> job_info = {'job_uuid': '12345', 'creation_data': {'model': 'gpt-4'}}
            >>> # Create a Results object from the job info
            >>> results = Results.from_job_info(job_info)
            >>> results.completed
            False
            >>> hasattr(results, 'job_info')
            True
        """
        results = cls()
        results.completed = False
        results.job_info = job_info
        return results

    def add_task_history_entry(self, interview: "Interview") -> None:
        self.task_history.add_interview(interview)

    @wraps(DataTypeCacheManager.get_answers)
    def get_answers(self, question_name: str) -> list:
        return self._cache_manager.get_answers(question_name)

    @wraps(ResultsRepresentation.summary)
    def _summary(self) -> dict:
        return self._representation.summary()

    def _cache_keys(self) -> List[str]:  # -> list:
        """Return a list of all cache keys from the results.

        This method collects all cache keys by iterating through each result in the data
        and extracting the values from the 'cache_keys' dictionary. These keys can be used
        to identify cached responses and manage the cache effectively.

        Returns:
            List[str]: A list of cache keys from all results.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> all([type(s) == str for s in r._cache_keys()])
            True
        """
        cache_keys = []
        for result in self:
            cache_keys.extend(list(result["cache_keys"].values()))
        return cache_keys

    def relevant_cache(self, cache: Cache) -> Cache:
        cache_keys = self._cache_keys()
        return cache.subset(cache_keys)

    def agent_answers_by_question(
        self, agent_key_fields: Optional[List[str]] = None, separator: str = ","
    ) -> dict:
        """Returns a dictionary of agent answers.

        The keys are the agent names and the values are the answers.

        >>> result = Results.example().agent_answers_by_question()
        >>> sorted(result['how_feeling'].values())
        ['Great', 'OK', 'OK', 'Terrible']
        >>> sorted(result['how_feeling_yesterday'].values())
        ['Good', 'Great', 'OK', 'Terrible']
        """
        return self._grouper.agent_answers_by_question(agent_key_fields, separator)

    def extend_sorted(self, other):
        """Extend the Results list with items from another iterable.

        This method preserves ordering based on 'order' attribute if present,
        otherwise falls back to 'iteration' attribute.
        """
        return self._container.extend_sorted(other)

    def compute_job_cost(self, include_cached_responses_in_cost: bool = False) -> float:
        """Compute the cost of a completed job in USD.

        This method delegates to the JobCostCalculator class to calculate the total
        cost of all model responses in the results. By default, it only counts the
        cost of responses that were not cached.

        Args:
            include_cached_responses_in_cost: Whether to include the cost of cached
                responses in the total. Defaults to False.

        Returns:
            float: The total cost in USD.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> r.compute_job_cost()
            0.0
        """
        calculator = JobCostCalculator(self)
        return calculator.compute_job_cost(include_cached_responses_in_cost)

    def code(self):
        """Method for generating code representations.

        Raises:
            ResultsError: This method is not implemented for Results objects.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> try:
            ...     r.code()
            ... except ResultsError as e:
            ...     str(e).startswith("The code() method is not implemented")
            True
        """
        raise ResultsError("The code() method is not implemented for Results objects")

    @ensure_ready
    def __getitem__(self, i):
        return self._container.__getitem__(i)

    @ensure_ready
    def __setitem__(self, i, item):
        return self._container.__setitem__(i, item)

    @ensure_ready
    def __delitem__(self, i):
        return self._container.__delitem__(i)

    @ensure_ready
    def __len__(self):
        return self._container.__len__()

    @ensure_ready
    def insert(self, index, item):
        return self._container.insert(index, item)

    @ensure_ready
    def extend(self, other):
        """Extend the Results list with items from another iterable."""
        return self._container.extend(other)

    @wraps(ResultsContainer.__add__)
    def __add__(self, other: Results) -> Results:
        return self._container.__add__(other)

    def _repr_html_(self):
        if not self.completed:
            if hasattr(self, "job_info"):
                self.fetch_remote(self.job_info)

            if not self.completed:
                return "Results not ready to call"

        return super()._repr_html_()

    @ensure_ready
    def __repr__(self) -> str:
        return super().__repr__()

    @wraps(ResultsRepresentation.eval_repr)
    def _eval_repr_(self) -> str:
        return self._representation.eval_repr()

    @wraps(ResultsRepresentation.summary_repr)
    def _summary_repr(self, max_text_preview: int = 60, max_items: int = 25) -> str:
        return self._representation.summary_repr(max_text_preview, max_items)

    def info(self) -> list:
        """Return display sections as (title, Dataset) pairs.

        Produces a summary table (Components/Count/Details) and the data
        table, mirroring what ``summary_repr`` shows in the terminal.
        """
        from edsl.dataset import Dataset

        num_obs = len(self)
        num_agents = len(set(self.agents))
        num_models = len(set(self.models))
        num_scenarios = len(set(self.scenarios))
        num_questions = (
            len(self.survey.questions)
            if self.survey and hasattr(self.survey, "questions")
            else 0
        )

        components = []
        counts = []
        details = []

        # Questions
        if self.survey and hasattr(self.survey, "questions"):
            names = [q.question_name for q in self.survey.questions]
            components.append("Questions")
            counts.append(str(num_questions))
            details.append(", ".join(names))

        # Agents
        agent_detail = ""
        if num_agents > 0:
            trait_keys = [k for k in self.agent_keys if not k.startswith("agent_")]
            if trait_keys:
                agent_detail = f"traits: {', '.join(trait_keys)}"
        components.append("Agents")
        counts.append(str(num_agents))
        details.append(agent_detail)

        # Models
        model_names = []
        for m in set(self.models):
            model_names.append(
                getattr(m, "model", getattr(m, "_model_", "unknown"))
            )
        components.append("Models")
        counts.append(str(num_models))
        details.append(", ".join(sorted(set(model_names))))

        # Scenarios
        scenario_detail = ""
        if num_scenarios > 0:
            field_keys = [
                k for k in self.scenario_keys if not k.startswith("scenario_")
            ]
            if field_keys:
                scenario_detail = f"keys: {', '.join(field_keys)}"
        components.append("Scenarios")
        counts.append(str(num_scenarios))
        details.append(scenario_detail)

        summary = Dataset(
            [
                {"Component": components},
                {"Count": counts},
                {"Details": details},
            ]
        )
        data = self.to_dataset()
        return [("Summary", summary), ("Data", data)]

    def table(
        self,
        *fields,
        tablefmt: Optional[str] = "rich",
        pretty_labels: Optional[dict] = None,
        print_parameters: Optional[dict] = None,
    ):
        new_fields = []
        for field in fields:
            if "." in field:
                data_type, key = field.split(".")
                if data_type not in self.known_data_types:
                    raise ResultsInvalidNameError(
                        f"{data_type} is not a valid data type. Must be in {self.known_data_types}"
                    )
                if key == "*":
                    for k in self._cache_manager.data_type_to_keys[data_type]:
                        new_fields.append(k)
                else:
                    if key not in self._cache_manager.key_to_data_type:
                        raise ResultsColumnNotFoundError(
                            f"{key} is not a valid key. Must be in {self._cache_manager.key_to_data_type}"
                        )
                    new_fields.append(key)
            else:
                new_fields.append(field)

        return (
            self.to_scenario_list()
            .to_dataset()
            .table(
                *new_fields,
                tablefmt=tablefmt,
                pretty_labels=pretty_labels,
                print_parameters=print_parameters,
            )
        )

    def to_dataset(self) -> "Dataset":
        return self.select()

    def optimzie_scenarios(self):
        for result in self.data:
            result.scenario.offload(inplace=True)

    @wraps(ResultsSerializer.to_dict)
    def to_dict(
        self,
        sort: bool = False,
        add_edsl_version: bool = True,
        include_cache: bool = True,
        include_task_history: bool = False,
        include_cache_info: bool = True,
        offload_scenarios: bool = True,
        full_dict: bool = False,
    ) -> dict[str, Any]:
        return self._results_serializer.to_dict(
            sort=sort,
            add_edsl_version=add_edsl_version,
            include_cache=include_cache,
            include_task_history=include_task_history,
            include_cache_info=include_cache_info,
            offload_scenarios=offload_scenarios,
        )

    def to_jsonl_rows(self, blob_writer=None):
        """Yield JSONL rows for CAS storage."""
        return self._results_serializer.to_jsonl_rows(blob_writer=blob_writer)

    def to_jsonl(self, filename=None, **kwargs):
        """Export as inline JSONL."""
        return self._results_serializer.to_jsonl(filename=filename)

    @classmethod
    def from_jsonl(cls, source, **kwargs):
        """Load a Results from an inline JSONL source."""
        return ResultsSerializer.from_jsonl(source)

    def initialize_cache_from_results(self):
        from ..caching import Cache, CacheEntry

        cache = Cache(data={})

        for result in self.data:
            for key in result.data["prompt"]:
                if key.endswith("_system_prompt"):
                    question_name = key.removesuffix("_system_prompt")
                    system_prompt = result.data["prompt"][key].text
                    user_key = f"{question_name}_user_prompt"
                    if user_key in result.data["prompt"]:
                        user_prompt = result.data["prompt"][user_key].text
                    else:
                        user_prompt = ""

                    # Get corresponding model response
                    response_key = f"{question_name}_raw_model_response"
                    output = result.data["raw_model_response"].get(response_key, "")

                    entry = CacheEntry(
                        model=result.model.model,
                        parameters=result.model.parameters,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        output=json.dumps(output),
                        iteration=0,
                    )
                    cache.data[entry.key] = entry

        self.cache = cache

    @property
    @wraps(ResultsProperties.has_unfixed_exceptions.fget)
    def has_unfixed_exceptions(self) -> bool:
        return self._properties.has_unfixed_exceptions

    def __hash__(self) -> int:
        return dict_hash(
            self.to_dict(
                sort=True,
                add_edsl_version=False,
                include_cache=False,
                include_cache_info=False,
            )
        )

    @property
    @wraps(ResultsProperties.hashes.fget)
    def hashes(self) -> set:
        return self._properties.hashes

    def _sample_legacy(self, n: int) -> Results:
        """Return a random sample of the results using legacy algorithm.

        This method delegates to the ResultsSampler class and is kept for
        backward compatibility. Use sample() instead.

        Args:
            n: The number of samples to return.

        Returns:
            Results: A new Results object with sampled data.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> len(r.sample(2))
            2
        """
        sampler = ResultsSampler(self)
        return sampler.sample_legacy(n)

    @classmethod
    @wraps(ResultsSerializer.from_dict)
    def from_dict(cls, data: dict[str, Any]) -> Results:
        return ResultsSerializer.from_dict(data)

    @property
    @wraps(ResultsProperties.columns.fget)
    def columns(self) -> list[str]:
        return self._properties.columns

    def show_columns(self):
        """Display columns in a tree format using a mermaid diagram.

        This method creates a hierarchical visualization of all columns in the Results object,
        organized by data type. Unlike the columns() property which returns a flat list,
        this method shows the relationship between data types and their corresponding keys.

        Returns:
            ColumnTreeVisualization: An object that displays as a mermaid diagram in Jupyter
            notebooks and as formatted text in terminals.

        Example:

        >>> r = Results.example()
        >>> r.show_columns()  # doctest: +SKIP
        # Shows a tree diagram with data types as parent nodes and keys as children
        """
        from .column_tree_visualization import ColumnTreeVisualization

        # Get the hierarchical columns
        relevant_cols = self.relevant_columns()

        # Group columns by data type
        data_types = {}
        for col in relevant_cols:
            if "." in col:
                data_type, key = col.split(".", 1)
                if data_type not in data_types:
                    data_types[data_type] = []
                data_types[data_type].append(key)
            else:
                # Handle columns without prefix (shouldn't happen in normal cases)
                if "other" not in data_types:
                    data_types["other"] = []
                data_types["other"].append(col)

        return ColumnTreeVisualization(data_types)

    @property
    @wraps(ResultsProperties.answer_keys.fget)
    def answer_keys(self) -> dict[str, str]:
        return self._properties.answer_keys

    @property
    @wraps(ResultsProperties.agents.fget)
    def agents(self) -> AgentList:
        return self._properties.agents

    @property
    @wraps(ResultsProperties.models.fget)
    def models(self) -> ModelList:
        return self._properties.models

    def __eq__(self, other):
        return hash(self) == hash(other)

    @property
    @wraps(ResultsProperties.scenarios.fget)
    def scenarios(self) -> ScenarioList:
        return self._properties.scenarios

    @property
    @wraps(ResultsProperties.agent_keys.fget)
    def agent_keys(self) -> list[str]:
        return self._properties.agent_keys

    @property
    @wraps(ResultsProperties.model_keys.fget)
    def model_keys(self) -> list[str]:
        return self._properties.model_keys

    @property
    @wraps(ResultsProperties.scenario_keys.fget)
    def scenario_keys(self) -> list[str]:
        return self._properties.scenario_keys

    @property
    @wraps(ResultsProperties.question_names.fget)
    def question_names(self) -> list[str]:
        return self._properties.question_names

    @property
    @wraps(ResultsProperties.all_keys.fget)
    def all_keys(self) -> list[str]:
        return self._properties.all_keys

    def first(self) -> Result:
        """Return the first observation in the results.

        Example:

        >>> r = Results.example()
        >>> r.first()
        Result(agent...
        """
        return self.data[0]

    @ensure_ready
    def mutate(
        self, new_var_string: str, functions_dict: Optional[dict] = None
    ) -> Results:
        """Create a new column based on a computational expression.

        This method delegates to the ResultsTransformer class to handle the mutation operation.

        Args:
            new_var_string: A string containing an assignment expression in the form
                "new_column_name = expression". The expression can reference
                any existing column and use standard Python syntax.
            functions_dict: Optional dictionary of custom functions that can be used in
                the expression. Keys are function names, values are function objects.

        Returns:
            A new Results object with the additional column.

        Examples:
            >>> r = Results.example()

            >>> # Create a simple derived column
            >>> r.mutate('how_feeling_x = how_feeling + "x"').select('how_feeling_x')
            Dataset([{'answer.how_feeling_x': ['OKx', 'Greatx', 'Terriblex', 'OKx']}])

            >>> # Create a binary indicator column
            >>> r.mutate('is_great = 1 if how_feeling == "Great" else 0').select('is_great')
            Dataset([{'answer.is_great': [0, 1, 0, 0]}])

            >>> # Create a column with custom functions
            >>> def sentiment(text):
            ...     return len(text) > 5
            >>> r.mutate('is_long = sentiment(how_feeling)',
            ...          functions_dict={'sentiment': sentiment}).select('is_long')
            Dataset([{'answer.is_long': [False, False, True, False]}])
        """
        transformer = ResultsTransformer(self)
        return transformer.mutate(new_var_string, functions_dict)

    def long_view(
        self,
        scenario_fields: Optional[List[str]] = None,
        agent_fields: Optional[List[str]] = None,
        model_fields: Optional[List[str]] = None,
    ) -> Results:
        """Return a long view of the results.

        The columns are: agent_index, scenario_index, question_name, question_text, answer.
        It is returned as a ScenarioList.

        Args:
            scenario_fields: Optional list of scenario field names to include instead of scenario_index.
            agent_fields: Optional list of agent field names to include instead of agent_index.
            model_fields: Optional list of model field names to include instead of model_index.
        """
        from ..scenarios import Scenario, ScenarioList

        rows = []
        for result in self:
            # Pull indices if available (fallbacks to None if not present)
            agent_index = None
            scenario_index = None
            if hasattr(result, "indices") and result.indices:
                agent_index = result.indices.get("agent")
                scenario_index = result.indices.get("scenario")

            # Build the base row data
            row_data = {}

            # Add scenario fields or index
            if scenario_fields:
                scenario_data = result.get("scenario", {})
                for field in scenario_fields:
                    row_data[f"scenario.{field}"] = scenario_data.get(field)
            else:
                row_data["scenario_index"] = scenario_index

            # Add agent fields or index
            if agent_fields:
                agent_data = result.get("agent")
                for field in agent_fields:
                    # Agent is an object, access attributes with getattr
                    row_data[f"agent.{field}"] = (
                        getattr(agent_data, field, None) if agent_data else None
                    )
            else:
                row_data["agent_index"] = agent_index

            # Add model fields or index
            if model_fields:
                model_data = result.get("model")
                for field in model_fields:
                    # Model is an object, access attributes with getattr
                    row_data[f"model.{field}"] = (
                        getattr(model_data, field, None) if model_data else None
                    )

            # Iterate questions present in answers
            answers_dict = result["answer"]
            question_attrs = result["question_to_attributes"]
            for q_name, q_answer in answers_dict.items():
                q_text = None
                if q_name in question_attrs:
                    q_text = question_attrs[q_name].get("question_text")

                # Create a copy of row_data and add question-specific fields
                question_row = row_data.copy()
                question_row.update(
                    {
                        "question_name": q_name,
                        "question_text": q_text,
                        "answer": q_answer,
                    }
                )
                rows.append(Scenario(question_row))

        return ScenarioList(rows)

    def q_and_a(self, include_scenario: bool = False) -> "ScenarioList":
        """Return a ScenarioList with question-answer pairs from all Results with result indices.

        This method gets the q_and_a() from each component Result object and adds an
        index field to indicate which Result object each entry came from. Each row
        contains:
        - "result_index": Index of the Result object (0-based)
        - "question_name": The internal question name/identifier
        - "question_text": The rendered question text (with scenario placeholders filled in)
        - "answer": The recorded answer value
        - "comment": The recorded comment for the question (if any)

        If include_scenario is True, all scenario fields are also included.

        Args:
            include_scenario: Whether to include all scenario fields in each row.
                Defaults to False.

        Returns:
            ScenarioList: Combined question-answer data from all Result objects.

        Examples:
            >>> r = Results.example()
            >>> qa = r.q_and_a()
            >>> "result_index" in qa.parameters
            True
            >>> {"question_name", "question_text", "answer", "comment"}.issubset(set(qa.parameters))
            True
        """
        from ..scenarios import Scenario, ScenarioList

        all_scenarios = []

        for result_index, result in enumerate(self.data):
            # Get q_and_a from each Result object
            result_qa = result.q_and_a(include_scenario=include_scenario)

            # Add result_index to each scenario in the list
            for scenario in result_qa:
                scenario_dict = dict(scenario)
                scenario_dict["result_index"] = result_index
                all_scenarios.append(Scenario(scenario_dict))

        return ScenarioList(all_scenarios)

    @ensure_ready
    def rename(self, old_name: str, new_name: str) -> Results:
        """Rename an answer column in a Results object.

        This method delegates to the ResultsTransformer class to handle the renaming operation.

        Args:
            old_name: The current name of the column to rename
            new_name: The new name for the column

        Returns:
            Results: A new Results object with the column renamed

        Examples:
            >>> s = Results.example()
            >>> s.rename('how_feeling', 'how_feeling_new').select('how_feeling_new')
            Dataset([{'answer.how_feeling_new': ['OK', 'Great', 'Terrible', 'OK']}])
        """
        transformer = ResultsTransformer(self)
        return transformer.rename(old_name, new_name)

    @ensure_ready
    def shuffle(self, seed: Optional[str] = "edsl") -> Results:
        """Return a shuffled copy of the results using Fisher-Yates algorithm.

        Args:
            seed: Random seed for reproducibility.

        Returns:
            Results: A new Results object with shuffled data.
        """
        sampler = ResultsSampler(self)
        return sampler.shuffle(seed)

    @ensure_ready
    def sample(
        self,
        n: Optional[int] = None,
        frac: Optional[float] = None,
        with_replacement: bool = True,
        seed: Optional[str] = None,
    ) -> Results:
        """Return a random sample of the results.

        Args:
            n: The number of samples to take.
            frac: The fraction of samples to take (alternative to n).
            with_replacement: Whether to sample with replacement.
            seed: Random seed for reproducibility.

        Returns:
            Results: A new Results object containing the sampled data.
        """
        sampler = ResultsSampler(self)
        return sampler.sample(
            n=n, frac=frac, with_replacement=with_replacement, seed=seed
        )

    @ensure_ready
    def select(self, *columns: Union[str, list[str]]) -> "Dataset":
        """Extract specific columns from the Results into a Dataset.

        This method allows you to select specific columns from the Results object
        and transforms the data into a Dataset for further analysis and visualization.
        A Dataset is a more general-purpose data structure optimized for analysis
        operations rather than the hierarchical structure of Result objects.

        Args:
            *columns: Column names to select. Each column can be:
                - A simple attribute name (e.g., "how_feeling")
                - A fully qualified name with type (e.g., "answer.how_feeling")
                - A wildcard pattern (e.g., "answer.*" to select all answer fields)
                If no columns are provided, selects all data.

        Returns:
            A Dataset object containing the selected data.

        Notes:
            - Column names are automatically disambiguated if needed
            - When column names are ambiguous, specify the full path with data type
            - You can use wildcard patterns with "*" to select multiple related fields
            - Selecting with no arguments returns all data
            - Results are restructured in a columnar format in the Dataset

        Examples:
            >>> results = Results.example()

            >>> # Select a single column by name
            >>> results.select('how_feeling')
            Dataset([{'answer.how_feeling': ['OK', 'Great', 'Terrible', 'OK']}])

            >>> # Select multiple columns
            >>> ds = results.select('how_feeling', 'how_feeling_yesterday')
            >>> sorted([list(d.keys())[0] for d in ds])
            ['answer.how_feeling', 'answer.how_feeling_yesterday']

            >>> # Using fully qualified names with data type
            >>> results.select('answer.how_feeling')
            Dataset([{'answer.how_feeling': ['OK', 'Great', 'Terrible', 'OK']}])

            >>> # Using partial matching for column names
            >>> results.select('answer.how_feeling_y')
            Dataset([{'answer.how_feeling_yesterday': ['Great', 'Good', 'OK', 'Terrible']}])

            >>> # Select all columns (same as calling select with no arguments)
            >>> results.select('*.*')
            Dataset([...])
        """

        from .results_selector import Selector

        if len(self) == 0:
            from .exceptions import ResultsError

            raise ResultsError("No data to select from---the Results object is empty.")

        selector = Selector.from_cache_manager(self._cache_manager)
        return selector.select(*columns)

    @ensure_ready
    def bucket_by(self, *columns: str) -> dict[tuple, list["Result"]]:
        """Group Result objects into buckets keyed by the specified column values.

        Each key in the returned dictionary is a tuple containing the values of
        the requested columns (in the same order as supplied).  The associated
        value is a list of ``Result`` instances whose values match that key.

        Args:
            *columns: Names of the columns to group by.  Column identifiers
                follow the same rules used by :meth:`select` – they can be
                specified either as fully-qualified names (e.g. ``"agent.status"``)
                or by bare attribute name when unambiguous.

        Returns:
            dict[tuple, list[Result]]: Mapping from value tuples to lists of
            ``Result`` objects.

        Raises:
            ResultsError: If no columns are provided or an invalid column name is
                supplied.

        Examples:
            >>> r = Results.example()
            >>> buckets = r.bucket_by('how_feeling')
            >>> list(buckets.keys())  # doctest: +ELLIPSIS
            [('OK',), ('Great',), ('Terrible',)]
            >>> all(isinstance(v, list) for v in buckets.values())
            True
        """
        return self._grouper.bucket_by(*columns)

    def _parse_column(self, column: str) -> tuple[str, str]:
        """Parse a column name into a data type and key."""
        if "." in column:
            return column.split(".", 1)
        return self._cache_manager.key_to_data_type[column], column

    @ensure_ready
    def sort_by(self, *columns: str, reverse: bool = False) -> Results:
        """Sort the results by one or more columns.

        This method delegates to the ResultsTransformer class to handle the sorting operation.

        Args:
            columns: One or more column names as strings.
            reverse: A boolean that determines whether to sort in reverse order.

        Returns:
            Results: A new Results object with sorted data.

        Examples:
            >>> r = Results.example()
            >>> sorted_results = r.order_by('how_feeling')
            >>> len(sorted_results) == len(r)
            True
        """
        warnings.warn(
            "sort_by is deprecated. Use order_by instead.", DeprecationWarning
        )
        transformer = ResultsTransformer(self)
        return transformer.order_by(*columns, reverse=reverse)

    @ensure_ready
    def order_by(self, *columns: str, reverse: bool = False) -> Results:
        """Sort the results by one or more columns.

        This method delegates to the ResultsTransformer class to handle the sorting operation.

        Args:
            columns: One or more column names as strings.
            reverse: A boolean that determines whether to sort in reverse order.

        Returns:
            Results: A new Results object with sorted data.

        Examples:
            >>> r = Results.example()
            >>> sorted_results = r.order_by('how_feeling')
            >>> len(sorted_results) == len(r)
            True
        """
        transformer = ResultsTransformer(self)
        return transformer.order_by(*columns, reverse=reverse)

    @ensure_ready
    @wraps(ResultsFilter.filter)
    def filter(self, expression: str) -> Results:
        return self._results_filter.filter(expression)

    @classmethod
    def example(cls, randomize: bool = False) -> Results:
        """Return an example `Results` object.

        Example usage:

        >>> r = Results.example()

        :param randomize: if True, randomizes agent and scenario combinations
        """
        from ..jobs import Jobs
        from ..caching import Cache

        c = Cache()
        job = Jobs.example(randomize=randomize, test_model=True)
        results = job.run(
            cache=c,
            stop_on_exception=True,
            skip_retry=True,
            raise_validation_errors=True,
            disable_remote_cache=True,
            disable_remote_inference=True,
        )
        return results

    def rich_print(self):
        """Display an object as a table."""
        pass

    @ensure_ready
    def __str__(self):
        data = self.to_dict()["data"]
        return json.dumps(data, indent=4)

    def show_exceptions(self, traceback=False):
        """Print the exceptions."""
        if hasattr(self, "task_history"):
            self.task_history.show_exceptions(traceback)
        else:
            print("No exceptions to show.")

    def give_agents_uuid_names(self) -> None:
        """Give the agents uuid names."""
        import uuid

        for agent in self.agents:
            agent.name = uuid.uuid4()
        return None

    def fetch_remote(self, job_info: Any) -> bool:
        """Fetch remote Results object and update this instance with the data.

        This method delegates to the ResultsRemoteFetcher class to handle the remote fetching operation.

        Args:
            job_info: RemoteJobInfo object containing the job_uuid and other remote job details

        Returns:
            bool: True if the fetch was successful, False if the job is not yet completed.

        Raises:
            ResultsError: If there's an error during the fetch process.
        """
        fetcher = ResultsRemoteFetcher(self)
        return fetcher.fetch_remote(job_info)

    def fetch(self, polling_interval: Union[float, int] = 1.0) -> Results:
        """Poll the server for job completion and update this Results instance.

        This method delegates to the ResultsRemoteFetcher class to handle the polling and fetching operation.

        Args:
            polling_interval: Number of seconds to wait between polling attempts (default: 1.0)

        Returns:
            Results: The updated Results instance

        Raises:
            ResultsError: If no job info is available or if there's an error during fetch.
        """
        fetcher = ResultsRemoteFetcher(self)
        return fetcher.fetch(polling_interval)

    @ensure_ready
    def insert_sorted(self, item: "Result") -> None:
        """Insert a Result object into the Results list while maintaining sort order.

        Uses the 'order' attribute if present, otherwise falls back to 'iteration' attribute.
        Utilizes bisect for efficient insertion point finding.

        Args:
            item: A Result object to insert

        Examples:
            >>> r = Results.example()
            >>> new_result = r[0].copy()
            >>> new_result.order = 1.5  # Insert between items
            >>> r.insert_sorted(new_result)
        """
        return self._container.insert_sorted(item)

def main():  # pragma: no cover
    """Run example operations on a Results object.

    This function demonstrates basic filtering and mutation operations on
    a Results object, printing the output.

    Examples:
        >>> # This can be run directly as a script
        >>> # python -m edsl.results.results
        >>> # It will create example results and show filtering and mutation
    """
    from ..results import Results

    results = Results.example(debug=True)
    print(results.filter("how_feeling == 'Great'").select("how_feeling"))
    print(results.mutate("how_feeling_x = how_feeling + 'x'").select("how_feeling_x"))


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
