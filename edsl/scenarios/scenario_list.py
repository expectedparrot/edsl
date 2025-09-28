"""
ScenarioList provides a collection of Scenario objects with advanced operations.

The ScenarioList module extends the functionality of a simple list of Scenario objects,
providing powerful operations for data manipulation, filtering, transformation, and analysis.
It serves as a bridge between individual Scenarios and higher-level EDSL components like
Surveys and Jobs.

Key features include:
- Collection operations (filtering, sorting, sampling, and iteration)
- Data manipulation (transformation, joining, grouping, pivoting)
- Format conversion (to/from pandas, CSV, Excel, etc.)
- Advanced selection and retrieval mechanisms
- Integration with other EDSL components

ScenarioList is a core component in the EDSL framework for creating, managing, and
manipulating collections of Scenarios for experiments, surveys, and data processing tasks.
"""

from __future__ import annotations
from typing import (
    Any,
    Optional,
    Union,
    List,
    Callable,
    Literal,
    TYPE_CHECKING,
)
import warnings
import csv
import random
import os
import inspect
from collections import defaultdict
from collections.abc import Iterable, MutableSequence
import json
import pickle


# Import for refactoring to Source classes

from simpleeval import EvalWithCompoundTypes, NameNotDefined  # type: ignore
from tabulate import tabulate_formats

try:
    from typing import TypeAlias
except ImportError:
    from typing_extensions import TypeAlias

from ..config import CONFIG

if TYPE_CHECKING:
    from ..dataset import Dataset
    from ..jobs import Jobs, Job
    from ..surveys import Survey
    from ..questions import QuestionBase, Question


from ..base import Base
from ..utilities import (
    remove_edsl_version,
    sanitize_string,
    is_valid_variable_name,
    dict_hash,
    memory_profile,
)
from ..dataset import ScenarioListOperationsMixin

from ..db_list.sqlite_list import SQLiteList

from .exceptions import ScenarioError
from .scenario import Scenario
from .firecrawl_scenario import FirecrawlRequest


if TYPE_CHECKING:
    from ..dataset import Dataset

TableFormat: TypeAlias = Literal[
    "plain",
    "simple",
    "github",
    "grid",
    "fancy_grid",
    "pipe",
    "orgtbl",
    "rst",
    "mediawiki",
    "html",
    "latex",
    "latex_raw",
    "latex_booktabs",
    "tsv",
]


class ScenarioSQLiteList(SQLiteList):
    """SQLite-backed list specifically for storing Scenario objects."""

    def serialize(self, obj):
        """Serialize a Scenario object or other data to bytes using pickle."""
        return pickle.dumps(obj)

    def deserialize(self, data):
        """Deserialize pickled bytes back to a Scenario object or other data."""
        if isinstance(data, str):
            return pickle.loads(data.encode())
        return pickle.loads(data)


if use_sqlite := CONFIG.get("EDSL_USE_SQLITE_FOR_SCENARIO_LIST").lower() == "true":
    data_class = ScenarioSQLiteList
else:
    data_class = list


class ScenarioList(MutableSequence, Base, ScenarioListOperationsMixin):
    """
    A collection of Scenario objects with advanced operations for manipulation and analysis.

    ScenarioList provides specialized functionality for working with collections of
    Scenario objects. It inherits from MutableSequence to provide standard list operations,
    from Base to integrate with EDSL's object model, and from ScenarioListOperationsMixin
    to provide powerful data manipulation capabilities.

    Attributes:
        data (list): The underlying list containing Scenario objects.
        codebook (dict): Optional metadata describing the fields in the scenarios.
    """

    __documentation__ = (
        "https://docs.expectedparrot.com/en/latest/scenarios.html#scenariolist"
    )
    
    firecrawl = FirecrawlRequest()

    def __init__(
        self,
        data: Optional[list] = None,
        codebook: Optional[dict[str, str]] = None,
        data_class: Optional[type] = data_class,
    ):
        """Initialize a new ScenarioList with optional data and codebook."""
        self._data_class = data_class
        self.data = self._data_class([])
        for item in data or []:
            self.data.append(item)
        self.codebook = codebook or {}

    def is_serializable(self):
        for item in self.data:
            try:
                _ = json.dumps(item.to_dict())
            except Exception:
                return False
        return True

    # Required MutableSequence abstract methods
    def __getitem__(self, index):
        """Get item at index.

        Example:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList([Scenario({'a': 12})])
            >>> sl[0]['b'] = 100  # modify in-place
            >>> sl[0]['b']
            100
        """
        if isinstance(index, slice):
            return self.__class__(list(self.data[index]), self.codebook.copy())
        return self.data[index]

    def __setitem__(self, index, value):
        """Set item at index."""
        self.data[index] = value

    def __delitem__(self, index):
        """Delete item at index."""
        del self.data[index]

    def __len__(self):
        """Return number of items."""
        return len(self.data)

    def insert(self, index, value):
        """Insert value at index."""
        self.data.insert(index, value)

    def at(self, index: int) -> Scenario:
        """Get the scenario at the specified index position.
        >>> sl = ScenarioList.from_list("a", [1, 2, 3])
        >>> sl.at(0)
        Scenario({'a': 1})
        >>> sl.at(-1)
        Scenario({'a': 3})
        """
        return self.data[index]
    
    def sum(self, field: str) -> int:
        """Sum the values of a field across all scenarios."""
        return sum(scenario[field] for scenario in self)

    def unique(self) -> ScenarioList:
        """
        Return a new ScenarioList containing only unique Scenario objects.

        This method removes duplicate Scenario objects based on their hash values,
        which are determined by their content. Two Scenarios with identical key-value
        pairs will have the same hash and be considered duplicates.

        Returns:
            A new ScenarioList containing only unique Scenario objects.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> s1 = Scenario({"a": 1})
            >>> s2 = Scenario({"a": 1})  # Same content as s1
            >>> s3 = Scenario({"a": 2})
            >>> sl = ScenarioList([s1, s2, s3])
            >>> unique_sl = sl.unique()
            >>> len(unique_sl)
            2
            >>> unique_sl
            ScenarioList([Scenario({'a': 1}), Scenario({'a': 2})])

        Notes:
            - The order of scenarios in the result is not guaranteed due to the use of sets
            - Uniqueness is determined by the Scenario's __hash__ method
            - The original ScenarioList is not modified
            - This implementation is memory efficient as it processes scenarios one at a time
        """
        seen_hashes = set()
        result = ScenarioList()

        for scenario in self.data:
            scenario_hash = hash(scenario)
            if scenario_hash not in seen_hashes:
                seen_hashes.add(scenario_hash)
                result.append(scenario)

        return result

    def to_agent_traits(self, agent_name: Optional[str] = None) -> "Agent":
        """Convert all Scenario objects to traits of a single Agent.

        Delegates to `ScenarioListTransformer.to_agent_traits`.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.to_agent_traits(self, agent_name)

    @property
    def has_jinja_braces(self) -> bool:
        """
        Check if any Scenario in the list contains values with Jinja template braces.

        This property checks all Scenarios in the list to determine if any contain
        string values with Jinja template syntax ({{ and }}). This is important for
        rendering templates and avoiding conflicts with other templating systems.

        Returns:
            True if any Scenario contains values with Jinja braces, False otherwise.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> s1 = Scenario({"text": "Plain text"})
            >>> s2 = Scenario({"text": "Template with {{variable}}"})
            >>> sl1 = ScenarioList([s1])
            >>> sl1.has_jinja_braces
            False
            >>> sl2 = ScenarioList([s1, s2])
            >>> sl2.has_jinja_braces
            True
        """
        for scenario in self:
            if scenario.has_jinja_braces:
                return True
        return False

    def _convert_jinja_braces(self) -> ScenarioList:
        """
        Convert Jinja braces to alternative symbols in all Scenarios in the list.

        This method creates a new ScenarioList where all Jinja template braces
        ({{ and }}) in string values are converted to alternative symbols (<< and >>).
        This is useful when you need to prevent template processing or avoid conflicts
        with other templating systems.

        Returns:
            A new ScenarioList with converted braces in all Scenarios.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> s = Scenario({"text": "Template with {{variable}}"})
            >>> sl = ScenarioList([s])
            >>> converted = sl._convert_jinja_braces()
            >>> converted[0]["text"]
            'Template with <<variable>>'

        Notes:
            - The original ScenarioList is not modified
            - This is primarily intended for internal use
            - The default replacement symbols are << and >>
        """
        converted_sl = ScenarioList()
        for scenario in self:
            converted_sl.append(scenario._convert_jinja_braces())
        return converted_sl

    def give_valid_names(self, existing_codebook: dict = None) -> ScenarioList:
        """Give valid names to the scenario keys, using an existing codebook if provided.

        Args:
            existing_codebook (dict, optional): Existing mapping of original keys to valid names.
                Defaults to None.

        Returns:
            ScenarioList: A new ScenarioList with valid variable names and updated codebook.

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 2}), Scenario({'a': 1, 'b': 1})])
        >>> s.give_valid_names()
        ScenarioList([Scenario({'a': 1, 'b': 2}), Scenario({'a': 1, 'b': 1})])
        >>> s = ScenarioList([Scenario({'are you there John?': 1, 'b': 2}), Scenario({'a': 1, 'b': 1})])
        >>> s.give_valid_names()
        ScenarioList([Scenario({'john': 1, 'b': 2}), Scenario({'a': 1, 'b': 1})])
        >>> s.give_valid_names({'are you there John?': 'custom_name'})
        ScenarioList([Scenario({'custom_name': 1, 'b': 2}), Scenario({'a': 1, 'b': 1})])
        """
        codebook = existing_codebook.copy() if existing_codebook else {}

        new_scenarios = ScenarioList(data=[], codebook=codebook)

        for scenario in self:
            new_scenario = {}
            for key in scenario:
                if is_valid_variable_name(key):
                    new_scenario[key] = scenario[key]
                    continue

                if key in codebook:
                    new_key = codebook[key]
                else:
                    new_key = sanitize_string(key)
                    if not is_valid_variable_name(new_key):
                        new_key = f"var_{len(codebook)}"
                    codebook[key] = new_key

                new_scenario[new_key] = scenario[key]

            new_scenarios.append(Scenario(new_scenario))

        return new_scenarios

    def unpivot(
        self,
        id_vars: Optional[List[str]] = None,
        value_vars: Optional[List[str]] = None,
    ) -> ScenarioList:
        """Unpivot the ScenarioList, allowing for id variables.

        Delegates to `ScenarioListTransformer.unpivot`.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.unpivot(self, id_vars, value_vars)
    
    def apply(self, func: Callable, field: str, new_name: Optional[str], replace:bool = False) -> ScenarioList:
        """Apply a function to a field and return a new ScenarioList.

        Delegates to `ScenarioListTransformer.apply`.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.apply(self, func, field, new_name, replace)

    def zip(self, field_a: str, field_b: str, new_name: str) -> ScenarioList:
        """Zip two iterable fields in each Scenario into a dict under a new key.

        For every Scenario in the list, this method computes
        ``dict(zip(scenario[field_a], scenario[field_b]))`` and stores the result
        in a new key named ``new_name``. It returns a new ScenarioList containing
        the updated Scenarios.

        Args:
            field_a: Name of the first iterable field whose values become dict keys.
            field_b: Name of the second iterable field whose values become dict values.
            new_name: Name of the new field to store the resulting dictionary under.

        Returns:
            A new ScenarioList with the zipped dictionary added to each Scenario.

        Raises:
            KeyError: If either field name does not exist in any Scenario.
            ScenarioError: If referenced fields are not iterable in any Scenario.

        Examples:
            >>> sl = ScenarioList([
            ...     Scenario({"keys": ["a", "b"], "vals": [1, 2]}),
            ...     Scenario({"keys": ["x", "y"], "vals": [9, 8]}),
            ... ])
            >>> sl2 = sl.zip("keys", "vals", "mapping")
            >>> sl2[0]["mapping"], sl2[1]["mapping"]
            ({'a': 1, 'b': 2}, {'x': 9, 'y': 8})
        """
        new_list = ScenarioList(data=[], codebook=self.codebook)
        for scenario in self:
            new_list.append(scenario.zip(field_a, field_b, new_name))
        return new_list

    def add_scenario_reference(self, key, scenario_field_name: str) -> ScenarioList:
        """Add a reference to the scenario to a field across all Scenarios."""
        new_list = ScenarioList(data=[], codebook=self.codebook)
        for scenario in self:
            scenario[key] = scenario[key] + "{{ scenario." + scenario_field_name + " }}"
            new_list.append(scenario)
        return new_list

    def string_cat(
        self,
        key: str,
        addend: str,
        position: str = "suffix",
        inplace: bool = False,
    ) -> ScenarioList:
        """Concatenate a string to a field across all Scenarios.

        Applies the same behavior as ``Scenario.string_cat`` to each Scenario in the list.
        By default, returns a new ``ScenarioList``; set ``inplace=True`` to modify this list.

        Args:
            key: The key whose value will be concatenated in each Scenario.
            addend: The string to concatenate to the existing value.
            position: Either "suffix" (default) or "prefix".
            inplace: If True, modify scenarios in place and return self.

        Returns:
            A ``ScenarioList`` with updated Scenarios.

        Raises:
            KeyError: If ``key`` is missing in any Scenario.
            TypeError: If any value under ``key`` is not a string.
            ValueError: If ``position`` is not "suffix" or "prefix".
        """
        if inplace:
            for scenario in self:
                scenario.string_cat(key, addend, position=position, inplace=True)
            return self

        new_list = ScenarioList(data=[], codebook=self.codebook)
        for scenario in self:
            new_list.append(
                scenario.string_cat(key, addend, position=position, inplace=False)
            )
        return new_list

    def transform_by_key(self, key_field: str) -> Scenario:
        """Transform the ScenarioList into a single Scenario with key/value pairs.
        
        This method transforms the ScenarioList by:
        1. Using the value of the specified key_field from each Scenario as a new key
        2. Automatically formatting the remaining values as "key: value, key: value"
        3. Creating a single Scenario containing all the transformed key/value pairs
        
        Args:
            key_field: The field name whose value will become the new key
            
        Returns:
            A single Scenario with all the transformed key/value pairs
            
        Examples:
            >>> # Original scenarios: [{'topic': 'party', 'location': 'offsite', 'time': 'evening'}]
            >>> scenarios = ScenarioList([
            ...     Scenario({'topic': 'party', 'location': 'offsite', 'time': 'evening'})
            ... ])
            >>> transformed = scenarios.transform_by_key('topic')
            >>> # Result: Scenario({'party': 'location: offsite, time: evening'})
        """
        # Create a single dictionary to hold all key/value pairs
        combined_dict = {}
        
        for scenario in self:
            # Get the new key from the specified field
            new_key = scenario[key_field]
            
            # Get remaining values (excluding the key field)
            remaining_values = {k: v for k, v in scenario.items() if k != key_field}
            
            # Format the remaining values as "key: value, key: value"
            formatted_value = ", ".join([f"{k}: {v}" for k, v in remaining_values.items()])
            
            # Add to the combined dictionary
            combined_dict[new_key] = formatted_value
        
        # Return a single Scenario with all the key/value pairs
        return Scenario(combined_dict)

    @classmethod
    def from_prompt(
        self,
        description: str,
        name: Optional[str] = "item",
        target_number: int = 10,
        verbose=False,
    ):
        from ..questions.question_list import QuestionList

        q = QuestionList(
            question_name=name,
            question_text=description
            + f"\n Please try to return {target_number} examples.",
        )
        results = q.run(verbose=verbose)
        return results.select(name).to_scenario_list().expand(name)

    def __add__(self, other):
        if isinstance(other, Scenario):
            new_list = self.duplicate()
            new_list.append(other)
            return new_list
        elif isinstance(other, ScenarioList):
            new_list = self.duplicate()
            for item in other:
                new_list.append(item)
        else:
            raise ScenarioError("Don't know how to combine!")
        return new_list

    @classmethod
    def from_search_terms(cls, search_terms: List[str]) -> ScenarioList:
        """Create a ScenarioList from a list of search terms, using Wikipedia.

        Args:
            search_terms: A list of search terms.
        """
        from ..utilities.wikipedia import fetch_wikipedia_content

        results = fetch_wikipedia_content(search_terms)
        return cls([Scenario(result) for result in results])

    def augment_with_wikipedia(
        self,
        search_key: str,
        content_only: bool = True,
        key_name: str = "wikipedia_content",
    ) -> ScenarioList:
        """Augment the ScenarioList with Wikipedia content."""
        search_terms = self.select(search_key).to_list()
        wikipedia_results = ScenarioList.from_search_terms(search_terms)
        new_sl = ScenarioList(data=[], codebook=self.codebook)
        for scenario, wikipedia_result in zip(self, wikipedia_results):
            if content_only:
                scenario[key_name] = wikipedia_result["content"]
                new_sl.append(scenario)
            else:
                scenario[key_name] = wikipedia_result
                new_sl.append(scenario)
        return new_sl

    def pivot(
        self,
        id_vars: List[str] = None,
        var_name="variable",
        value_name="value",
    ) -> ScenarioList:
        """Pivot the ScenarioList from long to wide format.

        Delegates to `ScenarioListTransformer.pivot`.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.pivot(self, id_vars, var_name, value_name)

    def group_by(
        self, id_vars: List[str], variables: List[str], func: Callable
    ) -> ScenarioList:
        """Group the ScenarioList by id_vars and apply a function.

        Delegates to `ScenarioListTransformer.group_by`.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.group_by(self, id_vars, variables, func)

    @property
    def parameters(self) -> set:
        """Return the set of parameters in the ScenarioList

        Example:

        >>> s = ScenarioList([Scenario({'a': 1}), Scenario({'b': 2})])
        >>> s.parameters == {'a', 'b'}
        True
        """
        if len(self) == 0:
            return set()

        params = set()
        for scenario in self:
            params.update(scenario.keys())
        return params

    def __original_hash__(self) -> int:
        """Return the original hash of the ScenarioList using the dictionary-based approach.

        >>> s = ScenarioList.example()
        >>> s.__original_hash__()
        1262252885757976162
        """
        return dict_hash(self.to_dict(sort=True, add_edsl_version=False))

    def __hash__(self) -> int:
        """Return the hash of the ScenarioList using a memory-efficient streaming approach.

        >>> s = ScenarioList.example()
        >>> hash(s)
        1219708685929871252
        """
        # Start with a seed value
        running_hash = 0

        # Use a heap to maintain sorted order as we go
        import heapq

        heap = []

        # Process each scenario's hash and add to heap
        for scenario in self:
            heapq.heappush(heap, hash(scenario))

        # Combine hashes in sorted order
        while heap:
            h = heapq.heappop(heap)
            # Use a large prime number to mix the bits
            running_hash = (running_hash * 31) ^ h

        return running_hash

    def __eq__(self, other: Any) -> bool:
        return hash(self) == hash(other)

    def __repr__(self):
        return f"ScenarioList({list(self.data)})"

    def __mul__(self, other: ScenarioList) -> ScenarioList:
        """Takes the cross product of two ScenarioLists.

        >>> s1 = ScenarioList.from_list("a", [1, 2])
        >>> s2 = ScenarioList.from_list("b", [3, 4])
        >>> s1 * s2
        ScenarioList([Scenario({'a': 1, 'b': 3}), Scenario({'a': 1, 'b': 4}), Scenario({'a': 2, 'b': 3}), Scenario({'a': 2, 'b': 4})])
        """
        from itertools import product
        from .scenario import Scenario

        if isinstance(other, Scenario):
            other = ScenarioList([other])
        elif not isinstance(other, ScenarioList):
            from .exceptions import TypeScenarioError

            raise TypeScenarioError(f"Cannot multiply ScenarioList with {type(other)}")

        new_sl = ScenarioList(data=[], codebook=self.codebook)
        for s1, s2 in product(self, other):
            new_sl.append(s1 + s2)
        return new_sl

    def times(self, other: ScenarioList) -> ScenarioList:
        """Takes the cross product of two ScenarioLists.

        Example:

        >>> s1 = ScenarioList([Scenario({'a': 1}), Scenario({'a': 2})])
        >>> s2 = ScenarioList([Scenario({'b': 1}), Scenario({'b': 2})])
        >>> s1 * s2
        ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2}), Scenario({'a': 2, 'b': 1}), Scenario({'a': 2, 'b': 2})])
        """

        warnings.warn("times is deprecated, use * instead", DeprecationWarning)
        return self.__mul__(other)

    def shuffle(self, seed: Optional[str] = None) -> ScenarioList:
        """Shuffle the ScenarioList.

        >>> s = ScenarioList.from_list("a", [1,2,3,4])
        >>> s.shuffle(seed = "1234")
        ScenarioList([Scenario({'a': 1}), Scenario({'a': 4}), Scenario({'a': 3}), Scenario({'a': 2})])
        """
        sl = self.duplicate()
        if seed:
            random.seed(seed)
        random.shuffle(sl.data)
        return sl

    def sample(self, n: int, seed: Optional[str] = None) -> ScenarioList:
        """Return a random sample from the ScenarioList

        >>> s = ScenarioList.from_list("a", [1,2,3,4,5,6])
        >>> s.sample(3, seed = "edsl")  # doctest: +SKIP
        ScenarioList([Scenario({'a': 2}), Scenario({'a': 1}), Scenario({'a': 3})])
        """
        if seed:
            random.seed(seed)

        sl = self.duplicate()
        # Convert to list if necessary for random.sample
        data_list = list(sl.data)
        return ScenarioList(random.sample(data_list, n))

    def expand(self, expand_field: str, number_field: bool = False) -> ScenarioList:
        """Expand the ScenarioList by a field.

        :param expand_field: The field to expand.
        :param number_field: Whether to add a field with the index of the value

        Example:

        >>> s = ScenarioList( [ Scenario({'a':1, 'b':[1,2]}) ] )
        >>> s.expand('b')
        ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        >>> s.expand('b', number_field=True)
        ScenarioList([Scenario({'a': 1, 'b': 1, 'b_number': 1}), Scenario({'a': 1, 'b': 2, 'b_number': 2})])
        """
        new_scenarios = []
        for scenario in self:
            values = scenario[expand_field]
            if not isinstance(values, Iterable) or isinstance(values, str):
                values = [values]
            for index, value in enumerate(values):
                new_scenario = scenario.copy()
                new_scenario[expand_field] = value
                if number_field:
                    new_scenario[expand_field + "_number"] = index + 1
                new_scenarios.append(new_scenario)
        return ScenarioList(new_scenarios)

    def _concatenate(
        self,
        fields: List[str],
        output_type: str = "string",
        separator: str = ";",
        prefix: str = "",
        postfix: str = "",
        new_field_name: Optional[str] = None,
    ) -> ScenarioList:
        """Private method to handle concatenation logic for different output types.

        Delegates to `ScenarioListTransformer._concatenate` for implementation.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer._concatenate(
            self,
            fields,
            output_type=output_type,
            separator=separator,
            prefix=prefix,
            postfix=postfix,
            new_field_name=new_field_name,
        )

    def concatenate(
        self,
        fields: List[str],
        separator: str = ";",
        prefix: str = "",
        postfix: str = "",
        new_field_name: Optional[str] = None,
    ) -> ScenarioList:
        """Concatenate specified fields into a single string field.

        Delegates to `ScenarioListTransformer.concatenate` for implementation.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.concatenate(
            self,
            fields,
            separator=separator,
            prefix=prefix,
            postfix=postfix,
            new_field_name=new_field_name,
        )

    def concatenate_to_list(
        self,
        fields: List[str],
        prefix: str = "",
        postfix: str = "",
        new_field_name: Optional[str] = None,
    ) -> ScenarioList:
        """Concatenate specified fields into a single list field.

        Delegates to `ScenarioListTransformer.concatenate_to_list` for implementation.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.concatenate_to_list(
            self,
            fields,
            prefix=prefix,
            postfix=postfix,
            new_field_name=new_field_name,
        )

    def concatenate_to_set(
        self,
        fields: List[str],
        prefix: str = "",
        postfix: str = "",
        new_field_name: Optional[str] = None,
    ) -> ScenarioList:
        """Concatenate specified fields into a single set field.

        Delegates to `ScenarioListTransformer.concatenate_to_set` for implementation.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.concatenate_to_set(
            self,
            fields,
            prefix=prefix,
            postfix=postfix,
            new_field_name=new_field_name,
        )

    def unpack_dict(
        self, field: str, prefix: Optional[str] = None, drop_field: bool = False
    ) -> ScenarioList:
        """Unpack a dictionary field into separate fields.

        Delegates to `ScenarioListTransformer.unpack_dict`.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.unpack_dict(self, field, prefix, drop_field)

    def transform(
        self, field: str, func: Callable, new_name: Optional[str] = None
    ) -> ScenarioList:
        """Transform a field using a function.

        Delegates to `ScenarioListTransformer.transform`.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.transform(self, field, func, new_name)

    def mutate(
        self, new_var_string: str, functions_dict: Optional[dict[str, Callable]] = None
    ) -> ScenarioList:
        """Return a new ScenarioList with a new variable added.

        Delegates to `ScenarioListTransformer.mutate`.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.mutate(self, new_var_string, functions_dict)

    def order_by(self, *fields: str, reverse: bool = False) -> ScenarioList:
        """Order the scenarios by one or more fields.

        Delegates to `ScenarioListTransformer.order_by`.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.order_by(self, list(fields), reverse)

    def duplicate(self) -> ScenarioList:
        """Return a copy of the ScenarioList using streaming to avoid loading everything into memory.

        >>> sl = ScenarioList.example()
        >>> sl_copy = sl.duplicate()
        >>> sl == sl_copy
        True
        >>> sl is sl_copy
        False
        """
        new_list = ScenarioList()
        for scenario in self.data:
            new_list.append(scenario.copy())
        return new_list

    def offload(self, inplace: bool = False) -> "ScenarioList":
        """
        Offloads base64-encoded content from all scenarios in the list by replacing
        'base64_string' fields with 'offloaded'. This reduces memory usage.

        Args:
            inplace (bool): If True, modify the current scenario list. If False, return a new one.

        Returns:
            ScenarioList: The modified scenario list (either self or a new instance).
        """
        if inplace:
            for i, scenario in enumerate(self.data):
                self.data[i] = scenario.offload(inplace=True)
            return self
        else:
            new_list = ScenarioList(codebook=self.codebook)
            for scenario in self.data:
                new_list.append(scenario.offload(inplace=False))
            return new_list

    def __iter__(self):
        """Iterate over scenarios using streaming."""
        return iter(self.data)

    def equals(self, other: Any) -> bool:
        """Memory-efficient comparison of two ScenarioLists."""
        if not isinstance(other, ScenarioList):
            return False
        if len(self) != len(other):
            return False
        if self.codebook != other.codebook:
            return False
        return self.data == other.data

    @memory_profile
    def filter(self, expression: str) -> ScenarioList:
        """Filter a list of scenarios based on an expression.

        Delegates to `ScenarioListTransformer.filter`.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.filter(self, expression)

    @classmethod
    def from_urls(
        cls, urls: list[str], field_name: Optional[str] = "text"
    ) -> ScenarioList:
        from .scenario_source import URLSource

        return URLSource(urls, field_name).to_scenario_list()

    @classmethod
    def from_list(
        cls, field_name: str, values: list, use_indexes: bool = False
    ) -> ScenarioList:
        """Create a ScenarioList from a list of values with a specified field name.

        >>> ScenarioList.from_list('text', ['a', 'b', 'c'])
        ScenarioList([Scenario({'text': 'a'}), Scenario({'text': 'b'}), Scenario({'text': 'c'})])
        """
        from .scenario_source import ListSource

        return ListSource(field_name, values, use_indexes).to_scenario_list()

    def select(self, *fields: str) -> ScenarioList:
        """Select only specified fields from all scenarios in the list.

        This method applies the select operation to each scenario in the list,
        returning a new ScenarioList where each scenario contains only the 
        specified fields.

        Args:
            *fields: Field names to select from each scenario.

        Returns:
            A new ScenarioList with each scenario containing only the selected fields.

        Raises:
            KeyError: If any specified field doesn't exist in any scenario.

        Examples:
            >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
            >>> s.select('a')
            ScenarioList([Scenario({'a': 1}), Scenario({'a': 1})])
        """
        new_sl = ScenarioList(data=[], codebook=self.codebook)
        for scenario in self:
            new_sl.append(scenario.select(*fields))
        return new_sl

    def drop(self, *fields: str) -> ScenarioList:
        """Drop fields from the scenarios.

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        >>> s.drop('a')
        ScenarioList([Scenario({'b': 1}), Scenario({'b': 2})])
        """
        new_sl = ScenarioList(data=[], codebook=self.codebook)
        for scenario in self:
            new_sl.append(scenario.drop(fields))
        return new_sl

    def keep(self, *fields: str) -> ScenarioList:
        """Keep only the specified fields in the scenarios.

        :param fields: The fields to keep.

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        >>> s.keep('a')
        ScenarioList([Scenario({'a': 1}), Scenario({'a': 1})])
        """
        new_sl = ScenarioList(data=[], codebook=self.codebook)
        for scenario in self:
            new_sl.append(scenario.keep(fields))
        return new_sl

    @classmethod
    def from_directory(
        cls,
        path: Optional[str] = None,
        recursive: bool = False,
        key_name: str = "content",
    ) -> "ScenarioList":
        """Create a ScenarioList of Scenario objects from files in a directory.

        This method scans a directory and creates a Scenario object for each file found,
        where each Scenario contains a FileStore object under the specified key.
        Optionally filters files based on a wildcard pattern. If no path is provided,
        the current working directory is used.

        Args:
            path: The directory path to scan, optionally including a wildcard pattern.
                 If None, uses the current working directory.
                 Examples:
                 - "/path/to/directory" - scans all files in the directory
                 - "/path/to/directory/*.py" - scans only Python files in the directory
                 - "*.txt" - scans only text files in the current working directory
            recursive: Whether to scan subdirectories recursively. Defaults to False.
            key_name: The key to use for the FileStore object in each Scenario. Defaults to "content".

        Returns:
            A ScenarioList containing Scenario objects for all matching files, where each Scenario
            has a FileStore object under the specified key.

        Raises:
            FileNotFoundError: If the specified directory does not exist.

        Examples:
            # Get all files in the current directory with default key "content"
            sl = ScenarioList.from_directory()

            # Get all Python files in a specific directory with custom key "python_file"
            sl = ScenarioList.from_directory('*.py', key_name="python_file")

            # Get all image files in the current directory
            sl = ScenarioList.from_directory('*.png', key_name="image")

            # Get all files recursively including subdirectories
            sl = ScenarioList.from_directory(recursive=True, key_name="document")
        """

        warnings.warn(
            "from_directory is deprecated. Use ScenarioSource.from_source('directory', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from .scenario_source import DirectorySource

        source = DirectorySource(
            directory=path or os.getcwd(),
            pattern="*",
            recursive=recursive,
            metadata=True,
        )

        # Get the ScenarioList with FileStore objects under "file" key
        sl = source.to_scenario_list()

        # If the requested key is different from the default "file" key used by DirectoryScanner.scan_directory,
        # rename the keys in all scenarios
        if key_name != "file":
            # Create a new ScenarioList
            result = ScenarioList([])
            for scenario in sl:
                # Create a new scenario with the file under the specified key
                new_data = {key_name: scenario["file"]}
                # Add all other fields from the original scenario
                for k, v in scenario.items():
                    if k != "file":
                        new_data[k] = v
                result.append(Scenario(new_data))
            return result

        return sl

    # @classmethod
    # def from_list(
    #     cls, name: str, values: list, func: Optional[Callable] = None
    # ) -> ScenarioList:
    #     """Create a ScenarioList from a list of values.

    #     :param name: The name of the field.
    #     :param values: The list of values.
    #     :param func: An optional function to apply to the values.

    #     Example:

    #     >>> ScenarioList.from_list('name', ['Alice', 'Bob'])
    #     ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
    #     """
    #     if not func:

    #         def identity(x):
    #             return x

    #         func = identity
    #     return cls([Scenario({name: func(value)}) for value in values])

    def table(
        self,
        *fields: str,
        tablefmt: Optional[TableFormat] = "rich",
        pretty_labels: Optional[dict[str, str]] = None,
    ) -> str:
        """Return the ScenarioList as a table."""

        if tablefmt is not None and tablefmt not in (tabulate_formats + ["rich"]):
            raise ValueError(
                f"Invalid table format: {tablefmt}",
                f"Valid formats are: {tabulate_formats}",
            )
        return self.to_dataset().table(
            *fields, tablefmt=tablefmt, pretty_labels=pretty_labels
        )

    def tree(self, node_list: Optional[List[str]] = None) -> str:
        """Return the ScenarioList as a tree.

        :param node_list: The list of nodes to include in the tree.
        """
        return self.to_dataset().tree(node_list)

    def _summary(self) -> dict:
        """Return a summary of the ScenarioList.

        >>> ScenarioList.example()._summary()
        {'scenarios': 2, 'keys': ['persona']}
        """
        d = {
            "scenarios": len(self),
            "keys": list(self.parameters),
        }
        return d

    def reorder_keys(self, new_order: List[str]) -> ScenarioList:
        """Reorder the keys in the scenarios.

        Delegates to `ScenarioListTransformer.reorder_keys`.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.reorder_keys(self, new_order)

    def to_survey(self) -> "Survey":
        from ..questions import QuestionBase
        from ..surveys import Survey


        s = Survey()
        for index, scenario in enumerate(self):
            d = scenario.to_dict(add_edsl_version=False)
            if d["question_type"] == "free_text":
                if "question_options" in d:
                    _ = d.pop("question_options")
            if 'question_name' not in d or d['question_name'] == None:
                d['question_name'] = f"question_{index}"

            if d['question_type'] == None:
                d['question_type'] = "free_text"
                d['question_options'] = None
            new_d = d
            question = QuestionBase.from_dict(new_d)
            s.add_question(question)

        return s

    def to_dataset(self) -> "Dataset":
        """
        Convert the ScenarioList to a Dataset.

        >>> s = ScenarioList.from_list("a", [1,2,3])
        >>> s.to_dataset()
        Dataset([{'a': [1, 2, 3]}])
        >>> s = ScenarioList.from_list("a", [1,2,3]).add_list("b", [4,5,6])
        >>> s.to_dataset()
        Dataset([{'a': [1, 2, 3]}, {'b': [4, 5, 6]}])
        """
        from ..dataset import Dataset

        if not self.data:
            return Dataset([])

        keys = list(self[0].keys())
        for scenario in self:
            new_keys = list(scenario.keys())
            if new_keys != keys:
                # Use dict.fromkeys to preserve order while ensuring uniqueness
                keys = list(dict.fromkeys(keys + new_keys))
        data = [
            {key: [scenario.get(key, None) for scenario in self.data]} for key in keys
        ]
        return Dataset(data)

    def to_scenario_of_lists(self) -> "Scenario":
        """Return a single Scenario whose values are lists across the list.

        The resulting Scenario contains every key that appears in any member
        of the list. For each key, the value is a list of that key's values
        taken row-wise from the ScenarioList, padding with None when a row is
        missing the key.

        >>> s = ScenarioList.from_list("a", [1, 2, 3])
        >>> s.to_scenario_of_lists()
        Scenario({'a': [1, 2, 3]})
        >>> s2 = ScenarioList([Scenario({'a': 1}), Scenario({'b': 2})])
        >>> s2.to_scenario_of_lists()
        Scenario({'a': [1, None], 'b': [None, 2]})
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.to_scenario_of_lists(self)

    def unpack(
        self, field: str, new_names: Optional[List[str]] = None, keep_original=True
    ) -> ScenarioList:
        """Unpack a field into multiple fields.

        Delegates to `ScenarioListTransformer.unpack`.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.unpack(self, field, new_names, keep_original)

    def add_list(self, name: str, values: List[Any]) -> ScenarioList:
        """Add a list of values to a ScenarioList.

        Example:

        >>> s = ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
        >>> s.add_list('age', [30, 25])
        ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
        """
        # sl = self.duplicate()
        if len(values) != len(self.data):
            raise ScenarioError(
                f"Length of values ({len(values)}) does not match length of ScenarioList ({len(self)})"
            )
        new_sl = ScenarioList(data=[], codebook=self.codebook)
        for i, value in enumerate(values):
            scenario = self.data[i]
            scenario[name] = value
            new_sl.append(scenario)
        return new_sl

    @classmethod
    def create_empty_scenario_list(cls, n: int) -> ScenarioList:
        """Create an empty ScenarioList with n scenarios.

        Args:
            n: The number of empty scenarios to create

        Example:

        >>> ScenarioList.create_empty_scenario_list(3)
        ScenarioList([Scenario({}), Scenario({}), Scenario({})])
        """
        return ScenarioList([Scenario({}) for _ in range(n)])

    def add_value(self, name: str, value: Any) -> ScenarioList:
        """Add a value to all scenarios in a ScenarioList.

        Example:

        >>> s = ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
        >>> s.add_value('age', 30)
        ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 30})])
        """
        new_sl = ScenarioList(data=[], codebook=self.codebook)
        for scenario in self:
            scenario[name] = value
            new_sl.append(scenario)
        return new_sl

    def tack_on(self, replacements: dict[str, Any], index: int = -1) -> "ScenarioList":
        """Add a duplicate of an existing scenario with optional value replacements.

        This method duplicates the scenario at *index* (default ``-1`` which refers to the
        last scenario), applies the key/value pairs provided in *replacements*, and
        returns a new ScenarioList with the modified scenario appended.

        Args:
            replacements: Mapping of field names to new values to overwrite in the cloned
                scenario.
            index: Index of the scenario to duplicate. Supports negative indexing just
                like normal Python lists (``-1`` is the last item).

        Returns:
            ScenarioList: A new ScenarioList containing all original scenarios plus the
            newly created one.

        Raises:
            ScenarioError: If the ScenarioList is empty, *index* is out of range, or if
                any key in *replacements* does not exist in the reference scenario.
        """
        # Ensure there is at least one scenario to duplicate
        if len(self) == 0:
            raise ScenarioError("Cannot tack_on to an empty ScenarioList.")

        # Resolve negative indices and validate range
        if index < 0:
            index = len(self) + index
        if index < 0 or index >= len(self):
            raise ScenarioError(
                f"Index {index} is out of range for ScenarioList of length {len(self)}."
            )

        # Reference scenario to clone
        reference = self[index]

        # Verify that all replacement keys are present in the scenario
        missing_keys = [key for key in replacements if key not in reference]
        if missing_keys:
            raise ScenarioError(
                f"Replacement keys not found in scenario: {', '.join(missing_keys)}"
            )

        # Create a modified copy of the scenario
        new_scenario = reference.copy()
        for key, value in replacements.items():
            new_scenario[key] = value

        # Duplicate the ScenarioList and append the modified scenario
        new_sl = self.duplicate()
        new_sl.append(new_scenario)
        return new_sl

    def rename(self, replacement_dict: dict) -> ScenarioList:
        """Rename the fields in the scenarios.

        :param replacement_dict: A dictionary with the old names as keys and the new names as values.

        Example:

        >>> s = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
        >>> s.rename({'name': 'first_name', 'age': 'years'})
        ScenarioList([Scenario({'first_name': 'Alice', 'years': 30}), Scenario({'first_name': 'Bob', 'years': 25})])

        """
        new_sl = ScenarioList(data=[], codebook=self.codebook)
        for scenario in self:
            new_scenario = scenario.rename(replacement_dict)
            new_sl.append(new_scenario)
        return new_sl

    def replace_names(self, new_names: list) -> ScenarioList:
        """Replace the field names in the scenarios with a new list of names.

        :param new_names: A list of new field names to use.

        Example:

        >>> s = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
        >>> s.replace_names(['first_name', 'years'])
        ScenarioList([Scenario({'first_name': 'Alice', 'years': 30}), Scenario({'first_name': 'Bob', 'years': 25})])
        """
        if not self:
            return ScenarioList([])

        if len(new_names) != len(self[0].keys()):
            raise ScenarioError(
                f"Length of new names ({len(new_names)}) does not match number of fields ({len(self[0].keys())})"
            )

        old_names = list(self[0].keys())
        replacement_dict = dict(zip(old_names, new_names))
        return self.rename(replacement_dict)


    def to_key_value(self, field: str, value=None) -> Union[dict, set]:
        """Return the set of values in the field.

        :param field: The field to extract values from.
        :param value: An optional field to use as the value in the key-value pair.

        Example:

        >>> s = ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
        >>> s.to_key_value('name') == {'Alice', 'Bob'}
        True
        """
        if value is None:
            return {scenario[field] for scenario in self}
        else:
            return {scenario[field]: scenario[value] for scenario in self}

    def left_join(self, other: ScenarioList, by: Union[str, list[str]]) -> ScenarioList:
        """Perform a left join with another ScenarioList, following SQL join semantics.

        Args:
            other: The ScenarioList to join with
            by: String or list of strings representing the key(s) to join on. Cannot be empty.

        >>> s1 = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
        >>> s2 = ScenarioList([Scenario({'name': 'Alice', 'location': 'New York'}), Scenario({'name': 'Charlie', 'location': 'Los Angeles'})])
        >>> s3 = s1.left_join(s2, 'name')
        >>> s3 == ScenarioList([Scenario({'age': 30, 'location': 'New York', 'name': 'Alice'}), Scenario({'age': 25, 'location': None, 'name': 'Bob'})])
        True
        """
        from .scenario_join import ScenarioJoin

        sj = ScenarioJoin(self, other)
        return sj.left_join(by)

    def inner_join(self, other: ScenarioList, by: Union[str, list[str]]) -> ScenarioList:
        """Perform an inner join with another ScenarioList, following SQL join semantics.

        Args:
            other: The ScenarioList to join with
            by: String or list of strings representing the key(s) to join on. Cannot be empty.

        Returns:
            A new ScenarioList containing only scenarios that have matches in both ScenarioLists

        >>> s1 = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
        >>> s2 = ScenarioList([Scenario({'name': 'Alice', 'location': 'New York'}), Scenario({'name': 'Charlie', 'location': 'Los Angeles'})])
        >>> s4 = s1.inner_join(s2, 'name')
        >>> s4 == ScenarioList([Scenario({'age': 30, 'location': 'New York', 'name': 'Alice'})])
        True
        """
        from .scenario_join import ScenarioJoin

        sj = ScenarioJoin(self, other)
        return sj.inner_join(by)

    def right_join(self, other: ScenarioList, by: Union[str, list[str]]) -> ScenarioList:
        """Perform a right join with another ScenarioList, following SQL join semantics.

        Args:
            other: The ScenarioList to join with
            by: String or list of strings representing the key(s) to join on. Cannot be empty.

        Returns:
            A new ScenarioList containing all right scenarios with matching left data added

        >>> s1 = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
        >>> s2 = ScenarioList([Scenario({'name': 'Alice', 'location': 'New York'}), Scenario({'name': 'Charlie', 'location': 'Los Angeles'})])
        >>> s5 = s1.right_join(s2, 'name')
        >>> s5 == ScenarioList([Scenario({'age': 30, 'location': 'New York', 'name': 'Alice'}), Scenario({'age': None, 'location': 'Los Angeles', 'name': 'Charlie'})])
        True
        """
        from .scenario_join import ScenarioJoin

        sj = ScenarioJoin(self, other)
        return sj.right_join(by)

    def to_dict(self, sort: bool = False, add_edsl_version: bool = False) -> dict:
        """
        >>> s = ScenarioList([Scenario({'food': 'wood chips'}), Scenario({'food': 'wood-fired pizza'})])
        >>> s.to_dict()
        {'scenarios': [{'food': 'wood chips'}, {'food': 'wood-fired pizza'}]}

        >>> s = ScenarioList([Scenario({'food': 'wood chips'})], codebook={'food': 'description'})
        >>> d = s.to_dict()
        >>> 'codebook' in d
        True
        >>> d['codebook'] == {'food': 'description'}
        True
        
        >>> # To include edsl_version and edsl_class_name, explicitly set add_edsl_version=True
        >>> s.to_dict(add_edsl_version=True)  # doctest: +ELLIPSIS
        {'scenarios': [{'food': 'wood chips', 'edsl_version': '...', 'edsl_class_name': 'Scenario'}], 'codebook': {'food': 'description'}, 'edsl_version': '...', 'edsl_class_name': 'ScenarioList'}
        """
        if sort:
            data = sorted(self, key=lambda x: hash(x))
        else:
            data = self

        d = {"scenarios": [s.to_dict(add_edsl_version=add_edsl_version) for s in data]}

        # Add codebook if it exists
        if hasattr(self, "codebook") and self.codebook:
            d["codebook"] = self.codebook

        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = self.__class__.__name__
        return d

    def clipboard_data(self) -> str:
        """Return TSV representation of this ScenarioList for clipboard operations.

        This method is called by the clipboard() method in the base class to provide
        a custom format for copying ScenarioList objects to the system clipboard.

        Returns:
            str: Tab-separated values representation of the ScenarioList
        """
        # Use the to_csv method with tab separator to create TSV format
        csv_filestore = self.to_csv()

        # Get the CSV content and convert it to TSV
        csv_content = csv_filestore.text

        # Convert CSV to TSV by replacing commas with tabs
        # This is a simple approach, but we should handle quoted fields properly
        import io

        # Parse the CSV content
        csv_reader = csv.reader(io.StringIO(csv_content))
        rows = list(csv_reader)

        # Convert to TSV format
        tsv_lines = []
        for row in rows:
            tsv_lines.append("\t".join(row))

        return "\n".join(tsv_lines)

    def to(self, survey: Union["Survey", "QuestionBase"]) -> "Jobs":
        """Create a Jobs object from a ScenarioList and a Survey object.

        :param survey: The Survey object to use for the Jobs object.

        Example:
        >>> from edsl import Survey, Jobs, ScenarioList  # doctest: +SKIP
        >>> isinstance(ScenarioList.example().to(Survey.example()), Jobs)  # doctest: +SKIP
        True
        """
        from ..surveys import Survey
        from ..questions import QuestionBase

        if isinstance(survey, QuestionBase):
            return Survey([survey]).by(self)
        else:
            return survey.by(self)

    def for_n(
        self, target: Union["Question", "Survey", "Job"], iterations: int
    ) -> "Jobs":
        """Execute a target multiple times, feeding each iteration's output
        into the next.

        Parameters
        ----------
        target : Question | Survey | Job
            The object to be executed on each round. A fresh ``duplicate()`` of
            *target* is taken for every iteration so that state is **not** shared
            between runs.
        iterations : int
            How many times to run *target*.

        Returns
        -------
        Jobs
            A :class:`~edsl.jobs.Jobs` instance containing the results of the
            final iteration.

        Example (non-doctest)::

            from edsl import ScenarioList, QuestionFreeText

            base_personas = ScenarioList.from_list(
                "persona",
                [
                    "- Likes basketball",
                    "- From Germany",
                    "- Once owned a sawmill",
                ],
            )

            persona_detail_jobs = (
                QuestionFreeText(
                    question_text=(
                        "Take this persona: {{ scenario.persona }} and add one additional detail, "
                        "preserving the original details."
                    ),
                    question_name="enhance",
                )
                .to_jobs()
                .select("enhance")
                .to_scenario_list()
                .rename({"enhance": "persona"})
            )

            # Run the enrichment five times
            enriched_personas = base_personas.for_n(persona_detail_jobs, 5)

            print(enriched_personas.select("persona"))
        """

        intermediate_result = self
        for i in range(iterations):
            clean_target = target.duplicate()
            new_jobs = clean_target.by(intermediate_result)
            intermediate_result = new_jobs.run()
        return intermediate_result

    @classmethod
    def gen(cls, scenario_dicts_list: List[dict]) -> ScenarioList:
        """Create a `ScenarioList` from a list of dictionaries.

        Example:

        >>> ScenarioList.gen([{'name': 'Alice'}, {'name': 'Bob'}])
        ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])

        """
        from .scenario import Scenario

        return cls([Scenario(s) for s in scenario_dicts_list])

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict) -> ScenarioList:
        """Create a `ScenarioList` from a dictionary.

        >>> d = {'scenarios': [{'food': 'wood chips'}], 'codebook': {'food': 'description'}}
        >>> s = ScenarioList.from_dict(d)
        >>> s.codebook == {'food': 'description'}
        True
        >>> s[0]['food']
        'wood chips'
        """
        from .scenario import Scenario

        # Extract codebook if it exists
        codebook = data.get("codebook", None)

        # Create ScenarioList with scenarios and codebook
        return cls(
            [Scenario.from_dict(s) for s in data["scenarios"]], codebook=codebook
        )

    @classmethod
    def from_nested_dict(cls, data: dict) -> ScenarioList:
        """Create a `ScenarioList` from a nested dictionary.

        >>> data = {"headline": ["Armistice Signed, War Over: Celebrations Erupt Across City"], "date": ["1918-11-11"], "author": ["Jane Smith"]}
        >>> ScenarioList.from_nested_dict(data)
        ScenarioList([Scenario({'headline': 'Armistice Signed, War Over: Celebrations Erupt Across City', 'date': '1918-11-11', 'author': 'Jane Smith'})])

        """
        length_of_first_list = len(next(iter(data.values())))
        s = ScenarioList.create_empty_scenario_list(n=length_of_first_list)

        if any(len(v) != length_of_first_list for v in data.values()):
            raise ValueError(
                "All lists in the dictionary must be of the same length.",
            )
        for key, list_of_values in data.items():
            s = s.add_list(key, list_of_values)
        return s

    def code(self) -> str:
        """Create the Python code representation of a survey."""
        header_lines = [
            "from edsl.scenarios import Scenario",
            "from edsl.scenarios import ScenarioList",
        ]
        lines = ["\n".join(header_lines)]
        names = []
        for index, scenario in enumerate(self):
            lines.append(f"scenario_{index} = " + repr(scenario))
            names.append(f"scenario_{index}")
        lines.append(f"scenarios = ScenarioList([{', '.join(names)}])")
        return lines

    @classmethod
    def example(cls, randomize: bool = False) -> ScenarioList:
        """
        Return an example ScenarioList instance.

        :params randomize: If True, use Scenario's randomize method to randomize the values.
        """
        return cls([Scenario.example(randomize), Scenario.example(randomize)])

    def items(self):
        """Make this class compatible with dict.items() by accessing first scenario items.

        This ensures the class works as a drop-in replacement for UserList in code
        that expects a dictionary-like interface.

        Returns:
            items view from the first scenario object if available, empty list otherwise
        """
        if len(self.data) > 0:
            return self.data[0].items()
        return {}.items()

    def copy(self):
        """Create a copy of this ScenarioList.

        Returns:
            A new ScenarioList with copies of the same scenarios
        """
        # Get copies of all scenarios
        if len(self.data) > 0:
            # If we have at least one scenario, copy the first one
            if hasattr(self.data[0], "copy"):
                return self.data[0].copy()
            # Otherwise try to convert to Scenario
            from .scenario import Scenario

            try:
                return Scenario(dict(self.data[0]))
            except (TypeError, ValueError):
                # Fallback to empty scenario
                return Scenario({})

    def to_agent_list(self):
        """Convert the ScenarioList to an AgentList.

        This method supports special fields that map to Agent parameters:
        - "name": Will be used as the agent's name
        - "agent_parameters": A dictionary containing:
            - "instruction": The agent's instruction text
            - "name": The agent's name (overrides the "name" field if present)

        Example:
            >>> from edsl import ScenarioList, Scenario
            >>> # Basic usage with traits
            >>> s = ScenarioList([Scenario({'age': 22, 'hair': 'brown', 'height': 5.5})])
            >>> al = s.to_agent_list()
            >>> al
            AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})])

            >>> # Using agent name
            >>> s = ScenarioList([Scenario({'name': 'Alice', 'age': 22})])
            >>> al = s.to_agent_list()
            >>> al[0].name
            'Alice'

            >>> # Using agent parameters for instructions
            >>> s = ScenarioList([Scenario({
            ...     'age': 22,
            ...     'agent_parameters': {
            ...         'instruction': 'You are a helpful assistant',
            ...         'name': 'Assistant'
            ...     }
            ... })])
            >>> al = s.to_agent_list()
            >>> al[0].instruction
            'You are a helpful assistant'
            >>> al[0].name
            'Assistant'
        """
        from ..agents import AgentList

        return AgentList.from_scenario_list(self)

    def to_ranked_scenario_list(
        self,
        option_fields: Sequence[str],
        answer_field: str,
        include_rank: bool = True,
        rank_field: str = "rank",
        item_field: str = "item"
    ) -> "ScenarioList":
        """Convert the ScenarioList to a ranked ScenarioList based on pairwise comparisons.

        Args:
            option_fields: List of scenario column names containing options to compare.
            answer_field: Name of the answer column containing the chosen option's value.
            include_rank: If True, include a rank field on each returned Scenario.
            rank_field: Name of the rank field to include when include_rank is True.
            item_field: Field name used to store the ranked item value on each Scenario.

        Returns:
            ScenarioList ordered best-to-worst according to pairwise ranking.
        """
        from .ranking_algorithm import results_to_ranked_scenario_list
        return results_to_ranked_scenario_list(
            self,
            option_fields=option_fields,
            answer_field=answer_field,
            include_rank=include_rank,
            rank_field=rank_field,
            item_field=item_field
        )

    def to_true_skill_ranked_list(
        self,
        option_fields: Sequence[str],
        answer_field: str,
        include_rank: bool = True,
        rank_field: str = "rank",
        item_field: str = "item",
        mu_field: str = "mu",
        sigma_field: str = "sigma",
        conservative_rating_field: str = "conservative_rating",
        initial_mu: float = 25.0,
        initial_sigma: float = 8.333,
        beta: float = None,
        tau: float = None
    ) -> "ScenarioList":
        """Convert the ScenarioList to a ranked ScenarioList using TrueSkill algorithm.
        Args:
            option_fields: List of scenario column names containing options to compare.
            answer_field: Name of the answer column containing the ranking order.
            include_rank: If True, include a rank field on each returned Scenario.
            rank_field: Name of the rank field to include when include_rank is True.
            item_field: Field name used to store the ranked item value on each Scenario.
            mu_field: Field name for TrueSkill mu (skill estimate) value.
            sigma_field: Field name for TrueSkill sigma (uncertainty) value.
            conservative_rating_field: Field name for conservative rating (mu - 3*sigma).
            initial_mu: Initial skill rating (default 25.0).
            initial_sigma: Initial uncertainty (default 8.333).
            beta: Skill class width (defaults to initial_sigma/2).
            tau: Dynamics factor (defaults to initial_sigma/300).
        Returns:
            ScenarioList ordered best-to-worst according to TrueSkill ranking.
        """
        from .true_skill_algorithm import results_to_true_skill_ranked_list
        return results_to_true_skill_ranked_list(
            self,
            option_fields=option_fields,
            answer_field=answer_field,
            include_rank=include_rank,
            rank_field=rank_field,
            item_field=item_field,
            mu_field=mu_field,
            sigma_field=sigma_field,
            conservative_rating_field=conservative_rating_field,
            initial_mu=initial_mu,
            initial_sigma=initial_sigma,
            beta=beta,
            tau=tau
        )

    def chunk(
        self,
        field,
        num_words: Optional[int] = None,
        num_lines: Optional[int] = None,
        include_original=False,
        hash_original=False,
    ) -> "ScenarioList":
        """Chunk the scenarios based on a field.

        Example:

        >>> s = ScenarioList([Scenario({'text': 'The quick brown fox jumps over the lazy dog.'})])
        >>> s.chunk('text', num_words=3)
        ScenarioList([Scenario({'text': 'The quick brown', 'text_chunk': 0, 'text_char_count': 15, 'text_word_count': 3}), Scenario({'text': 'fox jumps over', 'text_chunk': 1, 'text_char_count': 14, 'text_word_count': 3}), Scenario({'text': 'the lazy dog.', 'text_chunk': 2, 'text_char_count': 13, 'text_word_count': 3})])
        """
        new_scenarios = []
        for scenario in self:
            replacement_scenarios = scenario.chunk(
                field,
                num_words=num_words,
                num_lines=num_lines,
                include_original=include_original,
                hash_original=hash_original,
            )
            new_scenarios.extend(replacement_scenarios)
        return ScenarioList(new_scenarios)

    def choose_k(self, k: int, order_matters: bool = False) -> "ScenarioList":
        """Create a ScenarioList of all choose-k selections with suffixed keys.

        The input must be a ScenarioList where each scenario has exactly one key, e.g.:
        ``ScenarioList.from_list('item', ['a', 'b', 'c'])``.

        Example:
            >>> s = ScenarioList.from_list('x', ['a', 'b', 'c'])
            >>> s.choose_k(2)
            ScenarioList([Scenario({'x_1': 'a', 'x_2': 'b'}), Scenario({'x_1': 'a', 'x_2': 'c'}), Scenario({'x_1': 'b', 'x_2': 'c'})])
            >>> s.choose_k(2, order_matters=True)  # doctest: +ELLIPSIS
            ScenarioList([...])

        Args:
            k: Number of items to choose for each scenario.
            order_matters: If True, use ordered selections (permutations). If False, use
                unordered selections (combinations).

        Returns:
            ScenarioList: A new list containing all generated scenarios.
        """
        return ScenarioList(list(self._iter_choose_k(k=k, order_matters=order_matters)))

    def _iter_choose_k(self, k: int, order_matters: bool = False):
        """Delegate generator for choose-k to the ScenarioCombinator module.

        Returns a generator yielding `Scenario` instances.
        """
        from importlib import import_module
        ScenarioCombinator = import_module(
            "edsl.scenarios.scenario_combinator"
        ).ScenarioCombinator
        return ScenarioCombinator.iter_choose_k(self, k=k, order_matters=order_matters)

    def to_agent_blueprint(
        self,
        *,
        seed: Optional[int] = None,
        cycle: bool = True,
        dimension_name_field: str = "dimension",
        dimension_values_field: str = "dimension_values",
        dimension_description_field: Optional[str] = None,
    ):
        """Create an AgentBlueprint from this ScenarioList.

        Args:
            seed: Optional seed for deterministic permutation order.
            cycle: Whether to continue cycling through permutations indefinitely.
            dimension_name_field: Field name to read the dimension name from.
            dimension_values_field: Field name to read the dimension values from.
            dimension_description_field: Optional field name for the dimension description.
        """
        from .agent_blueprint import AgentBlueprint

        return AgentBlueprint(
            self,
            seed=seed,
            cycle=cycle,
            dimension_name_field=dimension_name_field,
            dimension_values_field=dimension_values_field,
            dimension_description_field=dimension_description_field,
        )

    def collapse(
        self,
        field: str,
        separator: Optional[str] = None,
        prefix: str = "",
        postfix: str = "",
        add_count: bool = False,
    ) -> ScenarioList:
        """Collapse by grouping on all fields except the specified one.

        Delegates to `ScenarioListTransformer.collapse`.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.collapse(
            self,
            field,
            separator=separator,
            prefix=prefix,
            postfix=postfix,
            add_count=add_count,
        )

    def create_comparisons(
        self,
        bidirectional: bool = False,
        num_options: int = 2,
        option_prefix: str = "option_",
        use_alphabet: bool = False,
    ) -> ScenarioList:
        """Create a new ScenarioList with comparisons between scenarios.

        Delegates to `ScenarioListTransformer.create_comparisons`.
        """
        from .scenario_list_transformer import ScenarioListTransformer

        return ScenarioListTransformer.create_comparisons(
            self,
            bidirectional=bidirectional,
            num_options=num_options,
            option_prefix=option_prefix,
            use_alphabet=use_alphabet,
        )

    def replace_values(self, replacements: dict) -> "ScenarioList":
        """
        Create new scenarios with values replaced according to the provided replacement dictionary.

        Args:
            replacements (dict): Dictionary of values to replace {old_value: new_value}

        Returns:
            ScenarioList: A new ScenarioList with replaced values

        Examples:
            >>> scenarios = ScenarioList([
            ...     Scenario({'a': 'nan', 'b': 1}),
            ...     Scenario({'a': 2, 'b': 'nan'})
            ... ])
            >>> replaced = scenarios.replace_values({'nan': None})
            >>> print(replaced)
            ScenarioList([Scenario({'a': None, 'b': 1}), Scenario({'a': 2, 'b': None})])
            >>> # Original scenarios remain unchanged
            >>> print(scenarios)
            ScenarioList([Scenario({'a': 'nan', 'b': 1}), Scenario({'a': 2, 'b': 'nan'})])
        """
        new_sl = ScenarioList(data=[], codebook=self.codebook)
        for scenario in self:
            new_scenario = {}
            for key, value in scenario.items():
                if str(value) in replacements:
                    new_scenario[key] = replacements[str(value)]
                else:
                    new_scenario[key] = value
            new_sl.append(Scenario(new_scenario))
        return new_sl

    def fillna(self, value: Any = "", inplace: bool = False) -> "ScenarioList":
        """
        Fill None/NaN values in all scenarios with a specified value.
        
        This method is equivalent to pandas' df.fillna() functionality, allowing you to
        replace None, NaN, or other null-like values across all scenarios in the list.
        
        Args:
            value: The value to use for filling None/NaN values. Defaults to empty string "".
            inplace: If True, modify the original ScenarioList. If False (default), 
                    return a new ScenarioList with filled values.
        
        Returns:
            ScenarioList: A new ScenarioList with filled values, or self if inplace=True
        
        Examples:
            >>> scenarios = ScenarioList([
            ...     Scenario({'a': None, 'b': 1, 'c': 'hello'}),
            ...     Scenario({'a': 2, 'b': None, 'c': None}),
            ...     Scenario({'a': None, 'b': 3, 'c': 'world'})
            ... ])
            >>> # Fill None values with empty string (default)
            >>> filled = scenarios.fillna()
            >>> print(filled)
            ScenarioList([Scenario({'a': '', 'b': 1, 'c': 'hello'}), Scenario({'a': 2, 'b': '', 'c': ''}), Scenario({'a': '', 'b': 3, 'c': 'world'})])
            >>> # Fill with custom value
            >>> filled_custom = scenarios.fillna(value="N/A")
            >>> print(filled_custom)
            ScenarioList([Scenario({'a': 'N/A', 'b': 1, 'c': 'hello'}), Scenario({'a': 2, 'b': 'N/A', 'c': 'N/A'}), Scenario({'a': 'N/A', 'b': 3, 'c': 'world'})])
            >>> # Original scenarios remain unchanged
            >>> print(scenarios)
            ScenarioList([Scenario({'a': None, 'b': 1, 'c': 'hello'}), Scenario({'a': 2, 'b': None, 'c': None}), Scenario({'a': None, 'b': 3, 'c': 'world'})])
            >>> # Modify in place
            >>> _ = scenarios.fillna(value="MISSING", inplace=True)
            >>> print(scenarios)
            ScenarioList([Scenario({'a': 'MISSING', 'b': 1, 'c': 'hello'}), Scenario({'a': 2, 'b': 'MISSING', 'c': 'MISSING'}), Scenario({'a': 'MISSING', 'b': 3, 'c': 'world'})])
        """
        def is_null(val):
            """Check if a value is considered null/None."""
            return val is None or (hasattr(val, '__str__') and str(val).lower() in ['nan', 'none', 'null', ''])
        
        if inplace:
            # Modify the original scenarios
            for scenario in self:
                for key in scenario:
                    if is_null(scenario[key]):
                        scenario[key] = value
            return self
        else:
            # Create new scenarios with filled values
            new_sl = ScenarioList(data=[], codebook=self.codebook)
            for scenario in self:
                new_scenario = {}
                for key, val in scenario.items():
                    if is_null(val):
                        new_scenario[key] = value
                    else:
                        new_scenario[key] = val
                new_sl.append(Scenario(new_scenario))
            return new_sl


    def create_conjoint_comparisons(
        self,
        attribute_field: str = 'attribute',
        levels_field: str = 'levels',
        count: int = 1,
        random_seed: Optional[int] = None
    ) -> "ScenarioList":
        """
        Generate random product profiles for conjoint analysis from attribute definitions.

        This method uses the current ScenarioList (which should contain attribute definitions)
        to create random product profiles by sampling from the attribute levels. Each scenario
        in the current list should represent one attribute with its possible levels.

        Args:
            attribute_field: Field name containing the attribute names (default: 'attribute')
            levels_field: Field name containing the list of levels (default: 'levels')
            count: Number of product profiles to generate (default: 1)
            random_seed: Optional seed for reproducible random sampling

        Returns:
            ScenarioList containing randomly generated product profiles

        Example:
            >>> from edsl.scenarios import ScenarioList, Scenario
            >>> # Create attribute definitions
            >>> attributes = ScenarioList([
            ...     Scenario({'attribute': 'price', 'levels': ['$100', '$200', '$300']}),
            ...     Scenario({'attribute': 'color', 'levels': ['Red', 'Blue', 'Green']}),
            ...     Scenario({'attribute': 'size', 'levels': ['Small', 'Medium', 'Large']})
            ... ])
            >>> # Generate conjoint profiles
            >>> profiles = attributes.create_conjoint_comparisons(count=3, random_seed=42)
            >>> len(profiles)
            3
            >>> # Each profile will have price, color, and size with random values

        Raises:
            ScenarioError: If the current ScenarioList doesn't have the required fields
            ValueError: If count is not positive
        """
        from .conjoint_profile_generator import ConjointProfileGenerator

        if count <= 0:
            raise ValueError("Count must be positive")

        # Create the generator with the current ScenarioList
        generator = ConjointProfileGenerator(
            self,
            attribute_field=attribute_field,
            levels_field=levels_field,
            random_seed=random_seed
        )

        # Generate the requested number of profiles
        return generator.generate_batch(count)

    @classmethod
    def from_source(cls, source_type: str, *args, **kwargs) -> "ScenarioList":
        """
        Create a ScenarioList from a specified source type.

        This method serves as the main entry point for creating ScenarioList objects,
        providing a unified interface for various data sources.

        Args:
            source_type: The type of source to create a ScenarioList from.
                         Valid values include: 'urls', 'directory', 'csv', 'tsv',
                         'excel', 'pdf', 'pdf_to_image', and others.
            *args: Positional arguments to pass to the source-specific method.
            **kwargs: Keyword arguments to pass to the source-specific method.

        Returns:
            A ScenarioList object created from the specified source.

        Examples:
            >>> # This is a simplified example for doctest
            >>> # In real usage, you would provide a path to your CSV file:
            >>> # sl_csv = ScenarioList.from_source('csv', 'your_data.csv')
            >>> # Or use other source types like 'directory', 'excel', etc.
            >>> # Examples of other source types:
            >>> # sl_dir = ScenarioList.from_source('directory', '/path/to/files')
        """
        from .scenario_source import ScenarioSource

        return ScenarioSource.from_source(source_type, *args, **kwargs)

if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
