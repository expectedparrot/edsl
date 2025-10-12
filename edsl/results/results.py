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
from dataclasses import dataclass
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


from ..utilities import dict_hash
from ..dataset import ResultsOperationsMixin

from .result import Result
from .results_filter import ResultsFilter
from .results_serializer import ResultsSerializer
from .utilities import ensure_ready
from .job_cost_calculator import JobCostCalculator
from .results_sampler import ResultsSampler
from .data_type_cache_manager import DataTypeCacheManager
from .results_analyzer import ResultsAnalyzer
from .results_remote_fetcher import ResultsRemoteFetcher
from .results_scorer import ResultsScorer
from .results_transformer import ResultsTransformer
from .results_properties import ResultsProperties
from .results_container import ResultsContainer
from .results_grouper import ResultsGrouper

from .exceptions import (
    ResultsError,
    ResultsColumnNotFoundError,
    ResultsInvalidNameError,
)


@dataclass
class AgentListSplit:
    """Result of splitting a Results object into train/test AgentLists with corresponding surveys.
    
    Attributes:
        train: AgentList containing agents with training questions as traits
        test: AgentList containing agents with test questions as traits  
        train_survey: Survey object containing only the training questions
        test_survey: Survey object containing only the test questions
    """
    train: "AgentList"
    test: "AgentList"
    train_survey: "Survey"
    test_survey: "Survey"


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
        survey: Optional["Survey"] = None,
        data: Optional[list["Result"]] = None,
        name: Optional[str] = None,
        created_columns: Optional[list[str]] = None,
        cache: Optional["Cache"] = None,
        job_uuid: Optional[str] = None,
        total_results: Optional[int] = None,
        task_history: Optional["TaskHistory"] = None,
        sort_by_iteration: bool = False,
        data_class: Optional[type] = list,  # ResultsSQLList,
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
            data_class: The class to use for the data container (default: list).
        """
        self.completed = True
        self._fetching = False

        # Determine the data class to use
        if data is not None:
            # Use the class of the provided data if it's not a basic list
            self._data_class = (
                data.__class__ if not isinstance(data, list) else data_class
            )
        else:
            self._data_class = data_class

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
        import tempfile
        import os

        # Create a unique shelve path in the system temp directory
        self._shelve_path = os.path.join(
            tempfile.gettempdir(), f"edsl_results_{os.getpid()}"
        )
        self._shelf_keys = set()  # Track shelved result keys

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

        if name is not None:
            self.name = name
        else:
            self.name = None

        if hasattr(self, "_add_output_functions"):
            self._add_output_functions()

        self._report = None

    def view(self) -> None:
        """View the results in a Jupyter notebook."""
        from ..widgets.results_viewer import ResultsViewerWidget

        return ResultsViewerWidget(results=self)

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

    def get_answers(self, question_name: str) -> list:
        """Get the answers for a given question name.

        Args:
            question_name: The name of the question to fetch answers for.

        Returns:
            list: A list of answers, one from each result in the data.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> answers = r.get_answers('how_feeling')
            >>> isinstance(answers, list)
            True
            >>> len(answers) == len(r)
            True
        """
        return self._cache_manager.fetch_list("answer", question_name)

    def _summary(self) -> dict:
        """Return a dictionary containing summary statistics about the Results object.

        The summary includes:
        - Number of observations (results)
        - Number of unique agents
        - Number of unique models
        - Number of unique scenarios
        - Number of questions in the survey
        - Survey question names (truncated for readability)

        Returns:
            dict: A dictionary containing the summary statistics

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> summary = r._summary()
            >>> isinstance(summary, dict)
            True
            >>> all(key in summary for key in ['observations', 'agents', 'models', 'scenarios', 'questions', 'Survey question names'])
            True
            >>> summary['observations'] > 0
            True
            >>> summary['questions'] > 0
            True
        """
        import reprlib

        d = {
            "observations": len(self),
            "agents": len(set(self.agents)),
            "models": len(set(self.models)),
            "scenarios": len(set(self.scenarios)),
            "questions": len(self.survey),
            "Survey question names": reprlib.repr(self.survey.question_names),
        }
        return d

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


    def analyze(self, *question_names: str) -> 'QuestionAnalysis':
        try: 
            from edsl.lenny import Report 
        except ImportError:
            raise ValueError("Please install edsl as edsl[viz] to use the analyze method.")
        
        if self._report is None:
            self._report = Report(self)
        
        return self._report.analyze(*question_names)


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

    def __add__(self, other: Results) -> Results:
        """Add two Results objects together.

        Combines two Results objects into a new one. Both objects must have the same
        survey and created columns.

        Args:
            other: A Results object to add to this one.

        Returns:
            A new Results object containing data from both objects.

        Raises:
            ResultsError: If the surveys or created columns of the two objects don't match.

        Examples:
            >>> from edsl.results import Results
            >>> r1 = Results.example()
            >>> r2 = Results.example()
            >>> # Combine two Results objects
            >>> r3 = r1 + r2
            >>> len(r3) == len(r1) + len(r2)
            True

            >>> # Attempting to add incompatible Results
            >>> from unittest.mock import Mock
            >>> r4 = Results(survey=Mock())  # Different survey
            >>> try:
            ...     r1 + r4
            ... except ResultsError:
            ...     True
            True
        """
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
        return f"Results(data = {self.data}, survey = {repr(self.survey)}, created_columns = {self.created_columns})"

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
        """Convert the Results object to a dictionary representation.

        This method delegates to the ResultsSerializer class to handle the conversion
        of the Results object to a dictionary format suitable for serialization.

        Args:
            sort: Whether to sort the results data by hash before serialization
            add_edsl_version: Whether to include the EDSL version in the output
            include_cache: Whether to include cache data in the output
            include_task_history: Whether to include task history in the output
            include_cache_info: Whether to include cache information in result data
            offload_scenarios: Whether to optimize scenarios before serialization

        Returns:
            dict[str, Any]: Dictionary representation of the Results object
        """
        serializer = ResultsSerializer(self)
        return serializer.to_dict(
            sort=sort,
            add_edsl_version=add_edsl_version,
            include_cache=include_cache,
            include_task_history=include_task_history,
            include_cache_info=include_cache_info,
            offload_scenarios=offload_scenarios,
        )

    def compare(self, other_results: Results) -> dict:
        """
        Compare two Results objects and return the differences.
        """
        hashes_0 = [hash(result) for result in self]
        hashes_1 = [hash(result) for result in other_results]

        in_self_but_not_other = set(hashes_0).difference(set(hashes_1))
        in_other_but_not_self = set(hashes_1).difference(set(hashes_0))

        indicies_self = [hashes_0.index(h) for h in in_self_but_not_other]
        indices_other = [hashes_1.index(h) for h in in_other_but_not_self]
        return {
            "a_not_b": [self[i] for i in indicies_self],
            "b_not_a": [other_results[i] for i in indices_other],
        }

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
    def from_dict(cls, data: dict[str, Any]) -> Results:
        """Convert a dictionary to a Results object.

        This method delegates to the ResultsSerializer class to handle the conversion
        of a dictionary representation back to a Results object.

        Args:
            data: A dictionary representation of a Results object.

        Returns:
            Results: A new Results object created from the dictionary data

        Examples:
            >>> r = Results.example()
            >>> d = r.to_dict()
            >>> r2 = Results.from_dict(d)
            >>> r == r2
            True
        """
        return ResultsSerializer.from_dict(data)

    @property
    def columns(self) -> list[str]:
        """Return a list of all of the columns that are in the Results.

        Example:

        >>> r = Results.example()
        >>> r.columns
        ['agent.agent_index', ...]
        """
        return self._properties.columns

    @property
    def answer_keys(self) -> dict[str, str]:
        """Return a mapping of answer keys to question text.

        Example:

        >>> r = Results.example()
        >>> r.answer_keys
        {'how_feeling': 'How are you this {{ period }}?', 'how_feeling_yesterday': 'How were you feeling yesterday {{ period }}?'}
        """
        return self._properties.answer_keys

    @property
    def agents(self) -> AgentList:
        """Return a list of all of the agents in the Results.

        Example:

        >>> r = Results.example()
        >>> r.agents
        AgentList([Agent(traits = {'status': 'Joyful'}), Agent(traits = {'status': 'Joyful'}), Agent(traits = {'status': 'Sad'}), Agent(traits = {'status': 'Sad'})])
        """
        return self._properties.agents

    @property
    def models(self) -> ModelList:
        """Return a list of all of the models in the Results.

        Example:

        >>> r = Results.example()
        >>> r.models[0]
        Model(model_name = ...)
        """
        return self._properties.models

    def __eq__(self, other):
        return hash(self) == hash(other)

    @property
    def scenarios(self) -> ScenarioList:
        """Return a list of all of the scenarios in the Results.

        Example:

        >>> r = Results.example()
        >>> r.scenarios
        ScenarioList([Scenario({'period': 'morning'}), Scenario({'period': 'afternoon'}), Scenario({'period': 'morning'}), Scenario({'period': 'afternoon'})])
        """
        return self._properties.scenarios

    @property
    def agent_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the Agent data.

        Example:

        >>> r = Results.example()
        >>> r.agent_keys
        ['agent_index', 'agent_instruction', 'agent_name', 'status']
        """
        return self._properties.agent_keys

    @property
    def model_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the LanguageModel data.

        >>> r = Results.example()
        >>> r.model_keys
        ['canned_response', 'inference_service', 'model', 'model_index', 'temperature']
        """
        return self._properties.model_keys

    @property
    def scenario_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the Scenario data.

        >>> r = Results.example()
        >>> r.scenario_keys
        ['period', 'scenario_index']
        """
        return self._properties.scenario_keys

    @property
    def question_names(self) -> list[str]:
        """Return a list of all of the question names.

        Example:

        >>> r = Results.example()
        >>> r.question_names
        ['how_feeling', 'how_feeling_yesterday']
        """
        return self._properties.question_names

    @property
    def all_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the Results.

        Example:

        >>> r = Results.example()
        >>> r.all_keys
        ['agent_index', ...]
        """
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
                    row_data[f"agent.{field}"] = getattr(agent_data, field, None) if agent_data else None
            else:
                row_data["agent_index"] = agent_index

            # Add model fields or index
            if model_fields:
                model_data = result.get("model")
                for field in model_fields:
                    # Model is an object, access attributes with getattr
                    row_data[f"model.{field}"] = getattr(model_data, field, None) if model_data else None

            # Iterate questions present in answers
            answers_dict = result["answer"]
            question_attrs = result["question_to_attributes"]
            for q_name, q_answer in answers_dict.items():
                q_text = None
                if q_name in question_attrs:
                    q_text = question_attrs[q_name].get("question_text")

                # Create a copy of row_data and add question-specific fields
                question_row = row_data.copy()
                question_row.update({
                    "question_name": q_name,
                    "question_text": q_text,
                    "answer": q_answer,
                })
                rows.append(Scenario(question_row))

        return ScenarioList(rows)

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


    # def augmented_agents(self, *fields) -> "AgentList":
    #     """Convert the results to an agent list."""
    #     if len(self.agents) != len(self.data):
    #         raise ResultsError("Cannot convert results to agent list when there are multiple observations per agent.")

    #     new_agent_list = self.agents.copy()
    #     for field in fields:
    #         breakpoint()
    #         new_agent_list = new_agent_list.add_trait(field, self.select(field))
    #     return new_agent_list


    @ensure_ready
    def augmented_agents(self, *fields: str, include_existing_traits: bool = False) -> "AgentList":
        """Augment the agent list by adding specified fields as new traits.

        Takes field names (similar to the select method) and adds them as new traits
        to the agents in the agent list. This only works when there is a one-to-one
        mapping between agents and results.

        Args:
            *fields: Field names to add as traits. Field identifiers follow the same
                rules as :meth:`select` – they can be specified either as fully-qualified
                names (e.g. ``"answer.how_feeling"``) or by bare attribute name when
                unambiguous.

        Returns:
            AgentList: A new AgentList with the specified fields added as traits.

        Raises:
            ResultsError: If there are multiple observations per agent (e.g., from
                multiple scenarios or models), or if no fields are provided, or if
                an invalid field name is supplied.

        Examples:
            >>> from edsl import QuestionFreeText, Agent, Survey
            >>> from edsl.language_models import LanguageModel
            >>> q1 = QuestionFreeText(question_name="color", question_text="What is your favorite color?")
            >>> q2 = QuestionFreeText(question_name="food", question_text="What is your favorite food?")
            >>> survey = Survey([q1, q2])
            >>> agents = [Agent(traits={"name": "Alice"}), Agent(traits={"name": "Bob"})]
            >>> m = LanguageModel.example(test_model=True, canned_response="Blue")
            >>> results = survey.by(agents).by(m).run()
            >>> augmented_agents = results.augment_agents("color", "food")
            >>> len(augmented_agents) == len(agents)
            True
        """
        # Check if fields are provided
        if not fields:
            raise ResultsError("At least one field must be specified for augmentation.")

        # Check for one-to-one mapping between agents and results
        agent_counts = {}
        for result in self.data:
            agent = result.get("agent")
            agent_hash = hash(agent)
            agent_counts[agent_hash] = agent_counts.get(agent_hash, 0) + 1

        # If any agent has more than one result, throw an exception
        max_count = max(agent_counts.values()) if agent_counts else 0
        if max_count > 1:
            raise ResultsError(
                f"Cannot augment agents when there are multiple observations per agent. "
                f"Found agents with up to {max_count} observations. This typically happens "
                f"when using multiple scenarios or models."
            )

        # Get the current agents
        agent_list = self.agents.copy()
        if not include_existing_traits:
            agent_list.traits = {}

        # For each field, extract the values and add as a trait
        for field in fields:
            # Use select to get the field values
            dataset = self.select(field)
            
            # Dataset is a list of dictionaries, each with a single key-value pair
            # We need to extract the values from the first (and only) dictionary
            if len(dataset) == 0:
                raise ResultsError(f"No data found for field '{field}'.")
            
            # Get the column name (which might be different from the field name)
            column_name = list(dataset[0].keys())[0]
            values = dataset[0][column_name]
            
            # Extract the trait name from the field
            # If it's fully qualified like "answer.how_feeling", use "how_feeling"
            # Otherwise use the field name as-is
            if "." in field:
                trait_name = field.split(".", 1)[1]
            else:
                # Look up the actual key from the field name
                if field in self._cache_manager.key_to_data_type:
                    trait_name = field
                else:
                    # Fallback: extract from column_name
                    trait_name = column_name.split(".", 1)[1] if "." in column_name else column_name
            
            # Add the trait to the agent list
            agent_list = agent_list.add_trait(trait_name, values)

        return agent_list

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
    def filter(self, expression: str) -> Results:
        """Filter results based on a boolean expression.

        This method delegates to the ResultsFilter class to evaluate a boolean expression
        against each Result object in the collection and returns a new Results object
        containing only those that match.

        Args:
            expression: A string containing a Python expression that evaluates to a boolean.
                       The expression is applied to each Result object individually.
                       Can be a multi-line string for better readability.
                       Supports template-style syntax with {{ field }} notation.

        Returns:
            A new Results object containing only the Result objects that satisfy the expression.

        Raises:
            ResultsFilterError: If the expression is invalid or uses improper syntax
                (like using '=' instead of '==').

        Examples:
            >>> r = Results.example()

            >>> # Simple equality filter
            >>> r.filter("how_feeling == 'Great'").select('how_feeling')
            Dataset([{'answer.how_feeling': ['Great']}])

            >>> # Using OR condition
            >>> r.filter("how_feeling == 'Great' or how_feeling == 'Terrible'").select('how_feeling')
            Dataset([{'answer.how_feeling': ['Great', 'Terrible']}])

            >>> # Filter on agent properties
            >>> r.filter("agent.status == 'Joyful'").select('agent.status')
            Dataset([{'agent.status': ['Joyful', 'Joyful']}])
        """
        filter_handler = ResultsFilter(self)
        return filter_handler.filter(expression)

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

    def score(self, f: Callable) -> list:
        """Score the results using a function.

        This method delegates to the ResultsScorer class to handle the scoring operation.

        Args:
            f: A function that takes values from a Result object and returns a score.

        Returns:
            list: A list of scores, one for each Result object.

        Examples:
            >>> r = Results.example()
            >>> def f(status): return 1 if status == 'Joyful' else 0
            >>> r.score(f)
            [1, 1, 0, 0]
        """
        scorer = ResultsScorer(self)
        return scorer.score(f)

    def give_agents_uuid_names(self) -> None:
        """Give the agents uuid names."""
        import uuid
        for agent in self.agents:
            agent.name = uuid.uuid4()
        return None

    def score_with_answer_key(self, answer_key: dict) -> list:
        """Score the results using an answer key.

        This method delegates to the ResultsScorer class to handle the scoring operation.

        Args:
            answer_key: A dictionary that maps answer values to scores.

        Returns:
            list: A list of scores, one for each Result object.
        """
        scorer = ResultsScorer(self)
        return scorer.score_with_answer_key(answer_key)

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


    def split(
        self, 
        train_questions: Optional[List[str]] = None, 
        test_questions: Optional[List[str]] = None, 
        exclude_questions: Optional[List[str]] = None,
        num_questions: Optional[int] = None,
        seed: Optional[int] = None
    ) -> "AgentListSplit":
        """Create an AgentList from the results with a train/test split.
        
        Args:
            train_questions: Questions to use as TRAIN (deterministic, creates split)
            test_questions: Questions to use as TEST (deterministic, creates split)
            exclude_questions: Questions to fully exclude from both train and test
            num_questions: Number of questions to randomly select for TRAIN (stochastic, creates split).
                          If None and no other split parameters are provided, defaults to half of available questions.
            seed: Optional random seed for reproducible random selection (only used with num_questions)
            
        Returns:
            AgentListSplit with train/test splits and corresponding surveys.
            
        Raises:
            ResultsError: If survey has skip logic or piping (not supported for splits)
            
        Examples:
            >>> # Deterministic split - specify train questions
            >>> # split = results.split(train_questions=['q1', 'q2'])
            >>> # split.train has q1, q2; split.test has all others
            >>> 
            >>> # Deterministic split - specify test questions  
            >>> # split = results.split(test_questions=['q8', 'q9'])
            >>> # split.train has all others; split.test has q8, q9
            >>> 
            >>> # Stochastic split - randomly select 3 questions for train
            >>> # split = results.split(num_questions=3, seed=42)
            >>> # split.train has 3 random questions; split.test has remaining
            >>> 
            >>> # Default 50/50 split - no parameters specified
            >>> # split = results.split(seed=42)
            >>> # split.train has half the questions; split.test has the other half
            >>> 
            >>> # Exclude certain questions entirely
            >>> # split = results.split(num_questions=3, exclude_questions=['q10'])
        """
        from ..agents import AgentList
        import random
        import re
        
        # Check if survey has skip logic (non-default rules)
        if len(self.survey.rule_collection.non_default_rules) > 0:
            raise ResultsError(
                "Cannot create agent list splits from surveys with skip logic. "
                "Skip logic creates dependencies between questions that would be broken by splitting."
            )
        
        # Check if survey has piping ({{ }} syntax in question text or options)
        piping_pattern = re.compile(r'\{\{.*?\}\}')
        for question in self.survey.questions:
            # Check question text
            if piping_pattern.search(question.question_text):
                raise ResultsError(
                    f"Cannot create agent list splits from surveys with piping. "
                    f"Question '{question.question_name}' has piping in its question_text."
                )
            # Check question options if they exist
            if hasattr(question, 'question_options') and question.question_options:
                for option in question.question_options:
                    if isinstance(option, str) and piping_pattern.search(option):
                        raise ResultsError(
                            f"Cannot create agent list splits from surveys with piping. "
                            f"Question '{question.question_name}' has piping in its options."
                        )
        
        # Ensure only one splitting method is used
        split_params = sum([
            train_questions is not None,
            test_questions is not None,
            num_questions is not None
        ])
        if split_params > 1:
            raise ValueError(
                "Only one of train_questions, test_questions, or num_questions can be specified"
            )
        
        all_questions = list(self.survey.question_names)
        
        # Apply exclusions first
        if exclude_questions is not None:
            for q in exclude_questions:
                if q not in all_questions:
                    raise ValueError(f"Question {q} not found in survey.")
            all_questions = [q for q in all_questions if q not in exclude_questions]
        
        # Case 1: train_questions - these become TRAIN split
        if train_questions is not None:
            # Validate questions exist
            for q in train_questions:
                if q not in all_questions:
                    raise ValueError(f"Question {q} not found in survey (or was excluded).")
            
            train_questions_list = train_questions
            test_questions_list = [q for q in all_questions if q not in train_questions_list]
            
            if not train_questions_list:
                raise ValueError("train_questions resulted in an empty list")
            if not test_questions_list:
                raise ValueError("No questions left for test split after selecting train questions")
            
            train_agent_list = AgentList.from_results(self, train_questions_list)
            test_agent_list = AgentList.from_results(self, test_questions_list)
            
            train_survey = self.survey.select(*train_questions_list)
            test_survey = self.survey.select(*test_questions_list)
            
            return AgentListSplit(
                train=train_agent_list,
                test=test_agent_list,
                train_survey=train_survey,
                test_survey=test_survey
            )
        
        # Case 2: test_questions - these become TEST split
        if test_questions is not None:
            # Validate questions exist
            for q in test_questions:
                if q not in all_questions:
                    raise ValueError(f"Question {q} not found in survey (or was excluded).")
            
            test_questions_list = test_questions
            train_questions = [q for q in all_questions if q not in test_questions_list]
            
            if not test_questions_list:
                raise ValueError("test_questions resulted in an empty list")
            if not train_questions:
                raise ValueError("No questions left for train split after selecting test questions")
            
            train_agent_list = AgentList.from_results(self, train_questions)
            test_agent_list = AgentList.from_results(self, test_questions_list)
            
            train_survey = self.survey.select(*train_questions)
            test_survey = self.survey.select(*test_questions_list)
            
            return AgentListSplit(
                train=train_agent_list,
                test=test_agent_list,
                train_survey=train_survey,
                test_survey=test_survey
            )
        
        # Case 3: num_questions - randomly select for TRAIN split (stochastic)
        # If num_questions is None, default to half of available questions
        if num_questions is None:
            num_questions = len(all_questions) // 2
        
        if num_questions > len(all_questions):
            raise ValueError(
                f"num_questions ({num_questions}) cannot exceed available questions ({len(all_questions)})"
            )
        
        # Set seed if provided
        if seed is not None:
            random.seed(seed)
        
        # Randomly select questions for train split
        train_questions = random.sample(all_questions, num_questions)
        test_questions_list = [q for q in all_questions if q not in train_questions]
        
        if not test_questions_list:
            raise ValueError("No questions left for test split after random selection")
        
        train_agent_list = AgentList.from_results(self, train_questions)
        test_agent_list = AgentList.from_results(self, test_questions_list)
        
        train_survey = self.survey.select(*train_questions)
        test_survey = self.survey.select(*test_questions_list)
        
        return AgentListSplit(
            train=train_agent_list,
            test=test_agent_list,
            train_survey=train_survey,
            test_survey=test_survey
        )

    def spot_issues(self, models: Optional[ModelList] = None) -> Results:
        """Run a survey to spot issues and suggest improvements for prompts that had no model response.

        This method delegates to the ResultsAnalyzer class to handle the analysis and debugging.

        Args:
            models: Optional ModelList to use for the analysis. If None, uses the default model.

        Returns:
            Results: A new Results object containing the analysis and suggestions for improvement.

        Notes:
            Future version: Allow user to optionally pass a list of questions to review,
            regardless of whether they had a null model response.
        """
        analyzer = ResultsAnalyzer(self)
        return analyzer.spot_issues(models)

    def shelve_result(self, result: "Result") -> str:
        """Store a Result object in persistent storage using its hash as the key.

        This method delegates to the ResultsSerializer class to handle the shelving operation.

        Args:
            result: A Result object to store

        Returns:
            str: The hash key for retrieving the result later

        Raises:
            ResultsError: If there's an error storing the Result
        """
        serializer = ResultsSerializer(self)
        return serializer.shelve_result(result)

    def get_shelved_result(self, key: str) -> "Result":
        """Retrieve a Result object from persistent storage.

        This method delegates to the ResultsSerializer class to handle the retrieval operation.

        Args:
            key: The hash key of the Result to retrieve

        Returns:
            Result: The stored Result object

        Raises:
            ResultsError: If the key doesn't exist or if there's an error retrieving the Result
        """
        serializer = ResultsSerializer(self)
        return serializer.get_shelved_result(key)

    @property
    def shelf_keys(self) -> set:
        """Return a copy of the set of shelved result keys.

        This property delegates to the ResultsSerializer class.
        """
        return self._properties.shelf_keys

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

    def insert_from_shelf(self) -> None:
        """Move all shelved results into memory using insert_sorted method.

        This method delegates to the ResultsSerializer class to handle the shelf operations.
        Clears the shelf after successful insertion.

        This method preserves the original order of results by using their 'order'
        attribute if available, which ensures consistent ordering even after
        serialization/deserialization.

        Raises:
            ResultsError: If there's an error accessing or clearing the shelf
        """
        serializer = ResultsSerializer(self)
        return serializer.insert_from_shelf()

    def to_disk(self, filepath: str) -> None:
        """Serialize the Results object to a zip file, preserving the SQLite database.

        This method delegates to the ResultsSerializer class to handle the disk serialization.

        This method creates a zip file containing:
        1. The SQLite database file from the data container
        2. A metadata.json file with the survey, created_columns, and other non-data info
        3. The cache data if present

        Args:
            filepath: Path where the zip file should be saved

        Raises:
            ResultsError: If there's an error during serialization
        """
        serializer = ResultsSerializer(self)
        return serializer.to_disk(filepath)

    @classmethod
    def from_disk(cls, filepath: str) -> "Results":
        """Load a Results object from a zip file.

        This method delegates to the ResultsSerializer class to handle the disk deserialization.

        This method:
        1. Extracts the SQLite database file
        2. Loads the metadata
        3. Creates a new Results instance with the restored data

        Args:
            filepath: Path to the zip file containing the serialized Results

        Returns:
            Results: A new Results instance with the restored data

        Raises:
            ResultsError: If there's an error during deserialization
        """
        return ResultsSerializer.from_disk(filepath)


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
