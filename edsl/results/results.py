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
import random
import warnings
from collections import defaultdict
from typing import Optional, Callable, Any, Union, List, TYPE_CHECKING
from bisect import bisect_left
from collections.abc import MutableSequence

from ..base import Base
from ..caching import Cache, CacheEntry

if TYPE_CHECKING:
    from ..surveys import Survey
    from ..agents import AgentList
    from ..scenarios import ScenarioList
    from ..results import Result
    from ..tasks import TaskHistory
    from ..language_models import ModelList
    from simpleeval import EvalWithCompoundTypes
    from ..dataset import Dataset

from ..utilities import remove_edsl_version, dict_hash
from ..dataset import ResultsOperationsMixin

from .result import Result
from ..db_list.sqlite_list import SQLiteList

from .exceptions import (
    ResultsError,
    ResultsBadMutationstringError,
    ResultsColumnNotFoundError,
    ResultsInvalidNameError,
    ResultsMutateError,
    ResultsFilterError,
    ResultsDeserializationError,
)


class ResultsSQLList(SQLiteList):
    def serialize(self, obj):
        return json.dumps(obj.to_dict()) if hasattr(obj, "to_dict") else json.dumps(obj)

    def deserialize(self, data):
        return (
            Result.from_dict(json.loads(data))
            if hasattr(Result, "from_dict")
            else json.loads(data)
        )


def ensure_fetched(method):
    """A decorator that checks if remote data is loaded, and if not, attempts to fetch it.

    Args:
        method: The method to decorate.

    Returns:
        The wrapped method that will ensure data is fetched before execution.
    """

    def wrapper(self, *args, **kwargs):
        if not self._fetched:
            # If not fetched, try fetching now.
            # (If you know you have job info stored in self.job_info)
            self.fetch_remote(self.job_info)
        return method(self, *args, **kwargs)

    return wrapper


def ensure_ready(method):
    """Decorator for Results methods to handle not-ready state.

    If the Results object is not ready, for most methods we return a NotReadyObject.
    However, for __repr__ (and other methods that need to return a string), we return
    the string representation of NotReadyObject.

    Args:
        method: The method to decorate.

    Returns:
        The wrapped method that will handle not-ready Results objects appropriately.

    Raises:
        Exception: Any exception from fetch_remote will be caught and printed.

    """
    from functools import wraps

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if self.completed:
            return method(self, *args, **kwargs)
        # Attempt to fetch remote data
        try:
            if hasattr(self, "job_info"):
                self.fetch_remote(self.job_info)
        except Exception as e:
            print(f"Error during fetch_remote in {method.__name__}: {e}")
        if not self.completed:
            not_ready = NotReadyObject(name=method.__name__, job_info=self.job_info)
            # For __repr__, ensure we return a string
            if method.__name__ == "__repr__" or method.__name__ == "__str__":
                return not_ready.__repr__()
            return not_ready
        return method(self, *args, **kwargs)

    return wrapper


class NotReadyObject:
    """A placeholder object that indicates results are not ready yet.

    This class returns itself for all attribute accesses and method calls,
    displaying a message about the job's running status when represented as a string.

    Attributes:
        name: The name of the method that was originally called.
        job_info: Information about the running job.

    """

    def __init__(self, name: str, job_info: "Any"):
        """Initialize a NotReadyObject.

        Args:
            name: The name of the method that was attempted to be called.
            job_info: Information about the running job.
        """
        self.name = name
        self.job_info = job_info
        # print(f"Not ready to call {name}")

    def __repr__(self):
        """Generate a string representation showing the job is still running.

        Returns:
            str: A message indicating the job is still running, along with job details.
        """
        message = """Results not ready - job still running on server."""
        for key, value in self.job_info.creation_data.items():
            message += f"\n{key}: {value}"
        return message

    def __getattr__(self, _):
        """Return self for any attribute access.

        Args:
            _: The attribute name (ignored).

        Returns:
            NotReadyObject: Returns self for chaining.
        """
        return self

    def __call__(self, *args, **kwargs):
        """Return self when called as a function.

        Args:
            *args: Positional arguments (ignored).
            **kwargs: Keyword arguments (ignored).

        Returns:
            NotReadyObject: Returns self for chaining.
        """
        return self


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
        - Database persistence via SQLAlchemy ORM

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
    ]

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

    def __init__(
        self,
        survey: Optional[Survey] = None,
        data: Optional[list[Result]] = None,
        created_columns: Optional[list[str]] = None,
        cache: Optional[Cache] = None,
        job_uuid: Optional[str] = None,
        total_results: Optional[int] = None,
        task_history: Optional[TaskHistory] = None,
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

        if hasattr(self, "_add_output_functions"):
            self._add_output_functions()

    def add_task_history_entry(self, interview: "Interview") -> None:
        self.task_history.add_interview(interview)

    def _fetch_list(self, data_type: str, key: str) -> list:
        """Return a list of values from the data for a given data type and key.

        Uses the filtered data, not the original data.

        Args:
            data_type: The type of data to fetch (e.g., 'answer', 'agent', 'scenario').
            key: The key to fetch from each data type dictionary.

        Returns:
            list: A list of values, one from each result in the data.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> values = r._fetch_list('answer', 'how_feeling')
            >>> len(values) == len(r)
            True
            >>> all(isinstance(v, (str, type(None))) for v in values)
            True
        """
        returned_list = []
        for row in self.data:
            returned_list.append(row.sub_dicts[data_type].get(key, None))

        return returned_list

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
        return self._fetch_list("answer", question_name)

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

    # def insert(self, item):
    #     """Insert a Result object into the Results list in the correct order.

    #     If the Result has an 'order' attribute, it uses that for ordering.
    #     Otherwise, it falls back to ordering by the 'iteration' attribute.

    #     >>> from edsl.results import Result
    #     >>> rnew = Result.example()
    #     >>> results = Results.example()
    #     >>> results.insert(rnew)
    #     >>> results[0] == rnew
    #     True
    #     >>> results = Results.example()
    #     >>> rnew.order = 100
    #     >>> results.insert(rnew)
    #     >>> results[-1] == rnew  # The new result is at the end
    #     True
    #     """

    #     def get_sort_key(result):
    #         if hasattr(result, "order"):
    #             return result.order
    #         return result.data["iteration"]

    #     # Find insertion point using bisect with custom key function
    #     index = bisect_left([get_sort_key(x) for x in self.data], get_sort_key(item))

    #     # Call the parent class's insert directly
    #     MutableSequence.insert(self, index, item)

    def extend_sorted(self, other):
        """Extend the Results list with items from another iterable.

        This method preserves ordering based on 'order' attribute if present,
        otherwise falls back to 'iteration' attribute.
        """
        # Collect all items (existing and new)
        all_items = list(self.data)
        all_items.extend(other)

        # Sort combined list by order attribute if available, otherwise by iteration
        def get_sort_key(item):
            if hasattr(item, "order"):
                return (0, item.order)  # Order attribute takes precedence
            return (1, item.data["iteration"])  # Iteration is secondary

        all_items.sort(key=get_sort_key)

        # Clear and refill with sorted items
        self.data.clear()
        self.data.extend(all_items)

    def compute_job_cost(self, include_cached_responses_in_cost: bool = False) -> float:
        """Compute the cost of a completed job in USD.

        This method calculates the total cost of all model responses in the results.
        By default, it only counts the cost of responses that were not cached.

        Args:
            include_cached_responses_in_cost: Whether to include the cost of cached
                responses in the total. Defaults to False.

        Returns:
            float: The total cost in USD.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> r.compute_job_cost()
            0
        """
        total_cost = 0
        for result in self:
            for key in result["raw_model_response"]:
                if key.endswith("_cost"):
                    result_cost = result["raw_model_response"][key]

                    # Extract the question name from the key
                    question_name = key.removesuffix("_cost")

                    # Get cache status safely - default to False if not found
                    cache_used = False
                    if (
                        "cache_used_dict" in result
                        and question_name in result["cache_used_dict"]
                    ):
                        cache_used = result["cache_used_dict"][question_name]

                    if isinstance(result_cost, (int, float)):
                        if include_cached_responses_in_cost:
                            total_cost += result_cost
                        elif not include_cached_responses_in_cost and not cache_used:
                            total_cost += result_cost

        return total_cost

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
        if isinstance(i, int):
            return self.data[i]
        if isinstance(i, slice):
            return self.__class__(survey=self.survey, data=self.data[i])
        if isinstance(i, str):
            return self.to_dict()[i]
        raise ResultsError("Invalid argument type for indexing Results object")

    @ensure_ready
    def __setitem__(self, i, item):
        self.data[i] = item

    @ensure_ready
    def __delitem__(self, i):
        del self.data[i]

    @ensure_ready
    def __len__(self):
        return len(self.data)

    @ensure_ready
    def insert(self, index, item):
        self.data.insert(index, item)

    @ensure_ready
    def extend(self, other):
        """Extend the Results list with items from another iterable."""
        self.data.extend(other)

    @ensure_ready
    def extend_sorted(self, other):
        """Extend the Results list with items from another iterable, maintaining sort order.

        This method preserves ordering based on 'order' attribute if present,
        otherwise falls back to 'iteration' attribute.
        """
        # Collect all items (existing and new)
        all_items = list(self.data)
        all_items.extend(other)

        # Sort combined list by order attribute if available, otherwise by iteration
        def get_sort_key(item):
            if hasattr(item, "order"):
                return (0, item.order)  # Order attribute takes precedence
            return (1, item.data["iteration"])  # Iteration is secondary

        all_items.sort(key=get_sort_key)

        # Clear and refill with sorted items
        self.data.clear()
        self.data.extend(all_items)

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
        if self.survey != other.survey:
            raise ResultsError(
                "The surveys are not the same so the the results cannot be added together."
            )
        if self.created_columns != other.created_columns:
            raise ResultsError(
                "The created columns are not the same so they cannot be added together."
            )

        # Create a new ResultsSQLList with the combined data
        # combined_data = ResultsSQLList()
        combined_data = self._data_class()
        combined_data.extend(self.data)
        combined_data.extend(other.data)

        return Results(
            survey=self.survey,
            data=combined_data,
            created_columns=self.created_columns,
        )

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
                    for k in self._data_type_to_keys[data_type]:
                        new_fields.append(k)
                else:
                    if key not in self._key_to_data_type:
                        raise ResultsColumnNotFoundError(
                            f"{key} is not a valid key. Must be in {self._key_to_data_type}"
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

    def to_dict(
        self,
        sort: bool = False,
        add_edsl_version: bool = False,
        include_cache: bool = True,
        include_task_history: bool = False,
        include_cache_info: bool = True,
    ) -> dict[str, Any]:
        from ..caching import Cache

        if sort:
            data = sorted([result for result in self.data], key=lambda x: hash(x))
        else:
            data = [result for result in self.data]

        d = {
            "data": [
                result.to_dict(
                    add_edsl_version=add_edsl_version,
                    include_cache_info=include_cache_info,
                )
                for result in data
            ],
            "survey": self.survey.to_dict(add_edsl_version=add_edsl_version),
            "created_columns": self.created_columns,
        }
        if include_cache:
            d.update(
                {
                    "cache": (
                        Cache()
                        if not hasattr(self, "cache")
                        else self.cache.to_dict(add_edsl_version=add_edsl_version)
                    )
                }
            )

        if self.task_history.has_unfixed_exceptions or include_task_history:
            d.update({"task_history": self.task_history.to_dict()})

        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Results"

        return d

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
        return self.task_history.has_unfixed_exceptions

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
        return set(hash(result) for result in self.data)

    def _sample_legacy(self, n: int) -> Results:
        """Return a random sample of the results.

        :param n: The number of samples to return.

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> len(r.sample(2))
        2
        """
        indices = None

        for entry in self:
            key, values = list(entry.items())[0]
            if indices is None:  # gets the indices for the first time
                indices = list(range(len(values)))
                sampled_indices = random.sample(indices, n)
                if n > len(indices):
                    raise ResultsError(
                        f"Cannot sample {n} items from a list of length {len(indices)}."
                    )
            entry[key] = [values[i] for i in sampled_indices]

        return self

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict[str, Any]) -> Results:
        """Convert a dictionary to a Results object.

        :param data: A dictionary representation of a Results object.

        Example:

        >>> r = Results.example()
        >>> d = r.to_dict()
        >>> r2 = Results.from_dict(d)
        >>> r == r2
        True
        """
        from ..surveys import Survey
        from ..caching import Cache
        from .result import Result
        from ..tasks import TaskHistory

        survey = Survey.from_dict(data["survey"])
        # Convert dictionaries to Result objects
        results_data = [Result.from_dict(r) for r in data["data"]]
        created_columns = data.get("created_columns", None)
        cache = Cache.from_dict(data.get("cache")) if "cache" in data else Cache()
        task_history = (
            TaskHistory.from_dict(data.get("task_history"))
            if "task_history" in data
            else TaskHistory(interviews=[])
        )

        # Create a Results object with original order preserved
        # using the empty data list initially
        params = {
            "survey": survey,
            "data": [],  # Start with empty data
            "created_columns": created_columns,
            "cache": cache,
            "task_history": task_history,
        }

        try:
            results = cls(**params)
            # Add each result individually to respect order attributes
            for result in results_data:
                results.append(result)
        except Exception as e:
            raise ResultsDeserializationError(f"Error in Results.from_dict: {e}")
        return results

    @property
    def _key_to_data_type(self) -> dict[str, str]:
        """
        Return a mapping of keys (how_feeling, status, etc.) to strings representing data types.

        Objects such as Agent, Answer, Model, Scenario, etc.
        - Uses the key_to_data_type property of the Result class.
        - Includes any columns that the user has created with `mutate`
        """
        d: dict = {}
        for result in self.data:
            d.update(result.key_to_data_type)
        for column in self.created_columns:
            d[column] = "answer"

        return d

    @property
    def _data_type_to_keys(self) -> dict[str, str]:
        """
        Return a mapping of strings representing data types (objects such as Agent, Answer, Model, Scenario, etc.) to keys (how_feeling, status, etc.)
        - Uses the key_to_data_type property of the Result class.
        - Includes any columns that the user has created with `mutate`

        Example:

        >>> r = Results.example()
        >>> r._data_type_to_keys
        defaultdict(...
        """
        d: dict = defaultdict(set)
        for result in self.data:
            for key, value in result.key_to_data_type.items():
                d[value] = d[value].union(set({key}))
        for column in self.created_columns:
            d["answer"] = d["answer"].union(set({column}))
        return d

    @property
    def columns(self) -> list[str]:
        """Return a list of all of the columns that are in the Results.

        Example:

        >>> r = Results.example()
        >>> r.columns
        ['agent.agent_index', ...]
        """
        column_names = [f"{v}.{k}" for k, v in self._key_to_data_type.items()]
        from ..utilities.PrettyList import PrettyList

        return PrettyList(sorted(column_names))

    @property
    def answer_keys(self) -> dict[str, str]:
        """Return a mapping of answer keys to question text.

        Example:

        >>> r = Results.example()
        >>> r.answer_keys
        {'how_feeling': 'How are you this {{ period }}?', 'how_feeling_yesterday': 'How were you feeling yesterday {{ period }}?'}
        """
        from ..utilities.utilities import shorten_string

        if not self.survey:
            raise ResultsError("Survey is not defined so no answer keys are available.")

        answer_keys = self._data_type_to_keys["answer"]
        answer_keys = {k for k in answer_keys if "_comment" not in k}
        questions_text = [
            self.survey._get_question_by_name(k).question_text for k in answer_keys
        ]
        short_question_text = [shorten_string(q, 80) for q in questions_text]
        initial_dict = dict(zip(answer_keys, short_question_text))
        sorted_dict = {key: initial_dict[key] for key in sorted(initial_dict)}
        return sorted_dict

    @property
    def agents(self) -> AgentList:
        """Return a list of all of the agents in the Results.

        Example:

        >>> r = Results.example()
        >>> r.agents
        AgentList([Agent(traits = {'status': 'Joyful'}), Agent(traits = {'status': 'Joyful'}), Agent(traits = {'status': 'Sad'}), Agent(traits = {'status': 'Sad'})])
        """
        from ..agents import AgentList

        return AgentList([r.agent for r in self.data])

    @property
    def models(self) -> ModelList:
        """Return a list of all of the models in the Results.

        Example:

        >>> r = Results.example()
        >>> r.models[0]
        Model(model_name = ...)
        """
        from ..language_models import ModelList

        return ModelList([r.model for r in self.data])

    def __eq__(self, other):
        return hash(self) == hash(other)

    @property
    def scenarios(self) -> ScenarioList:
        """Return a list of all of the scenarios in the Results.

        Example:

        >>> r = Results.example()
        >>> r.scenarios
        ScenarioList([Scenario({'period': 'morning', 'scenario_index': 0}), Scenario({'period': 'afternoon', 'scenario_index': 1}), Scenario({'period': 'morning', 'scenario_index': 0}), Scenario({'period': 'afternoon', 'scenario_index': 1})])
        """
        from ..scenarios import ScenarioList

        return ScenarioList([r.scenario for r in self.data])

    @property
    def agent_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the Agent data.

        Example:

        >>> r = Results.example()
        >>> r.agent_keys
        ['agent_index', 'agent_instruction', 'agent_name', 'status']
        """
        return sorted(self._data_type_to_keys["agent"])

    @property
    def model_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the LanguageModel data.

        >>> r = Results.example()
        >>> r.model_keys
        ['frequency_penalty', 'inference_service', 'logprobs', 'max_tokens', 'model', 'model_index', 'presence_penalty', 'temperature', 'top_logprobs', 'top_p']
        """
        return sorted(self._data_type_to_keys["model"])

    @property
    def scenario_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the Scenario data.

        >>> r = Results.example()
        >>> r.scenario_keys
        ['period', 'scenario_index']
        """
        return sorted(self._data_type_to_keys["scenario"])

    @property
    def question_names(self) -> list[str]:
        """Return a list of all of the question names.

        Example:

        >>> r = Results.example()
        >>> r.question_names
        ['how_feeling', 'how_feeling_yesterday']
        """
        if self.survey is None:
            return []
        return sorted(list(self.survey.question_names))

    @property
    def all_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the Results.

        Example:

        >>> r = Results.example()
        >>> r.all_keys
        ['agent_index', ...]
        """
        answer_keys = set(self.answer_keys)
        all_keys = (
            answer_keys.union(self.agent_keys)
            .union(self.scenario_keys)
            .union(self.model_keys)
        )
        return sorted(list(all_keys))

    def first(self) -> Result:
        """Return the first observation in the results.

        Example:

        >>> r = Results.example()
        >>> r.first()
        Result(agent...
        """
        return self.data[0]

    def answer_truncate(
        self, column: str, top_n: int = 5, new_var_name: Optional[str] = None
    ) -> Results:
        """Create a new variable that truncates the answers to the top_n.

        :param column: The column to truncate.
        :param top_n: The number of top answers to keep.
        :param new_var_name: The name of the new variable. If None, it is the original name + '_truncated'.

        Example:
        >>> r = Results.example()
        >>> r.answer_truncate('how_feeling', top_n = 2).select('how_feeling', 'how_feeling_truncated')
        Dataset([{'answer.how_feeling': ['OK', 'Great', 'Terrible', 'OK']}, {'answer.how_feeling_truncated': ['Other', 'Other', 'Other', 'Other']}])


        """
        if new_var_name is None:
            new_var_name = column + "_truncated"
        answers = list(self.select(column).tally().keys())

        def f(x):
            if x in answers[:top_n]:
                return x
            else:
                return "Other"

        return self.recode(column, recode_function=f, new_var_name=new_var_name)

    @ensure_ready
    def recode(
        self, column: str, recode_function: Optional[Callable], new_var_name=None
    ) -> Results:
        """
        Recode a column in the Results object.

        >>> r = Results.example()
        >>> r.recode('how_feeling', recode_function = lambda x: 1 if x == 'Great' else 0).select('how_feeling', 'how_feeling_recoded')
        Dataset([{'answer.how_feeling': ['OK', 'Great', 'Terrible', 'OK']}, {'answer.how_feeling_recoded': [0, 1, 0, 0]}])
        """

        if new_var_name is None:
            new_var_name = column + "_recoded"
        new_data = []
        for result in self.data:
            new_result = result.copy()
            value = new_result.get_value("answer", column)
            # breakpoint()
            new_result["answer"][new_var_name] = recode_function(value)
            new_data.append(new_result)

        # print("Created new variable", new_var_name)
        return Results(
            survey=self.survey,
            data=new_data,
            created_columns=self.created_columns + [new_var_name],
        )

    @ensure_ready
    def add_column(self, column_name: str, values: list) -> Results:
        """Adds columns to Results

        >>> r = Results.example()
        >>> r.add_column('a', [1,2,3, 4]).select('a')
        Dataset([{'answer.a': [1, 2, 3, 4]}])
        """
        assert len(values) == len(
            self.data
        ), "The number of values must match the number of results."

        # Create new Results object with same properties but empty data
        new_results = Results(
            survey=self.survey,
            data=[],
            created_columns=self.created_columns + [column_name],
            data_class=self._data_class,
        )

        # Process one result at a time
        for i, result in enumerate(self.data):
            new_result = result.copy()
            new_result["answer"][column_name] = values[i]
            new_results.append(new_result)

        return new_results

    @ensure_ready
    def add_columns_from_dict(self, columns: List[dict]) -> Results:
        """Adds columns to Results from a list of dictionaries.

        >>> r = Results.example()
        >>> r.add_columns_from_dict([{'a': 1, 'b': 2}, {'a': 3, 'b': 4}, {'a':3, 'b':2}, {'a':3, 'b':2}]).select('a', 'b')
        Dataset([{'answer.a': [1, 3, 3, 3]}, {'answer.b': [2, 4, 2, 2]}])
        """
        keys = list(columns[0].keys())
        for key in keys:
            values = [d[key] for d in columns]
            self = self.add_column(key, values)
        return self

    @staticmethod
    def _create_evaluator(
        result: Result, functions_dict: Optional[dict] = None
    ) -> "EvalWithCompoundTypes":
        """Create an evaluator for the expression.

        >>> from unittest.mock import Mock
        >>> result = Mock()
        >>> result.combined_dict = {'how_feeling': 'OK'}

        >>> evaluator = Results._create_evaluator(result = result, functions_dict = {})
        >>> evaluator.eval("how_feeling == 'OK'")
        True

        >>> result.combined_dict = {'answer': {'how_feeling': 'OK'}}
        >>> evaluator = Results._create_evaluator(result = result, functions_dict = {})
        >>> evaluator.eval("answer.how_feeling== 'OK'")
        True

        Note that you need to refer to the answer dictionary in the expression.

        >>> evaluator.eval("how_feeling== 'OK'")
        Traceback (most recent call last):
        ...
        simpleeval.NameNotDefined: 'how_feeling' is not defined for expression 'how_feeling== 'OK''
        """
        from simpleeval import EvalWithCompoundTypes

        if functions_dict is None:
            functions_dict = {}
        evaluator = EvalWithCompoundTypes(
            names=result.combined_dict, functions=functions_dict
        )
        evaluator.functions.update(int=int, float=float)
        return evaluator

    @ensure_ready
    def mutate(
        self, new_var_string: str, functions_dict: Optional[dict] = None
    ) -> Results:
        """Create a new column based on a computational expression.

        The mutate method allows you to create new derived variables based on existing data.
        You provide an assignment expression where the left side is the new column name
        and the right side is a Python expression that computes the value. The expression
        can reference any existing columns in the Results object.

        Args:
            new_var_string: A string containing an assignment expression in the form
                "new_column_name = expression". The expression can reference
                any existing column and use standard Python syntax.
            functions_dict: Optional dictionary of custom functions that can be used in
                the expression. Keys are function names, values are function objects.

        Returns:
            A new Results object with the additional column.

        Notes:
            - The expression must contain an equals sign (=) separating the new column name
              from the computation expression
            - The new column name must be a valid Python variable name
            - The expression is evaluated for each Result object individually
            - The expression can access any data in the Result object using the column names
            - New columns are added to the "answer" data type
            - Created columns are tracked in the `created_columns` property

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
        # extract the variable name and the expression
        if "=" not in new_var_string:
            raise ResultsBadMutationstringError(
                f"Mutate requires an '=' in the string, but '{new_var_string}' doesn't have one."
            )
        raw_var_name, expression = new_var_string.split("=", 1)
        var_name = raw_var_name.strip()
        from ..utilities.utilities import is_valid_variable_name

        if not is_valid_variable_name(var_name):
            raise ResultsInvalidNameError(f"{var_name} is not a valid variable name.")

        # create the evaluator
        functions_dict = functions_dict or {}

        def new_result(old_result: "Result", var_name: str) -> "Result":
            evaluator = self._create_evaluator(old_result, functions_dict)
            value = evaluator.eval(expression)
            new_result = old_result.copy()
            new_result["answer"][var_name] = value
            return new_result

        try:
            new_data = [new_result(result, var_name) for result in self.data]
        except Exception as e:
            raise ResultsMutateError(f"Error in mutate. Exception:{e}")

        return Results(
            survey=self.survey,
            data=new_data,
            created_columns=self.created_columns + [var_name],
        )

    # Method removed due to duplication (F811)

    @ensure_ready
    def rename(self, old_name: str, new_name: str) -> Results:
        """Rename an answer column in a Results object.

        >>> s = Results.example()
        >>> s.rename('how_feeling', 'how_feeling_new').select('how_feeling_new')
        Dataset([{'answer.how_feeling_new': ['OK', 'Great', 'Terrible', 'OK']}])
        """
        # Create new Results object with same properties but empty data
        new_results = Results(
            survey=self.survey,
            data=[],
            created_columns=self.created_columns,
            data_class=self._data_class,
        )

        # Update created_columns if old_name was in there
        if old_name in new_results.created_columns:
            new_results.created_columns.remove(old_name)
            new_results.created_columns.append(new_name)

        # Process one result at a time
        for obs in self.data:
            new_result = obs.copy()
            new_result["answer"][new_name] = new_result["answer"][old_name]
            del new_result["answer"][old_name]
            new_results.append(new_result)

        return new_results

    @ensure_ready
    def shuffle(self, seed: Optional[str] = "edsl") -> Results:
        """Return a shuffled copy of the results using Fisher-Yates algorithm.

        Args:
            seed: Random seed for reproducibility.

        Returns:
            Results: A new Results object with shuffled data.
        """
        if seed != "edsl":
            random.seed(seed)

        # Create new Results object with same properties but empty data
        shuffled_results = Results(
            survey=self.survey,
            data=[],
            created_columns=self.created_columns,
            data_class=self._data_class,
        )

        # First pass: copy data while tracking indices
        indices = list(range(len(self.data)))

        # Second pass: Fisher-Yates shuffle on indices
        for i in range(len(indices) - 1, 0, -1):
            j = random.randrange(i + 1)
            indices[i], indices[j] = indices[j], indices[i]

        # Final pass: append items in shuffled order
        for idx in indices:
            shuffled_results.append(self.data[idx])

        return shuffled_results

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
        if seed:
            random.seed(seed)

        if n is None and frac is None:
            raise ResultsError("You must specify either n or frac.")

        if n is not None and frac is not None:
            raise ResultsError("You cannot specify both n and frac.")

        if frac is not None:
            n = int(frac * len(self.data))

        # Create new Results object with same properties but empty data
        sampled_results = Results(
            survey=self.survey,
            data=[],
            created_columns=self.created_columns,
            data_class=self._data_class,
        )

        if with_replacement:
            # For sampling with replacement, we can generate indices and sample one at a time
            indices = (random.randrange(len(self.data)) for _ in range(n))
            for i in indices:
                sampled_results.append(self.data[i])
        else:
            # For sampling without replacement, use reservoir sampling
            if n > len(self.data):
                raise ResultsError(
                    f"Cannot sample {n} items from a list of length {len(self.data)}."
                )

            # Reservoir sampling algorithm
            for i, item in enumerate(self.data):
                if i < n:
                    # Fill the reservoir initially
                    sampled_results.append(item)
                else:
                    # Randomly replace items with decreasing probability
                    j = random.randrange(i + 1)
                    if j < n:
                        sampled_results.data[j] = item

        return sampled_results

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

        selector = Selector(
            known_data_types=self.known_data_types,
            data_type_to_keys=self._data_type_to_keys,
            key_to_data_type=self._key_to_data_type,
            fetch_list_func=self._fetch_list,
            columns=self.columns,
        )
        return selector.select(*columns)

    @ensure_ready
    def sort_by(self, *columns: str, reverse: bool = False) -> Results:
        """Sort the results by one or more columns."""
        warnings.warn(
            "sort_by is deprecated. Use order_by instead.", DeprecationWarning
        )
        return self.order_by(*columns, reverse=reverse)

    def _parse_column(self, column: str) -> tuple[str, str]:
        """Parse a column name into a data type and key."""
        if "." in column:
            return column.split(".")
        return self._key_to_data_type[column], column

    @ensure_ready
    def order_by(self, *columns: str, reverse: bool = False) -> Results:
        """Sort the results by one or more columns.

        Args:
            columns: One or more column names as strings.
            reverse: A boolean that determines whether to sort in reverse order.

        Returns:
            Results: A new Results object with sorted data.
        """

        def to_numeric_if_possible(v):
            try:
                return float(v)
            except (ValueError, TypeError):
                return v

        def sort_key(item):
            key_components = []
            for col in columns:
                data_type, key = self._parse_column(col)
                value = item.get_value(data_type, key)
                if isinstance(value, (str, bytes)):
                    key_components.append(str(value))
                else:
                    key_components.append(to_numeric_if_possible(value))
            return tuple(key_components)

        # Create a new sorted view of the data without materializing it
        sorted_data = sorted(self.data, key=sort_key, reverse=reverse)

        # Create new Results object that uses the sorted iterator
        return Results(
            survey=self.survey,
            data=sorted_data,  # This will be an iterator, not a materialized list
            created_columns=self.created_columns,
            data_class=self._data_class,
            sort_by_iteration=False,
        )

    @staticmethod
    def has_single_equals(expression: str) -> bool:
        """Check if an expression contains a single equals sign not part of ==, >=, or <=.

        Args:
            expression: String expression to check

        Returns:
            bool: True if there is a standalone = sign

        Examples:
            >>> Results.has_single_equals("x = 1")
            True
            >>> Results.has_single_equals("x == 1")
            False
            >>> Results.has_single_equals("x >= 1")
            False
            >>> Results.has_single_equals("x <= 1")
            False
        """
        # First remove valid operators that contain =
        cleaned = (
            expression.replace("==", "")
            .replace(">=", "")
            .replace("<=", "")
            .replace("!=", "")
        )
        return "=" in cleaned

    @ensure_ready
    def filter(self, expression: str) -> Results:
        """Filter results based on a boolean expression.

        This method evaluates a boolean expression against each Result object in the
        collection and returns a new Results object containing only those that match.
        The expression can reference any column in the data and supports standard
        Python operators and syntax.

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

        Notes:
            - Column names can be specified with or without their data type prefix
              (e.g., both "how_feeling" and "answer.how_feeling" work if unambiguous)
            - You must use double equals (==) for equality comparison, not single equals (=)
            - You can use logical operators like 'and', 'or', 'not'
            - You can use comparison operators like '==', '!=', '>', '<', '>=', '<='
            - You can use membership tests with 'in'
            - You can use string methods like '.startswith()', '.contains()', etc.
            - The expression can be a multi-line string for improved readability
            - You can use template-style syntax with double curly braces: {{ field }}

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

            >>> # Using multi-line string for complex conditions
            >>> r.filter('''
            ...     how_feeling == 'Great'
            ...     or how_feeling == 'Terrible'
            ... ''').select('how_feeling')
            Dataset([{'answer.how_feeling': ['Great', 'Terrible']}])

            >>> # Using template-style syntax with {{}}
            >>> r.filter("{{ answer.how_feeling }} == 'Great'").select('how_feeling')
            Dataset([{'answer.how_feeling': ['Great']}])

            >>> # Common error: using = instead of ==
            >>> try:
            ...     r.filter("how_feeling = 'Great'")
            ... except Exception as e:
            ...     print("ResultsFilterError: You must use '==' instead of '=' in the filter expression.")
            ResultsFilterError: You must use '==' instead of '=' in the filter expression.
        """
        # Normalize expression by removing extra whitespace and newlines
        normalized_expression = " ".join(expression.strip().split())

        # Remove template-style syntax (double curly braces)
        normalized_expression = normalized_expression.replace("{{", "").replace(
            "}}", ""
        )

        if self.has_single_equals(normalized_expression):
            raise ResultsFilterError(
                "You must use '==' instead of '=' in the filter expression."
            )

        try:
            # Create new Results object with same class as original but empty data
            filtered_results = Results(
                survey=self.survey,
                data=[],  # Empty data list
                created_columns=self.created_columns,
                data_class=self._data_class,  # Preserve the original data class
            )

            # Process one result at a time
            for result in self.data:
                evaluator = self._create_evaluator(result)
                result.check_expression(normalized_expression)  # check expression
                if evaluator.eval(normalized_expression):
                    filtered_results.append(
                        result
                    )  # Use append method to add matching results

            if len(filtered_results) == 0:
                import warnings

                warnings.warn("No results remain after applying the filter.")

            return filtered_results

        except ValueError as e:
            raise ResultsFilterError(
                f"Error in filter. Exception:{e}",
                f"The expression you provided was: {expression}",
                "See https://docs.expectedparrot.com/en/latest/results.html#filtering-results for more details.",
            )
        except Exception as e:
            raise ResultsFilterError(
                f"Error in filter. Exception:{e}.",
                f"The expression you provided was: {expression}.",
                "Please make sure that the expression is a valid Python expression that evaluates to a boolean.",
                'For example, \'how_feeling == "Great"\' is a valid expression, as is \'how_feeling in ["Great", "Terrible"]\'.',
                "However, 'how_feeling = \"Great\"' is not a valid expression.",
                "See https://docs.expectedparrot.com/en/latest/results.html#filtering-results for more details.",
            )

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
        job = Jobs.example(randomize=randomize)
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
        """Score the results using in a function.

        :param f: A function that takes values from a Resul object and returns a score.

        >>> r = Results.example()
        >>> def f(status): return 1 if status == 'Joyful' else 0
        >>> r.score(f)
        [1, 1, 0, 0]
        """
        return [r.score(f) for r in self.data]

    def score_with_answer_key(self, answer_key: dict) -> list:
        """Score the results using an answer key.

        :param answer_key: A dictionary that maps answer values to scores.
        """
        return [r.score_with_answer_key(answer_key) for r in self.data]

    def fetch_remote(self, job_info: Any) -> None:
        """Fetch remote Results object and update this instance with the data.

        This is useful when you have a Results object that was created locally but want to sync it with
        the latest data from the remote server.

        Args:
            job_info: RemoteJobInfo object containing the job_uuid and other remote job details

        Returns:
            bool: True if the fetch was successful, False if the job is not yet completed.

        Raises:
            ResultsError: If there's an error during the fetch process.

        Examples:
            >>> # This is a simplified example since we can't actually test this without a remote server
            >>> from unittest.mock import Mock, patch
            >>> # Create a mock job_info and Results
            >>> job_info = Mock()
            >>> job_info.job_uuid = "test_uuid"
            >>> results = Results()
            >>> # In a real scenario:
            >>> # results.fetch_remote(job_info)
            >>> # results.completed  # Would be True if successful
        """
        try:
            from ..coop import Coop
            from ..jobs import JobsRemoteInferenceHandler

            # Get the remote job data
            remote_job_data = JobsRemoteInferenceHandler.check_status(job_info.job_uuid)

            if remote_job_data.get("status") not in ["completed", "failed"]:
                return False
                #
            results_uuid = remote_job_data.get("results_uuid")
            if not results_uuid:
                raise ResultsError("No results_uuid found in remote job data")

            # Fetch the remote Results object
            coop = Coop()
            remote_results = coop.get(results_uuid, expected_object_type="results")

            # Update this instance with remote data
            self.data = remote_results.data
            self.survey = remote_results.survey
            self.created_columns = remote_results.created_columns
            self.cache = remote_results.cache
            self.task_history = remote_results.task_history
            self.completed = True

            # Set job_uuid and results_uuid from remote data
            self.job_uuid = job_info.job_uuid
            if hasattr(remote_results, "results_uuid"):
                self.results_uuid = remote_results.results_uuid

            return True

        except Exception as e:
            raise ResultsError(f"Failed to fetch remote results: {str(e)}")

    def fetch(self, polling_interval: Union[float, int] = 1.0) -> Results:
        """Poll the server for job completion and update this Results instance.

        This method continuously polls the remote server until the job is completed or
        fails, then updates this Results object with the final data.

        Args:
            polling_interval: Number of seconds to wait between polling attempts (default: 1.0)

        Returns:
            self: The updated Results instance

        Raises:
            ResultsError: If no job info is available or if there's an error during fetch.

        Examples:
            >>> # This is a simplified example since we can't actually test polling
            >>> from unittest.mock import Mock, patch
            >>> # Create a mock results object
            >>> results = Results()
            >>> # In a real scenario with a running job:
            >>> # results.job_info = remote_job_info
            >>> # results.fetch()  # Would poll until complete
            >>> # results.completed  # Would be True if successful
        """
        if not hasattr(self, "job_info"):
            raise ResultsError(
                "No job info available - this Results object wasn't created from a remote job"
            )

        from ..jobs import JobsRemoteInferenceHandler

        try:
            # Get the remote job data
            remote_job_data = JobsRemoteInferenceHandler.check_status(
                self.job_info.job_uuid
            )

            while remote_job_data.get("status") not in ["completed", "failed"]:
                print("Waiting for remote job to complete...")
                import time

                time.sleep(polling_interval)
                remote_job_data = JobsRemoteInferenceHandler.check_status(
                    self.job_info.job_uuid
                )

            # Once complete, fetch the full results
            self.fetch_remote(self.job_info)
            return self

        except Exception as e:
            raise ResultsError(f"Failed to fetch remote results: {str(e)}")

    def spot_issues(self, models: Optional[ModelList] = None) -> Results:
        """Run a survey to spot issues and suggest improvements for prompts that had no model response, returning a new Results object.
        Future version: Allow user to optionally pass a list of questions to review, regardless of whether they had a null model response.
        """
        from ..questions import QuestionFreeText, QuestionDict
        from ..surveys import Survey
        from ..scenarios import Scenario, ScenarioList
        from ..language_models import ModelList
        import pandas as pd

        df = self.select(
            "agent.*", "scenario.*", "answer.*", "raw_model_response.*", "prompt.*"
        ).to_pandas()
        scenario_list = []

        for _, row in df.iterrows():
            for col in df.columns:
                if col.endswith("_raw_model_response") and pd.isna(row[col]):
                    q = col.split("_raw_model_response")[0].replace(
                        "raw_model_response.", ""
                    )

                    s = Scenario(
                        {
                            "original_question": q,
                            "original_agent_index": row["agent.agent_index"],
                            "original_scenario_index": row["scenario.scenario_index"],
                            "original_prompts": f"User prompt: {row[f'prompt.{q}_user_prompt']}\nSystem prompt: {row[f'prompt.{q}_system_prompt']}",
                        }
                    )

                    scenario_list.append(s)

        sl = ScenarioList(set(scenario_list))

        q1 = QuestionFreeText(
            question_name="issues",
            question_text="""
            The following prompts generated a bad or null response: '{{ original_prompts }}'
            What do you think was the likely issue(s)?
            """,
        )

        q2 = QuestionDict(
            question_name="revised",
            question_text="""
            The following prompts generated a bad or null response: '{{ original_prompts }}'
            You identified the issue(s) as '{{ issues.answer }}'.
            Please revise the prompts to address the issue(s).
            """,
            answer_keys=["revised_user_prompt", "revised_system_prompt"],
        )

        survey = Survey(questions=[q1, q2])

        if models is not None:
            if not isinstance(models, ModelList):
                raise ResultsError("models must be a ModelList")
            results = survey.by(sl).by(models).run()
        else:
            results = survey.by(sl).run()  # use the default model

        return results

    def shelve_result(self, result: "Result") -> str:
        """Store a Result object in persistent storage using its hash as the key.

        Args:
            result: A Result object to store

        Returns:
            str: The hash key for retrieving the result later

        Raises:
            ResultsError: If there's an error storing the Result
        """
        import shelve

        key = str(hash(result))
        try:
            with shelve.open(self._shelve_path) as shelf:
                shelf[key] = result.to_dict()
                self._shelf_keys.add(key)
            return key
        except Exception as e:
            raise ResultsError(f"Error storing Result in shelve database: {str(e)}")

    def get_shelved_result(self, key: str) -> "Result":
        """Retrieve a Result object from persistent storage.

        Args:
            key: The hash key of the Result to retrieve

        Returns:
            Result: The stored Result object

        Raises:
            ResultsError: If the key doesn't exist or if there's an error retrieving the Result
        """
        import shelve
        from .result import Result

        if key not in self._shelf_keys:
            raise ResultsError(f"No result found with key: {key}")

        try:
            with shelve.open(self._shelve_path) as shelf:
                return Result.from_dict(shelf[key])
        except Exception as e:
            raise ResultsError(
                f"Error retrieving Result from shelve database: {str(e)}"
            )

    @property
    def shelf_keys(self) -> set:
        """Return a copy of the set of shelved result keys."""
        return self._shelf_keys.copy()

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
        from bisect import bisect_left

        def get_sort_key(result):
            if hasattr(result, "order"):
                return (0, result.order)  # Order attribute takes precedence
            return (1, result.data["iteration"])  # Iteration is secondary

        # Get the sort key for the new item
        item_key = get_sort_key(item)

        # Get list of sort keys for existing items
        keys = [get_sort_key(x) for x in self.data]

        # Find insertion point
        index = bisect_left(keys, item_key)

        # Insert at the found position
        self.data.insert(index, item)

    def insert_from_shelf(self) -> None:
        """Move all shelved results into memory using insert_sorted method.
        Clears the shelf after successful insertion.

        This method preserves the original order of results by using their 'order'
        attribute if available, which ensures consistent ordering even after
        serialization/deserialization.

        Raises:
            ResultsError: If there's an error accessing or clearing the shelf
        """
        import shelve
        from .result import Result

        if not self._shelf_keys:
            return

        try:
            # First collect all results from shelf
            with shelve.open(self._shelve_path) as shelf:
                # Get and insert all results first
                for key in self._shelf_keys:
                    result_dict = shelf[key]
                    result = Result.from_dict(result_dict)
                    self.insert_sorted(result)

                # Now clear the shelf
                for key in self._shelf_keys:
                    del shelf[key]

            # Clear the tracking set
            self._shelf_keys.clear()

        except Exception as e:
            raise ResultsError(f"Error moving results from shelf to memory: {str(e)}")

    def to_disk(self, filepath: str) -> None:
        """Serialize the Results object to a zip file, preserving the SQLite database.

        This method creates a zip file containing:
        1. The SQLite database file from the data container
        2. A metadata.json file with the survey, created_columns, and other non-data info
        3. The cache data if present

        Args:
            filepath: Path where the zip file should be saved

        Raises:
            ResultsError: If there's an error during serialization
        """
        import zipfile
        import json
        import os
        import tempfile
        from pathlib import Path
        import sqlite3
        import shutil

        data_class = ResultsSQLList

        try:
            # Create a temporary directory to store files before zipping
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # 1. Handle the SQLite database
                db_path = temp_path / "results.db"

                if isinstance(self.data, list):
                    # If data is a list, create a new SQLiteList
                    # from .sqlite_list import SQLiteList
                    new_db = data_class()
                    new_db.extend(self.data)
                    shutil.copy2(new_db.db_path, db_path)
                elif hasattr(self.data, "db_path") and os.path.exists(
                    self.data.db_path
                ):
                    # If data is already a SQLiteList, copy its database
                    shutil.copy2(self.data.db_path, db_path)
                else:
                    # If no database exists, create a new one
                    # from .sqlite_list import SQLiteList
                    # new_db = SQLiteList()
                    new_db = data_class()
                    new_db.extend(self.data)
                    shutil.copy2(new_db.db_path, db_path)

                # 2. Create metadata.json
                metadata = {
                    "survey": self.survey.to_dict() if self.survey else None,
                    "created_columns": self.created_columns,
                    "cache": self.cache.to_dict() if hasattr(self, "cache") else None,
                    "task_history": self.task_history.to_dict()
                    if hasattr(self, "task_history")
                    else None,
                    "completed": self.completed,
                    "job_uuid": self._job_uuid if hasattr(self, "_job_uuid") else None,
                    "total_results": self._total_results
                    if hasattr(self, "_total_results")
                    else None,
                }

                metadata_path = temp_path / "metadata.json"
                metadata_path.write_text(json.dumps(metadata, indent=4))

                # 3. Create the zip file
                with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zipf:
                    # Add all files from temp directory to zip
                    for file in temp_path.glob("*"):
                        zipf.write(file, file.name)

        except Exception as e:
            raise ResultsError(f"Error saving Results to disk: {str(e)}")

    @classmethod
    def from_disk(cls, filepath: str) -> "Results":
        """Load a Results object from a zip file.

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
        import zipfile
        import json
        import tempfile
        from pathlib import Path
        from ..surveys import Survey
        from ..caching import Cache
        from ..tasks import TaskHistory

        data_class = ResultsSQLList

        try:
            # Create a temporary directory to extract files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract the zip file
                with zipfile.ZipFile(filepath, "r") as zipf:
                    zipf.extractall(temp_path)

                # 1. Load metadata
                metadata_path = temp_path / "metadata.json"
                metadata = json.loads(metadata_path.read_text())

                # 2. Create a new Results instance
                results = cls(
                    survey=Survey.from_dict(metadata["survey"])
                    if metadata["survey"]
                    else None,
                    created_columns=metadata["created_columns"],
                    cache=Cache.from_dict(metadata["cache"])
                    if metadata["cache"]
                    else None,
                    task_history=TaskHistory.from_dict(metadata["task_history"])
                    if metadata["task_history"]
                    else None,
                    job_uuid=metadata["job_uuid"],
                    total_results=metadata["total_results"],
                )

                # 3. Set the SQLite database path if it exists
                db_path = temp_path / "results.db"
                if db_path.exists():
                    # Create a new ResultsSQLList instance
                    new_db = data_class()
                    # Copy data from the source database - convert Path to string
                    new_db.copy_from(str(db_path))
                    # Set the new database as the results data
                    results.data = new_db

                results.completed = metadata["completed"]
                return results

        except Exception as e:
            raise ResultsError(f"Error loading Results from disk: {str(e)}")
    


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

    # Run doctests
    doctest.testmod(optionflags=doctest.ELLIPSIS)

    # Create an example Results object
    results = Results.example()
    print("Example Results object created.")

    # Run the main function to demonstrate functionalities
    main()


    
