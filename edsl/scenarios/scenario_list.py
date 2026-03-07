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

Doctest (chainable conditionals design)
    >>> from edsl.scenarios import Scenario, ScenarioList
    >>> sl = ScenarioList([Scenario({"a": "x"}), Scenario({"a": "y"})])
    >>> # If True, apply then-branch; else apply else-branch
    >>> out_true = (
    ...     sl.when(True)            # start recording (active branch: then)
    ...       .then()                # explicitly set then-branch (optional)
    ...         .add_value("flag", 1)
    ...       .else_()               # switch to else branch
    ...         .add_value("flag", 0)
    ...       .end()                 # evaluate and apply
    ... )
    >>> set(s["flag"] for s in out_true) == {1}
    True
    >>> out_false = (
    ...     sl.when(False)
    ...       .then()
    ...         .add_value("flag", 1)
    ...       .else_()
    ...         .add_value("flag", 0)
    ...       .end()
    ... )
    >>> set(s["flag"] for s in out_false) == {0}
    True
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
from collections.abc import Iterable, MutableSequence
from functools import wraps
import json


# Import for refactoring to Source classes

from ..dataset.display.table_display import SUPPORTED_TABLE_FORMATS

try:
    from typing import TypeAlias
except ImportError:
    from typing_extensions import TypeAlias


if TYPE_CHECKING:
    from ..dataset import Dataset
    from ..jobs import Jobs, Job
    from ..surveys import Survey
    from ..questions import QuestionBase, Question
    from ..agents import Agent
    from typing import Sequence



from ..base import Base
from ..utilities import (
    remove_edsl_version,
    sanitize_string,
    is_valid_variable_name,
    dict_hash,
    memory_profile,
    list_split,
)
from ..utilities.display_utils import smart_truncate
from ..dataset import ScenarioListOperationsMixin

from .exceptions import ScenarioError
from .scenario import Scenario
from .scenario_list_transformer import ScenarioListTransformer
from .scenario_list_joiner import ScenarioListJoiner


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

    def __init__(
        self,
        data: Optional[list | str] = None,
        codebook: Optional[dict[str, str]] = None,
        data_class: Optional[type] = data_class,
    ):
        """Initialize a new ScenarioList with optional data and codebook."""
        self._data_class = data_class
        self.data = self._data_class([])
        if data is not None and isinstance(data, str):
            sl = ScenarioList.pull(data)
            if codebook is not None:
                raise ValueError(
                    "Codebook cannot be provided when pulling from a remote source"
                )
            codebook = sl.codebook
            super().__init__()
            for item in sl.data:
                self.data.append(item)
        else:
            for item in data or []:
                self.data.append(item)
        self.codebook = codebook or {}
        self._transformer = ScenarioListTransformer(self)
        self._joiner = ScenarioListJoiner(self)
        # Conditional builder state (ephemeral)
        self._cond_active: bool = False
        self._cond_branch: Optional[str] = None
        self._cond_condition: Any = None
        self._cond_ops: dict[str, list[tuple[str, tuple, dict]]] = {
            "then": [],
            "else": [],
        }

    # Intercept method access during conditional recording
    def __getattribute__(self, name: str):  # noqa: D401
        # Fast path for core attributes to avoid recursion
        if name in {
            "_cond_active",
            "_cond_branch",
            "_cond_condition",
            "_cond_ops",
            "when",
            "then",
            "else_",
            "otherwise",
            "end",
            "cancel",
        }:
            return object.__getattribute__(self, name)

        attr = object.__getattribute__(self, name)

        # Only intercept when actively recording and the attribute is a public bound method to record
        try:
            is_active = object.__getattribute__(self, "_cond_active")
            _current_branch = object.__getattribute__(self, "_cond_branch")
        except Exception:
            return attr

        if not is_active:
            return attr

        # Do not record private/dunder or builder controls
        if name.startswith("_"):
            return attr

        builder_exclusions = {
            "when",
            "then",
            "else_",
            "otherwise",
            "end",
            "cancel",
        }

        if name in builder_exclusions:
            return attr

        # Only wrap callables (methods)
        import inspect as _inspect

        if callable(attr) and _inspect.ismethod(attr):

            def recorder(*args, **kwargs):
                ops = object.__getattribute__(self, "_cond_ops")
                branch = object.__getattribute__(self, "_cond_branch")
                ops[branch].append((name, args, kwargs))
                return self

            return recorder

        return attr

    # ---- Chainable conditional builder API ----
    def when(self, condition: Any) -> "ScenarioList":
        """Begin a conditional chain on this ScenarioList.

        Records subsequent method calls until `end()`.
        """
        if self._cond_active:
            raise ScenarioError(
                "Nested when() is not supported. Call end() or cancel() first."
            )
        self._cond_active = True
        self._cond_branch = "then"
        self._cond_condition = condition
        self._cond_ops = {"then": [], "else": []}
        return self

    def then(self) -> "ScenarioList":
        if not self._cond_active:
            raise ScenarioError("then() called without an active when().")
        self._cond_branch = "then"
        return self

    def else_(self) -> "ScenarioList":
        if not self._cond_active:
            raise ScenarioError("else_() called without an active when().")
        self._cond_branch = "else"
        return self

    def otherwise(self) -> "ScenarioList":
        return self.else_()

    def cancel(self) -> "ScenarioList":
        """Abort the current conditional recording and reset state."""
        self._cond_active = False
        self._cond_branch = None
        self._cond_condition = None
        self._cond_ops = {"then": [], "else": []}
        return self

    @staticmethod
    def _cond_to_bool(val: Any) -> bool:
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            lowered = val.strip().lower()
            if lowered in {"", "false", "no", "0", "off", "n"}:
                return False
            if lowered in {"true", "yes", "1", "on", "y"}:
                return True
            return True
        return bool(val)

    def end(self) -> "ScenarioList":
        """End the conditional chain, apply recorded ops for the chosen branch, and return a ScenarioList."""
        if not self._cond_active:
            raise ScenarioError("end() called without an active when().")

        chosen_branch = "then" if self._cond_to_bool(self._cond_condition) else "else"
        ops_to_apply = self._cond_ops.get(chosen_branch, [])

        sl: "ScenarioList" = self
        for method_name, args, kwargs in ops_to_apply:
            method = object.__getattribute__(sl, method_name)
            result = method(*args, **kwargs)
            # Preserve chaining semantics: some methods return None/inplace
            sl = result if isinstance(result, ScenarioList) else sl

        # Reset state
        self._cond_active = False
        self._cond_branch = None
        self._cond_condition = None
        self._cond_ops = {"then": [], "else": []}

        return sl

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

    def slice(self, slice_str: str) -> ScenarioList:
        """Get a slice of the ScenarioList using string notation.

        Args:
            slice_str: String slice notation like '1:', '2:5', ':3', '1:5:2'

        Returns:
            A new ScenarioList containing the sliced scenarios.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList.from_list("a", [1, 2, 3, 4, 5])
            >>> sl.slice('1:')  # Everything from index 1 onwards
            ScenarioList([Scenario({'a': 2}), Scenario({'a': 3}), Scenario({'a': 4}), Scenario({'a': 5})])
            >>> sl.slice(':3')  # First 3 elements
            ScenarioList([Scenario({'a': 1}), Scenario({'a': 2}), Scenario({'a': 3})])
            >>> sl.slice('2:4')  # Elements from index 2 to 4 (exclusive)
            ScenarioList([Scenario({'a': 3}), Scenario({'a': 4})])
            >>> sl.slice('1:5:2')  # Every 2nd element from index 1 to 5
            ScenarioList([Scenario({'a': 2}), Scenario({'a': 4})])
        """
        # Parse the slice string
        parts = slice_str.split(":")
        if len(parts) == 1:
            # Single index
            start = int(parts[0]) if parts[0] else 0
            stop = start + 1
            step = 1
        elif len(parts) == 2:
            # start:stop
            start = int(parts[0]) if parts[0] else None
            stop = int(parts[1]) if parts[1] else None
            step = 1
        elif len(parts) == 3:
            # start:stop:step
            start = int(parts[0]) if parts[0] else None
            stop = int(parts[1]) if parts[1] else None
            step = int(parts[2]) if parts[2] else 1
        else:
            raise ValueError(f"Invalid slice string: {slice_str}")

        # Create slice object and use existing __getitem__ method
        slice_obj = slice(start, stop, step)
        return self[slice_obj]

    def sum(self, field: str) -> int:
        """Sum the values of a field across all scenarios."""
        return sum(scenario[field] for scenario in self)

    @wraps(ScenarioListTransformer.unique)
    def unique(self) -> ScenarioList:
        return self._transformer.unique()

    @wraps(ScenarioListTransformer.uniquify)
    def uniquify(self, field: str) -> "ScenarioList":
        return self._transformer.uniquify(field)

    @wraps(ScenarioListTransformer.to_agent_traits)
    def to_agent_traits(self, agent_name: Optional[str] = None) -> "Agent":
        return self._transformer.to_agent_traits(agent_name)

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

    @wraps(ScenarioListTransformer.unpivot)
    def unpivot(
        self,
        id_vars: Optional[List[str]] = None,
        value_vars: Optional[List[str]] = None,
    ) -> ScenarioList:
        return self._transformer.unpivot(id_vars, value_vars)

    @wraps(ScenarioListTransformer.apply)
    def apply(
        self, func: Callable, field: str, new_name: Optional[str], replace: bool = False
    ) -> ScenarioList:
        return self._transformer.apply(func, field, new_name, replace)

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

    def string_cat_if(
        self,
        key: str,
        addend: str,
        condition: Any,
        position: str = "suffix",
        inplace: bool = False,
    ) -> ScenarioList:
        """Conditionally concatenate a string to a field across all Scenarios.

        The condition may be a boolean or a string such as 'yes'/'no', 'true'/'false', '1'/'0'.
        Non-empty strings are coerced using a permissive truthy mapping.
        """

        def _to_bool(val: Any) -> bool:
            if isinstance(val, bool):
                return val
            if val is None:
                return False
            if isinstance(val, (int, float)):
                return bool(val)
            if isinstance(val, str):
                lowered = val.strip().lower()
                if lowered in {"", "false", "no", "0", "off", "n"}:
                    return False
                if lowered in {"true", "yes", "1", "on", "y"}:
                    return True
                # Fallback: any other non-empty string is considered True
                return True
            return bool(val)

        if not _to_bool(condition):
            return self if inplace else self.duplicate()
        return self.string_cat(key, addend, position=position, inplace=inplace)

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
            formatted_value = ", ".join(
                [f"{k}: {v}" for k, v in remaining_values.items()]
            )

            # Add to the combined dictionary
            combined_dict[new_key] = formatted_value

        # Return a single Scenario with all the key/value pairs
        return Scenario(combined_dict)

    # @classmethod
    # def from_prompt(
    #     self,
    #     description: str,
    #     name: Optional[str] = "item",
    #     target_number: int = 10,
    #     verbose=False,
    # ):
    #     from ..questions.question_list import QuestionList

    #     q = QuestionList(
    #         question_name=name,
    #         question_text=description
    #         + f"\n Please try to return {target_number} examples.",
    #     )
    #     results = q.run(verbose=verbose)
    #     return results.select(name).to_scenario_list().expand(name)

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

    # @classmethod
    # def from_search_terms(cls, search_terms: List[str]) -> ScenarioList:
    #     """Create a ScenarioList from a list of search terms, using Wikipedia.

    #     Args:
    #         search_terms: A list of search terms.
    #     """
    #     from ..utilities.wikipedia import fetch_wikipedia_content

    #     results = fetch_wikipedia_content(search_terms)
    #     return cls([Scenario(result) for result in results])

    # def augment_with_wikipedia(
    #     self,
    #     search_key: str,
    #     content_only: bool = True,
    #     key_name: str = "wikipedia_content",
    # ) -> ScenarioList:
    #     """Augment the ScenarioList with Wikipedia content."""
    #     search_terms = self.select(search_key).to_list()
    #     wikipedia_results = ScenarioList.from_search_terms(search_terms)
    #     new_sl = ScenarioList(data=[], codebook=self.codebook)
    #     for scenario, wikipedia_result in zip(self, wikipedia_results):
    #         if content_only:
    #             scenario[key_name] = wikipedia_result["content"]
    #             new_sl.append(scenario)
    #         else:
    #             scenario[key_name] = wikipedia_result
    #             new_sl.append(scenario)
    #     return new_sl

    @wraps(ScenarioListTransformer.pivot)
    def pivot(
        self,
        id_vars: List[str] = None,
        var_name="variable",
        value_name="value",
    ) -> ScenarioList:
        return self._transformer.pivot(id_vars, var_name, value_name)

    @wraps(ScenarioListTransformer.group_by)
    def group_by(
        self, id_vars: List[str], variables: List[str], func: Callable
    ) -> ScenarioList:
        return self._transformer.group_by(id_vars, variables, func)

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

    def to_scenario_list(self) -> "ScenarioList":
        """Convert the ScenarioList to a ScenarioList.

        This is useful when the user calls to_scenario_list on an object that is already a ScenarioList but they don't know it.
        """
        return self

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

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the ScenarioList.

        This representation can be used with eval() to recreate the ScenarioList object.
        Used primarily for doctests and debugging.
        """
        return f"ScenarioList([{', '.join([x._eval_repr_() for x in self.data])}])"

    # @classmethod
    # def from_vibes(cls, description: str) -> ScenarioList:
    #     """Create a ScenarioList from a vibe description.

    #     Args:
    #         description: A description of the vibe.
    #     """
    #     from edsl.dataset.vibes.scenario_generator import ScenarioGenerator

    #     gen = ScenarioGenerator(model="gpt-4o", temperature=0.7)
    #     result = gen.generate_scenarios(description)
    #     return cls([Scenario(scenario) for scenario in result["scenarios"]])

    def _summary_repr(self, MAX_SCENARIOS: int = 10, MAX_FIELDS: int = 500) -> str:
        """Generate a summary representation of the ScenarioList with Rich formatting.

        Args:
            MAX_SCENARIOS: Maximum number of scenarios to show (default: 10)
            MAX_FIELDS: Maximum number of fields to show per scenario (default: 500)
        """
        from rich.console import Console
        from rich.text import Text
        import io
        import shutil
        from edsl.config import RICH_STYLES

        # Get terminal width
        terminal_width = shutil.get_terminal_size().columns

        # Build the Rich text
        output = Text()
        output.append("ScenarioList(\n", style=RICH_STYLES["primary"])
        output.append(f"    num_scenarios={len(self)},\n", style=RICH_STYLES["default"])
        output.append("    scenarios=[\n", style=RICH_STYLES["default"])

        # Show the first MAX_SCENARIOS scenarios
        num_to_show = min(MAX_SCENARIOS, len(self))
        for i, scenario in enumerate(self.data[:num_to_show]):
            # Get scenario representation with limited fields
            scenario_data = dict(list(scenario.items())[:MAX_FIELDS])

            # Check if we need to indicate truncation
            num_fields = len(scenario)
            was_truncated = num_fields > MAX_FIELDS

            # Build scenario repr with indentation
            output.append("        Scenario(\n", style=RICH_STYLES["primary"])
            output.append(
                f"            num_keys={num_fields},\n", style=RICH_STYLES["default"]
            )
            output.append("            data={\n", style=RICH_STYLES["default"])

            # Show fields
            for key, value in scenario_data.items():
                # Format the value with smart truncation if needed
                max_value_length = max(terminal_width - 30, 50)
                value_repr = repr(value)
                if len(value_repr) > max_value_length:
                    value_repr = smart_truncate(value_repr, max_value_length)

                output.append("                ", style=RICH_STYLES["default"])
                output.append(f"'{key}'", style=RICH_STYLES["key"])
                output.append(f": {value_repr},\n", style=RICH_STYLES["default"])

            if was_truncated:
                output.append(
                    f"                ... ({num_fields - MAX_FIELDS} more fields)\n",
                    style=RICH_STYLES["dim"],
                )

            output.append("            }\n", style=RICH_STYLES["default"])
            output.append("        )", style=RICH_STYLES["primary"])

            # Add comma and newline unless it's the last one
            if i < num_to_show - 1:
                output.append(",\n", style=RICH_STYLES["default"])
            else:
                output.append("\n", style=RICH_STYLES["default"])

        # Add ellipsis if there are more scenarios
        if len(self) > MAX_SCENARIOS:
            output.append(
                f"        ... ({len(self) - MAX_SCENARIOS} more scenarios)\n",
                style=RICH_STYLES["dim"],
            )

        output.append("    ]\n", style=RICH_STYLES["default"])
        output.append(")", style=RICH_STYLES["primary"])

        # Render to string
        console = Console(file=io.StringIO(), force_terminal=True, width=terminal_width)
        console.print(output, end="")
        return console.file.getvalue()

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

    @wraps(ScenarioListTransformer.shuffle)
    def shuffle(self, seed: Optional[str] = None) -> ScenarioList:
        return self._transformer.shuffle(seed)

    def full_replace(self, other: ScenarioList, inplace: bool = False) -> ScenarioList:
        """Replace the ScenarioList with another ScenarioList."""
        if inplace:
            self.data = other.data
            self.codebook = other.codebook
            return self
        else:
            return ScenarioList(data=other.data, codebook=other.codebook)

    @wraps(ScenarioListTransformer.sample)
    def sample(self, n: int, seed: Optional[str] = None) -> ScenarioList:
        return self._transformer.sample(n, seed)

    @wraps(ScenarioListTransformer.split)
    def split(
        self, frac_left: float = 0.5, seed: Optional[int] = None
    ) -> tuple[ScenarioList, ScenarioList]:
        return self._transformer.split(frac_left, seed)

#
    @wraps(ScenarioListTransformer.expand)
    def expand(self, *expand_fields: str, number_field: bool = False) -> ScenarioList:
        return self._transformer.expand(*expand_fields, number_field=number_field)

    @wraps(ScenarioListTransformer._concatenate)
    def _concatenate(
        self,
        fields: List[str],
        output_type: str = "string",
        separator: str = ";",
        prefix: str = "",
        postfix: str = "",
        new_field_name: Optional[str] = None,
    ) -> ScenarioList:
        return self._transformer._concatenate(
            fields,
            output_type=output_type,
            separator=separator,
            prefix=prefix,
            postfix=postfix,
            new_field_name=new_field_name,
        )

    @wraps(ScenarioListTransformer.concatenate)
    def concatenate(
        self,
        fields: List[str],
        separator: str = ";",
        prefix: str = "",
        postfix: str = "",
        new_field_name: Optional[str] = None,
    ) -> ScenarioList:
        return self._transformer.concatenate(
            fields,
            separator=separator,
            prefix=prefix,
            postfix=postfix,
            new_field_name=new_field_name,
        )

    @wraps(ScenarioListTransformer.concatenate_to_list)
    def concatenate_to_list(
        self,
        fields: List[str],
        prefix: str = "",
        postfix: str = "",
        new_field_name: Optional[str] = None,
    ) -> ScenarioList:
        return self._transformer.concatenate_to_list(
            fields,
            prefix=prefix,
            postfix=postfix,
            new_field_name=new_field_name,
        )

    @wraps(ScenarioListTransformer.concatenate_to_set)
    def concatenate_to_set(
        self,
        fields: List[str],
        prefix: str = "",
        postfix: str = "",
        new_field_name: Optional[str] = None,
    ) -> ScenarioList:
        return self._transformer.concatenate_to_set(
            fields,
            prefix=prefix,
            postfix=postfix,
            new_field_name=new_field_name,
        )

    @wraps(ScenarioListTransformer.unpack_dict)
    def unpack_dict(
        self, field: str, prefix: Optional[str] = None, drop_field: bool = False
    ) -> ScenarioList:
        return self._transformer.unpack_dict(field, prefix, drop_field)

    @wraps(ScenarioListTransformer.transform)
    def transform(
        self, field: str, func: Callable, new_name: Optional[str] = None
    ) -> ScenarioList:
        return self._transformer.transform(field, func, new_name)

    @wraps(ScenarioListTransformer.mutate)
    def mutate(
        self, new_var_string: str, functions_dict: Optional[dict[str, Callable]] = None
    ) -> ScenarioList:
        return self._transformer.mutate(new_var_string, functions_dict)

    @wraps(ScenarioListTransformer.order_by)
    def order_by(self, *fields: str, reverse: bool = False) -> ScenarioList:
        return self._transformer.order_by(list(fields), reverse)

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
    @wraps(ScenarioListTransformer.filter)
    def filter(self, expression: str) -> ScenarioList:
        return self._transformer.filter(expression)

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

    @wraps(ScenarioListTransformer.select)
    def select(self, *fields: str) -> ScenarioList:
        return self._transformer.select(*fields)

    @wraps(ScenarioListTransformer.drop)
    def drop(self, *fields: str) -> ScenarioList:
        return self._transformer.drop(*fields)

    @wraps(ScenarioListTransformer.keep)
    def keep(self, *fields: str) -> ScenarioList:
        return self._transformer.keep(*fields)

    @wraps(ScenarioListTransformer.numberify)
    def numberify(self) -> ScenarioList:
        return self._transformer.numberify()

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

    def table(
        self,
        *fields: str,
        tablefmt: Optional[TableFormat] = "rich",
        pretty_labels: Optional[dict[str, str]] = None,
    ) -> str:
        """Return the ScenarioList as a table."""

        if tablefmt is not None and tablefmt not in SUPPORTED_TABLE_FORMATS:
            raise ValueError(
                f"Invalid table format: {tablefmt}",
                f"Valid formats are: {list(SUPPORTED_TABLE_FORMATS)}",
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

    @wraps(ScenarioListTransformer.reorder_keys)
    def reorder_keys(self, new_order: List[str]) -> ScenarioList:
        return self._transformer.reorder_keys(new_order)

    def to_survey(self) -> "Survey":
        from ..questions import QuestionBase
        from ..surveys import Survey

        s = Survey()
        for index, scenario in enumerate(self):
            d = scenario.to_dict(add_edsl_version=False)
            if d["question_type"] == "free_text":
                if "question_options" in d:
                    _ = d.pop("question_options")
            if "question_name" not in d or d["question_name"] is None:
                d["question_name"] = f"question_{index}"

            if d["question_type"] is None:
                d["question_type"] = "free_text"
                d["question_options"] = None

            if "weight" in d:
                d["weight"] = float(d["weight"])

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

    @wraps(ScenarioListTransformer.to_scenario_of_lists)
    def to_scenario_of_lists(self) -> "Scenario":
        return self._transformer.to_scenario_of_lists()

    @wraps(ScenarioListTransformer.unpack)
    def unpack(
        self, field: str, new_names: Optional[List[str]] = None, keep_original=True
    ) -> ScenarioList:
        return self._transformer.unpack(field, new_names, keep_original)

    @wraps(ScenarioListTransformer.add_list)
    def add_list(self, name: str, values: List[Any]) -> ScenarioList:
        return self._transformer.add_list(name, values)

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

    @wraps(ScenarioListTransformer.add_value)
    def add_value(self, name: str, value: Any) -> ScenarioList:
        return self._transformer.add_value(name, value)

    @wraps(ScenarioListTransformer.tack_on)
    def tack_on(self, replacements: dict[str, Any], index: int = -1) -> "ScenarioList":
        return self._transformer.tack_on(replacements, index)

    @wraps(ScenarioListTransformer.rename)
    def rename(self, replacement_dict: dict) -> ScenarioList:
        return self._transformer.rename(replacement_dict)

    @wraps(ScenarioListTransformer.snakify)
    def snakify(self) -> ScenarioList:
        return self._transformer.snakify()

    @wraps(ScenarioListTransformer.replace_names)
    def replace_names(self, new_names: list) -> ScenarioList:
        return self._transformer.replace_names(new_names)

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

    @wraps(ScenarioListJoiner.left_join)
    def left_join(self, other: ScenarioList, by: Union[str, list[str]]) -> ScenarioList:
        return self._joiner.left_join(other, by)

    @wraps(ScenarioListJoiner.inner_join)
    def inner_join(
        self, other: ScenarioList, by: Union[str, list[str]]
    ) -> ScenarioList:
        return self._joiner.inner_join(other, by)

    @wraps(ScenarioListJoiner.right_join)
    def right_join(
        self, other: ScenarioList, by: Union[str, list[str]]
    ) -> ScenarioList:
        return self._joiner.right_join(other, by)

    def to_dict(self, sort: bool = False, add_edsl_version: bool = True) -> dict:
        """
        >>> s = ScenarioList([Scenario({'food': 'wood chips'}), Scenario({'food': 'wood-fired pizza'})])
        >>> s.to_dict()  # doctest: +ELLIPSIS
        {'scenarios': [{'food': 'wood chips', 'edsl_version': '...', 'edsl_class_name': 'Scenario'}, {'food': 'wood-fired pizza', 'edsl_version': '...', 'edsl_class_name': 'Scenario'}], 'edsl_version': '...', 'edsl_class_name': 'ScenarioList'}

        >>> s = ScenarioList([Scenario({'food': 'wood chips'})], codebook={'food': 'description'})
        >>> d = s.to_dict()
        >>> 'codebook' in d
        True
        >>> d['codebook'] == {'food': 'description'}
        True

        >>> # To exclude edsl_version and edsl_class_name, explicitly set add_edsl_version=False
        >>> s.to_dict(add_edsl_version=False)
        {'scenarios': [{'food': 'wood chips'}], 'codebook': {'food': 'description'}}

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
    def from_list_of_dicts(cls, data: list[dict]) -> ScenarioList:
        """Create a `ScenarioList` from a list of dictionaries.

        >>> data = [{'name': 'Alice'}, {'name': 'Bob'}]
        >>> ScenarioList.from_list_of_dicts(data)
        ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
        """
        return cls([Scenario(s) for s in data])

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

    @wraps(ScenarioListTransformer.chunk)
    def chunk(
        self,
        field,
        num_words: Optional[int] = None,
        num_lines: Optional[int] = None,
        include_original=False,
        hash_original=False,
    ) -> "ScenarioList":
        return self._transformer.chunk(
            field,
            num_words=num_words,
            num_lines=num_lines,
            include_original=include_original,
            hash_original=hash_original,
        )

    @wraps(ScenarioListTransformer.choose_k)
    def choose_k(self, k: int, order_matters: bool = False) -> "ScenarioList":
        return self._transformer.choose_k(k, order_matters)

    def to_agent_blueprint(
        self,
        *,
        seed: Optional[int] = None,
        cycle: bool = True,
        dimension_name_field: str = "dimension",
        dimension_values_field: str = "dimension_values",
        dimension_description_field: Optional[str] = None,
        dimension_probs_field: Optional[str] = None,
    ):
        """Create an AgentBlueprint from this ScenarioList.

        Args:
            seed: Optional seed for deterministic permutation order.
            cycle: Whether to continue cycling through permutations indefinitely.
            dimension_name_field: Field name to read the dimension name from.
            dimension_values_field: Field name to read the dimension values from.
            dimension_description_field: Optional field name for the dimension description.
            dimension_probs_field: Optional field name for probability weights.
        """
        from .agent_blueprint import AgentBlueprint

        return AgentBlueprint.from_scenario_list(
            self,
            seed=seed,
            cycle=cycle,
            dimension_name_field=dimension_name_field,
            dimension_values_field=dimension_values_field,
            dimension_description_field=dimension_description_field,
            dimension_probs_field=dimension_probs_field,
        )

    @wraps(ScenarioListTransformer.collapse)
    def collapse(
        self,
        field: str,
        separator: Optional[str] = None,
        prefix: str = "",
        postfix: str = "",
        add_count: bool = False,
    ) -> ScenarioList:
        return self._transformer.collapse(
            field,
            separator=separator,
            prefix=prefix,
            postfix=postfix,
            add_count=add_count,
        )

    @wraps(ScenarioListTransformer.create_comparisons)
    def create_comparisons(
        self,
        bidirectional: bool = False,
        num_options: int = 2,
        option_prefix: str = "option_",
        use_alphabet: bool = False,
    ) -> ScenarioList:
        return self._transformer.create_comparisons(
            bidirectional=bidirectional,
            num_options=num_options,
            option_prefix=option_prefix,
            use_alphabet=use_alphabet,
        )

    @wraps(ScenarioListTransformer.replace_values)
    def replace_values(self, replacements: dict) -> "ScenarioList":
        return self._transformer.replace_values(replacements)

    @wraps(ScenarioListTransformer.fillna)
    def fillna(self, value: Any = "", inplace: bool = False) -> "ScenarioList":
        return self._transformer.fillna(value, inplace)

    @wraps(ScenarioListTransformer.filter_na)
    def filter_na(self, fields: Union[str, List[str]] = "*") -> "ScenarioList":
        return self._transformer.filter_na(fields)

    @classmethod
    def from_source(
        cls, source_type_or_data: Any, *args, snakify: bool = True, **kwargs
    ) -> "ScenarioList":
        """
        Create a ScenarioList from a specified source type or infer it automatically.

        This method serves as the main entry point for creating ScenarioList objects,
        providing a unified interface for various data sources. By default, column names
        are automatically converted to valid Python identifiers (snake_case).

        **Two modes of operation:**

        1. **Explicit source type** (2+ arguments): Specify the source type explicitly
           Example: ScenarioList.from_source('csv', 'data.csv')

        2. **Auto-detect source** (1 argument): Pass only the data and let it infer the type
           Example: ScenarioList.from_source('data.csv')

        Args:
            source_type_or_data: Either:
                - A string specifying the source type ('csv', 'excel', 'pdf', etc.)
                  when using explicit mode with additional args
                - The actual data source (file path, URL, dict, DataFrame, etc.)
                  when using auto-detect mode
            *args: Positional arguments to pass to the source-specific method
                   (only used in explicit mode).
            snakify: If True (default), automatically convert all scenario keys to
                     valid Python identifiers (snake_case). Set to False to preserve
                     original column names.
            **kwargs: Keyword arguments to pass to the source-specific method.

        Returns:
            A ScenarioList object created from the specified source, with snakified keys
            if snakify=True.

        Examples:
            >>> # Explicit source type (original behavior)
            >>> # sl = ScenarioList.from_source('csv', 'data.csv')

            >>> # Auto-detect source type (new behavior)
            >>> sl = ScenarioList.from_source({'name': ['Alice', 'Bob'], 'age': [25, 30]})
            Detected source type: dictionary

            >>> # Auto-detect from file with snakify
            >>> # sl = ScenarioList.from_source('data.csv')  # Keys will be snakified
            >>> # Detected source type: CSV file at data.csv

            >>> # Preserve original column names
            >>> sl = ScenarioList.from_source({'First Name': ['Alice']}, snakify=False)
            Detected source type: dictionary
            >>> 'First Name' in sl[0]
            True
        """
        from .scenario_source import ScenarioSource
        from .scenario_source_inferrer import ScenarioSourceInferrer

        # If no additional positional args, assume user wants auto-detection
        if len(args) == 0:
            # Auto-detect mode: source_type_or_data is actually the data
            scenario_list = ScenarioSourceInferrer.infer_and_create(
                source_type_or_data, verbose=True, **kwargs
            )
        else:
            # Explicit mode: source_type_or_data is the source type string
            scenario_list = ScenarioSource.from_source(
                source_type_or_data, *args, **kwargs
            )

        # Apply snakify transformation if requested
        if snakify:
            scenario_list = scenario_list.snakify()

        return scenario_list


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
