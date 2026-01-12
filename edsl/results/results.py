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
from typing import Optional, Callable, Any, Union, List, Dict, TYPE_CHECKING
from collections.abc import MutableSequence

from ..base import Base

if TYPE_CHECKING:
    from ..interviews import Interview
    from ..surveys import Survey
    from ..agents import AgentList
    from ..reports.report import QuestionAnalysis
    from ..scenarios import ScenarioList
    from ..results import Result
    from ..tasks import TaskHistory
    from ..language_models import ModelList
    from ..dataset import Dataset
    from ..caching import Cache
    from .results_transcript import Transcripts
    from .vibes import ResultsVibeAnalysis
    from .vibes.vibe_accessor import ResultsVibeAccessor


from ..utilities import dict_hash
from ..dataset import ResultsOperationsMixin

# Import event-sourcing infrastructure
from ..versioning import GitMixin, event
from ..store import (
    Store,
    AppendRowEvent,
    SetMetaEvent,
    apply_event,
)

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
from .results_ml import ResultsML
from .results_transformer import ResultsTransformer
from .results_properties import ResultsProperties
from .results_grouper import ResultsGrouper

from .exceptions import (
    ResultsError,
    ResultsColumnNotFoundError,
    ResultsInvalidNameError,
)


class ResultCodec:
    """Codec for Result objects - handles encoding/decoding for the Store."""

    def encode(self, obj: Union["Result", dict[str, Any]]) -> dict[str, Any]:
        """Encode a Result to a dictionary for storage."""
        if isinstance(obj, dict):
            return dict(obj)
        return obj.to_dict(add_edsl_version=False, include_cache_info=True)

    def decode(self, data: dict[str, Any]) -> "Result":
        """Decode a dictionary back to a Result object."""
        return Result.from_dict(data)


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


from .results_likely_remove import ResultsLikelyRemoveMixin


class ResultsMeta(Base.__class__):
    """Metaclass for Results that enables dynamic service accessor access.
    
    Inherits from Base's metaclass (RegisterSubclassesMeta) to avoid metaclass conflicts.
    
    This metaclass intercepts class-level attribute access (e.g., Results.charts)
    and returns service accessor instances from the edsl.services registry.
    
    Examples:
        >>> accessor = Results.charts  # Returns charts accessor
    """
    
    def __getattr__(cls, name: str):
        """Called when Results.{name} is accessed and {name} isn't found normally."""
        # Lazy import to avoid circular dependencies
        from edsl.services.accessors import get_service_accessor
        
        accessor = get_service_accessor(name, owner_class=cls)
        if accessor is not None:
            return accessor
        
        # Standard AttributeError
        raise AttributeError(f"type object 'Results' has no attribute '{name}'")


class Results(
    GitMixin, MutableSequence, ResultsOperationsMixin, ResultsLikelyRemoveMixin, Base,
    metaclass=ResultsMeta
):
    """A collection of Result objects with powerful data analysis capabilities.

    The Results class is the primary container for working with data from EDSL surveys.
    It provides a rich set of methods for data analysis, transformation, and visualization
    inspired by data manipulation libraries like dplyr and pandas. The Results class
    implements a functional, fluent interface for data manipulation where each method
    returns a new Results object, allowing method chaining.

    The Results class uses an event-sourcing architecture where all mutations are
    captured as events and applied to a Store backend. This enables version control,
    immutability patterns, and integration with git-like operations via GitMixin.

    Note: Results is fundamentally append-only. Result objects are immutable and cannot
    be modified after creation. The only supported mutation is appending new Results.

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

    # Event-sourcing infrastructure
    _versioned = "store"
    _store_class = Store
    _event_handler = apply_event
    _codec = ResultCodec()

    # Allowed instance attributes - minimal set for truly immutable Results
    _allowed_attrs = frozenset(
        {
            # Core state - the single source of truth
            "store",
            # Properties with setters (these delegate to cache attributes)
            "completed",
            "_fetching",
            "_report",
            # Runtime state caches (backing stores for properties)
            "_completed_cache",
            "_fetching_cache",
            # Lazy-initialized helper caches (private backing stores for properties)
            "_cache_manager_cache",
            "_properties_cache",
            "_grouper_cache",
            "_report_cache",
            "_shelve_path_cache",
            "_shelf_keys_cache",
            # GitMixin
            "_git",
            "_needs_git_init",
            "_last_push_result",
            # Remote job info (runtime only)
            "job_info",
            # Job execution runtime attributes (not persisted in store)
            "bucket_collection",
            "jobs_runner_status",
            "key_lookup",
            "order",
        }
    )

    # =========================================================================
    # Properties that read from store - these make Results truly immutable
    # =========================================================================

    @property
    def data(self) -> list:
        """Returns the list of Result objects, decoded from the store.

        This is a computed property - the source of truth is always self.store.entries.
        """
        if not hasattr(self, "store") or self.store is None:
            return []
        return [self._codec.decode(entry) for entry in self.store.entries]

    @property
    def survey(self) -> Optional["Survey"]:
        """Get survey from store meta."""
        if not hasattr(self, "store") or self.store is None:
            return None
        survey_dict = self.store.meta.get("survey")
        if survey_dict is None:
            return None
        from ..surveys import Survey

        return Survey.from_dict(survey_dict)

    @property
    def cache(self) -> "Cache":
        """Get cache from store meta."""
        from ..caching import Cache

        if not hasattr(self, "store") or self.store is None:
            return Cache()
        cache_dict = self.store.meta.get("cache")
        if cache_dict is None:
            return Cache()
        return Cache.from_dict(cache_dict)

    @property
    def task_history(self) -> "TaskHistory":
        """Get task_history from store meta."""
        from ..tasks import TaskHistory

        if not hasattr(self, "store") or self.store is None:
            return TaskHistory(interviews=[])
        th_dict = self.store.meta.get("task_history")
        if th_dict is None:
            return TaskHistory(interviews=[])
        return TaskHistory.from_dict(th_dict)

    @property
    def name(self) -> Optional[str]:
        """Get name from store meta."""
        if not hasattr(self, "store") or self.store is None:
            return None
        return self.store.meta.get("name")

    @property
    def _job_uuid(self) -> Optional[str]:
        """Get job_uuid from store meta."""
        if not hasattr(self, "store") or self.store is None:
            return None
        return self.store.meta.get("job_uuid")

    @property
    def job_uuid(self) -> Optional[str]:
        """Get job_uuid from store meta."""
        return self._job_uuid

    @job_uuid.setter
    def job_uuid(self, value: str) -> None:
        """Set job_uuid in store meta."""
        if hasattr(self, "store") and self.store is not None:
            self.store.meta["job_uuid"] = value

    @property
    def results_uuid(self) -> Optional[str]:
        """Get results_uuid from store meta."""
        if not hasattr(self, "store") or self.store is None:
            return None
        return self.store.meta.get("results_uuid")

    @results_uuid.setter
    def results_uuid(self, value: str) -> None:
        """Set results_uuid in store meta."""
        if hasattr(self, "store") and self.store is not None:
            self.store.meta["results_uuid"] = value

    @property
    def _total_results(self) -> Optional[int]:
        """Get total_results from store meta."""
        if not hasattr(self, "store") or self.store is None:
            return None
        return self.store.meta.get("total_results")

    # =========================================================================
    # Runtime state properties (not persisted in store)
    # =========================================================================

    @property
    def completed(self) -> bool:
        """Get completed flag (defaults to True)."""
        if not hasattr(self, "_completed_cache"):
            return True  # Default
        return self._completed_cache

    @completed.setter
    def completed(self, value: bool):
        """Set completed flag."""
        object.__setattr__(self, "_completed_cache", value)

    @property
    def _fetching(self) -> bool:
        """Get fetching flag (defaults to False)."""
        if not hasattr(self, "_fetching_cache"):
            return False  # Default
        return self._fetching_cache

    @_fetching.setter
    def _fetching(self, value: bool):
        """Set fetching flag."""
        object.__setattr__(self, "_fetching_cache", value)

    # =========================================================================
    # Lazy-initialized helper objects (cached for performance)
    # =========================================================================

    @property
    def _cache_manager(self) -> "DataTypeCacheManager":
        """Get cache manager, creating if needed."""
        if (
            not hasattr(self, "_cache_manager_cache")
            or self._cache_manager_cache is None
        ):
            object.__setattr__(self, "_cache_manager_cache", DataTypeCacheManager(self))
        return self._cache_manager_cache

    @property
    def _properties(self) -> "ResultsProperties":
        """Get properties handler, creating if needed."""
        if not hasattr(self, "_properties_cache") or self._properties_cache is None:
            object.__setattr__(self, "_properties_cache", ResultsProperties(self))
        return self._properties_cache

    @property
    def _grouper(self) -> "ResultsGrouper":
        """Get grouper handler, creating if needed."""
        if not hasattr(self, "_grouper_cache") or self._grouper_cache is None:
            object.__setattr__(self, "_grouper_cache", ResultsGrouper(self))
        return self._grouper_cache

    @property
    def scoring(self) -> "ResultsScorer":
        """Access scoring methods via namespace.

        Returns:
            ResultsScorer: Accessor for scoring methods.

        Examples:
            >>> r = Results.example()
            >>> def f(status): return 1 if status == 'Joyful' else 0
            >>> r.scoring.score(f)
            [1, 1, 0, 0]
        """
        return ResultsScorer(self)

    @property
    def ml(self) -> "ResultsML":
        """Access machine learning methods via namespace.

        Returns:
            ResultsML: Accessor for ML methods like train/test splitting.

        Examples:
            >>> # Create a train/test split
            >>> # split = results.ml.split(train_questions=['q1', 'q2'])
            >>> # split.train, split.test  # AgentLists
            >>> # split.train_survey, split.test_survey  # Surveys
        """
        return ResultsML(self)

    @property
    def _report(self):
        """Get report, creating if needed."""
        if not hasattr(self, "_report_cache"):
            object.__setattr__(self, "_report_cache", None)
        return self._report_cache

    @_report.setter
    def _report(self, value):
        """Set report cache."""
        object.__setattr__(self, "_report_cache", value)

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


    def __setattr__(self, name: str, value: Any) -> None:
        """Restrict attribute setting to allowed attributes only.

        This prevents external code from using Results instances to store
        temporary data, enforcing immutability through the event-based Store mechanism.
        """
        # Check if there's a property with a setter for this name
        prop = getattr(type(self), name, None)
        if isinstance(prop, property) and prop.fset is not None:
            prop.fset(self, value)
        elif name in self._allowed_attrs:
            super().__setattr__(name, value)
        else:
            raise AttributeError(
                f"Cannot set attribute '{name}' on Results. "
                f"Results is immutable - use event-based methods to modify data."
            )

    def __getattr__(self, name: str):
        """Intercept attribute access to provide service accessor instances.
        
        This method is called when an attribute isn't found normally on the instance.
        It checks if the attribute name matches a registered service and returns
        the appropriate accessor bound to this Results instance.
        
        Examples:
            >>> r = Results.example()
            >>> _ = r.charts  # Returns charts accessor bound to this instance
        """
        # Lazy import to avoid circular dependencies
        from edsl.services.accessors import get_service_accessor
        
        accessor = get_service_accessor(name, instance=self)
        if accessor is not None:
            return accessor
        
        raise AttributeError(f"'Results' object has no attribute '{name}'")

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
        # Handle pull from string UUID
        if survey is not None and isinstance(survey, str):
            pulled_results = Results.pull(survey)
            self.__dict__.update(pulled_results.__dict__)
            return

        # Runtime state (not persisted in store)
        self.completed = True
        self._fetching = False

        # Sort data appropriately before initialization if needed
        if data and sort_by_iteration:
            has_order = any(hasattr(item, "order") for item in data)
            if has_order:

                def get_order(item):
                    if hasattr(item, "order"):
                        return item.order
                    return item.data.get("iteration", 0) * 1000

                data = sorted(data, key=get_order)
            else:
                data = sorted(data, key=lambda x: x.data.get("iteration", 0))

        # Initialize GitMixin
        super().__init__()

        # Build the store directly - this is the single source of truth
        from ..caching import Cache
        from ..tasks import TaskHistory

        entries = [self._codec.encode(result) for result in (data or [])]

        meta: Dict[str, Any] = {
            "created_columns": created_columns or [],
        }

        if survey is not None:
            meta["survey"] = survey.to_dict(add_edsl_version=False)

        if cache is not None:
            meta["cache"] = cache.to_dict()
        else:
            meta["cache"] = Cache().to_dict()

        if task_history is not None:
            meta["task_history"] = task_history.to_dict()
        else:
            meta["task_history"] = TaskHistory(interviews=[]).to_dict()

        if job_uuid is not None:
            meta["job_uuid"] = job_uuid
        if total_results is not None:
            meta["total_results"] = total_results
        if name is not None:
            meta["name"] = name

        self.store = Store(entries=entries, meta=meta)

        if hasattr(self, "_add_output_functions"):
            self._add_output_functions()

    # =========================================================================
    # Lazy-initialized helper properties
    # =========================================================================

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

    @event
    def add_task_history_entry(self, interview: "Interview") -> SetMetaEvent:
        """Add an interview to the task history (returns new Results via event)."""
        from ..tasks import TaskHistory

        # Get current task_history and add the interview to it
        current_th = self.task_history
        # Create a new TaskHistory and manually copy over the existing data
        new_th = TaskHistory(
            interviews=[],  # Start empty, we'll add refs directly
            include_traceback=current_th.include_traceback,
        )
        # Copy existing interview refs directly (they're already InterviewReference objects)
        new_th.total_interviews = list(current_th.total_interviews)
        new_th._interviews = dict(current_th._interviews)
        # Add the new interview through the proper method
        new_th.add_interview(interview)
        return SetMetaEvent(key="task_history", value=new_th.to_dict())

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
        """Return a subset of the cache containing only keys relevant to these results."""
        cache_keys = self._cache_keys()
        return cache.subset(cache_keys)

    @event
    def set_cache(self, cache: Cache) -> SetMetaEvent:
        """Set the cache for these results (returns new Results via event)."""
        return SetMetaEvent(key="cache", value=cache.to_dict())

    @event
    def set_task_history(self, task_history: "TaskHistory") -> SetMetaEvent:
        """Set the task_history for these results (returns new Results via event)."""
        return SetMetaEvent(key="task_history", value=task_history.to_dict())

    @event
    def set_name(self, name: str) -> SetMetaEvent:
        """Set the name for these results (returns new Results via event)."""
        return SetMetaEvent(key="name", value=name)

    @event
    def set_created_columns(self, created_columns: list[str]) -> SetMetaEvent:
        """Set the created_columns for these results (returns new Results via event)."""
        return SetMetaEvent(key="created_columns", value=created_columns)

    def analyze(self, *question_names: str, verbose: bool = False):
        """Analyze answer distributions for specified questions.
        
        Provides statistical summaries and visualizations for questions in
        the Results. Uses the answer_analysis service for computation.
        
        Args:
            *question_names: Question names to analyze. If none provided,
                            analyzes all questions.
            verbose: Show progress messages. Default False.
        
        Returns:
            AnalysisResult: Rich analysis with summaries and visualizations.
            
        Example:
            r = Results.example()
            analysis = r.analyze('how_feeling')   # One question
            analysis = r.analyze('q1', 'q2')      # Multiple questions  
            analysis = r.analyze()                # All questions
        """
        from .analysis_result import AnalysisResult
        from edsl.services import dispatch
        
        # Default to all questions if none specified
        if not question_names:
            question_names = tuple(self.question_names)
        
        # Serialize results for service
        results_data = self.to_dict()
        
        # Call service for each question
        analysis_results = {}
        for q_name in question_names:
            try:
                pending = dispatch("answer_analysis", {
                    "operation": "show",
                    "results_data": results_data,
                    "question": q_name,
                })
                analysis_results[q_name] = pending.result(verbose=verbose)
            except Exception as e:
                analysis_results[q_name] = {"status": "error", "error": str(e)}
        
        return AnalysisResult(analysis_results, self)

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
        """Get item(s) from the Results container.

        Args:
            i: Index (int), slice, or string key for accessing data

        Returns:
            Individual Result, new Results object, or dictionary value

        Raises:
            ResultsError: If invalid argument type is provided
        """
        if isinstance(i, int):
            return self.data[i]
        if isinstance(i, slice):
            return self.__class__(survey=self.survey, data=self.data[i])
        if isinstance(i, str):
            return self.to_dict()[i]
        raise ResultsError("Invalid argument type for indexing Results object")

    @ensure_ready
    def __setitem__(self, i, item):
        """Block item assignment - Results is immutable.

        Results objects are append-only. Individual Result objects cannot be
        replaced or modified after creation.

        Raises:
            ResultsError: Always raised as Results is immutable.
        """
        raise ResultsError(
            "Cannot set items in Results - Results is immutable. "
            "Result objects cannot be modified after creation. "
            "Use append_result() to add new results."
        )

    @ensure_ready
    def __delitem__(self, i):
        """Block item deletion - Results is immutable.

        Results objects are append-only. Individual Result objects cannot be
        deleted after creation.

        Raises:
            ResultsError: Always raised as Results is immutable.
        """
        raise ResultsError(
            "Cannot delete items from Results - Results is immutable. "
            "Result objects cannot be removed after creation."
        )

    @ensure_ready
    def __len__(self):
        """Return the number of Result objects in this Results container."""
        return len(self.data)

    @ensure_ready
    def insert(self, index, item):
        """Block arbitrary insertion - Results is append-only.

        Results objects only support appending new results at the end.
        Use append_result() to add new results.

        Raises:
            ResultsError: Always raised as Results is append-only.
        """
        raise ResultsError(
            "Cannot insert items at arbitrary positions in Results - Results is append-only. "
            "Use append_result() to add new results at the end."
        )

    @event
    def append_result(self, result: "Result") -> AppendRowEvent:
        """Append a new Result to this Results object.

        This is the primary way to add new results. Returns a new Results
        instance with the appended result (Results is immutable).

        Args:
            result: A Result object to append.

        Returns:
            AppendRowEvent: The event representing the append operation.

        Note:
            Due to the @event decorator, this method returns a new Results
            instance with the appended result, not the event itself.
        """
        encoded = self._codec.encode(result)
        return AppendRowEvent(row=encoded)

    @ensure_ready
    def extend(self, other) -> "Results":
        """Extend the Results by appending items from another iterable.

        This method creates a new Results instance with all items from both
        this Results and the other iterable. Results is immutable - each append
        returns a new instance.

        Args:
            other: Iterable of Result objects to append.

        Returns:
            Results: A new Results instance with the extended data.
        """
        # Use event-sourced append for each item
        result = self
        for item in other:
            result = result.append(item)
        return result

    def _repr_html_(self):
        if not self.completed:
            if hasattr(self, "job_info"):
                self.fetch_remote(self.job_info)

            if not self.completed:
                return "Results not ready to call"

        return super()._repr_html_()

    @ensure_ready
    def __repr__(self) -> str:
        """Return a string representation of the Results.

        Uses traditional repr format when running doctests, otherwise uses
        rich-based display for better readability. In Jupyter notebooks,
        returns a minimal string since _repr_html_ handles the display.
        """
        import os

        if os.environ.get("EDSL_RUNNING_DOCTESTS") == "True":
            return self._eval_repr_()

        # Check if we're in a Jupyter notebook environment
        # If so, return minimal representation since _repr_html_ will handle display
        try:
            from IPython import get_ipython

            ipy = get_ipython()
            if ipy is not None and "IPKernelApp" in ipy.config:
                # We're in a Jupyter notebook/kernel, not IPython terminal
                return "Results(...)"
        except (NameError, ImportError):
            pass

        return self._summary_repr()

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the Results.

        This representation can be used with eval() to recreate the Results object.
        Used primarily for doctests and debugging.
        """
        return f"Results(data = {self.data}, survey = {repr(self.survey)}, created_columns = {self.created_columns})"

    def _summary_repr(self, max_text_preview: int = 60, max_items: int = 25) -> str:
        """Generate a summary representation of the Results with Rich formatting.

        Args:
            max_text_preview: Maximum characters to show for question text previews
            max_items: Maximum number of items to show in lists before truncating
        """
        from rich.console import Console
        from rich.text import Text
        import io
        from edsl.config import RICH_STYLES

        # Build the Rich text
        output = Text()
        output.append("Results(\n", style=RICH_STYLES["primary"])
        output.append(
            f"    num_observations={len(self)},\n", style=RICH_STYLES["default"]
        )
        output.append(
            f"    num_agents={len(set(self.agents))},\n", style=RICH_STYLES["default"]
        )
        output.append(
            f"    num_models={len(set(self.models))},\n", style=RICH_STYLES["default"]
        )
        output.append(
            f"    num_scenarios={len(set(self.scenarios))},\n",
            style=RICH_STYLES["default"],
        )

        # Show agent traits
        if len(self.agents) > 0:
            agent_keys = self.agent_keys
            if agent_keys:
                output.append("    agent_traits: [", style=RICH_STYLES["default"])
                # Filter out internal fields
                trait_keys = [k for k in agent_keys if not k.startswith("agent_")]
                if trait_keys:
                    output.append(
                        f"{', '.join(repr(k) for k in trait_keys[:max_items])}",
                        style=RICH_STYLES["secondary"],
                    )
                    if len(trait_keys) > max_items:
                        output.append(
                            f", ... ({len(trait_keys) - max_items} more)",
                            style=RICH_STYLES["dim"],
                        )
                output.append("],\n", style=RICH_STYLES["default"])

        # Show scenario fields
        if len(self.scenarios) > 0:
            scenario_keys = self.scenario_keys
            if scenario_keys:
                output.append("    scenario_fields: [", style=RICH_STYLES["default"])
                # Filter out internal fields
                field_keys = [k for k in scenario_keys if not k.startswith("scenario_")]
                if field_keys:
                    output.append(
                        f"{', '.join(repr(k) for k in field_keys[:max_items])}",
                        style=RICH_STYLES["secondary"],
                    )
                    if len(field_keys) > max_items:
                        output.append(
                            f", ... ({len(field_keys) - max_items} more)",
                            style=RICH_STYLES["dim"],
                        )
                output.append("],\n", style=RICH_STYLES["default"])

        # Show question information with text previews
        if self.survey and hasattr(self.survey, "questions"):
            questions = self.survey.questions
            output.append(
                f"    num_questions={len(questions)},\n", style=RICH_STYLES["default"]
            )
            output.append("    questions: [\n", style=RICH_STYLES["default"])

            # Show up to max_items questions with text previews
            for question in questions[:max_items]:
                q_name = question.question_name
                q_text = question.question_text

                # Truncate text if too long
                if len(q_text) > max_text_preview:
                    q_text = q_text[:max_text_preview] + "..."

                output.append("        ", style=RICH_STYLES["default"])
                output.append(f"'{q_name}'", style=RICH_STYLES["secondary"])
                output.append(": ", style=RICH_STYLES["default"])
                output.append(f'"{q_text}"', style=RICH_STYLES["dim"])
                output.append(",\n", style=RICH_STYLES["default"])

            if len(questions) > max_items:
                output.append(
                    f"        ... ({len(questions) - max_items} more)\n",
                    style=RICH_STYLES["dim"],
                )

            output.append("    ],\n", style=RICH_STYLES["default"])

        # Show created columns if any
        if self.created_columns:
            output.append(
                f"    created_columns={self.created_columns}\n",
                style=RICH_STYLES["key"],
            )

        output.append(")", style=RICH_STYLES["primary"])

        # Render to string
        console = Console(file=io.StringIO(), force_terminal=True, width=120)
        console.print(output, end="")
        return console.file.getvalue()

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
