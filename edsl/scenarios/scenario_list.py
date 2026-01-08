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
import json
import pickle


# Import for refactoring to Source classes

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
    from ..agents import Agent
    from typing import Sequence
    from .scenarioml.prediction import Prediction


from ..base import Base
from ..utilities import (
    remove_edsl_version,
    sanitize_string,
    is_valid_variable_name,
    dict_hash,
    list_split,
)
from ..display.utils import smart_truncate
from ..dataset import ScenarioListOperationsMixin
from .exceptions import ScenarioError
from .scenario import Scenario

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

from .scenario_list_likely_remove import ScenarioListLikelyRemove
from .scenario_list_to import ScenarioListTo
from .scenario_list_joins import ScenarioListJoin

from edsl.versioning import GitMixin
from edsl.versioning import event

# Import event-sourcing infrastructure from edsl.store
from edsl.store import (
    Codec,
    Store,
    Event,
    AppendRowEvent,
    UpdateRowEvent,
    RemoveRowsEvent,
    InsertRowEvent,
    UpdateEntryFieldEvent,
    SetMetaEvent,
    UpdateMetaEvent,
    RemoveMetaKeyEvent,
    ClearEntriesEvent,
    AddFieldToAllEntriesEvent,
    AddFieldByIndexEvent,
    ReplaceAllEntriesEvent,
    DropFieldsEvent,
    KeepFieldsEvent,
    RenameFieldsEvent,
    ReorderEntriesEvent,
    FillNaEvent,
    StringCatFieldEvent,
    ReplaceValuesEvent,
    UniquifyFieldEvent,
    NumberifyEvent,
    TransformFieldEvent,
    ReplaceEntriesAndMetaEvent,
    ReorderKeysEvent,
    apply_event,
)


class ScenarioCodec:
    """Codec for Scenario objects."""
    
    def encode(self, obj: Union["Scenario", dict[str, Any]]) -> dict[str, Any]:
        # Handle both Scenario objects and plain dicts
        if isinstance(obj, dict):
            return dict(obj)
        return obj.to_dict(add_edsl_version=False)
    
    def decode(self, data: dict[str, Any]) -> "Scenario":
        return Scenario.from_dict(data)


class ScenarioList(GitMixin, MutableSequence, Base, ScenarioListOperationsMixin, ScenarioListLikelyRemove):
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

    _versioned = 'store'
    _store_class = Store
    _event_handler = apply_event
    _codec = ScenarioCodec()  # Codec for Scenario <-> dict conversion

    # Allowed instance attributes - prevents external code from storing temporary data
    _allowed_attrs = frozenset({
        # Core state
        'store',
        # Properties with setters (these delegate to store.meta)
        'codebook',
        # Namespace objects (cached)
        '_to', '_join',
        # Conditional builder (ephemeral)
        '_cond_active', '_cond_branch', '_cond_condition', '_cond_ops',
        # GitMixin
        '_git', '_needs_git_init', '_last_push_result',
    })

    def __setattr__(self, name: str, value: Any) -> None:
        """Restrict attribute setting to allowed attributes only.
        
        This prevents external code from using ScenarioList instances to store
        temporary data, enforcing immutability through the event-based Store mechanism.
        """
        if name in self._allowed_attrs:
            super().__setattr__(name, value)
        else:
            raise AttributeError(
                f"Cannot set attribute '{name}' on ScenarioList. "
                f"ScenarioList is immutable - use event-based methods to modify data."
            )

    def __init__(
        self,
        data: Optional[list | str] = None,
        codebook: Optional[dict[str, str]] = None,
    ):
        """Initialize a new ScenarioList with optional data and codebook."""
        super().__init__()
        data_to_store = []
        if data is not None and isinstance(data, str):
            sl = ScenarioList.pull(data)
            if codebook is not None:
                raise ValueError(
                    "Codebook cannot be provided when pulling from a remote source"
                )
            codebook = sl.codebook
            super().__init__()
            for item in sl.data:
                # Already decoded Scenario objects from pull - encode for store
                data_to_store.append(self._codec.encode(item))
        else:
            for item in data or []:
                # Encode Scenario objects to dicts for primitive store
                data_to_store.append(self._codec.encode(item))
        #self.codebook = codebook or {}
        # Conditional builder state (ephemeral)
        self._cond_active: bool = False
        self._cond_branch: Optional[str] = None
        self._cond_condition: Any = None
        self._cond_ops: dict[str, list[tuple[str, tuple, dict]]] = {
            "then": [],
            "else": [],
        }

        self.store = Store(entries=data_to_store, meta={"codebook": codebook or {}})
    
    @event
    def append(self, item: Scenario) -> None:
        return AppendRowEvent(row=self._codec.encode(item))

    @property
    def data(self) -> List[Scenario]:
        """Decode store primitives to Scenario objects on read."""
        return [self._codec.decode(row) for row in self.store.entries]

    @property
    def codebook(self) -> dict[str, str]:
        return self.store.meta["codebook"]

    @codebook.setter
    def codebook(self, value: dict[str, str]) -> None:
        self.store.meta["codebook"] = value

    @property
    def convert(self) -> ScenarioListTo:
        """Namespace for conversion methods.
        
        Access conversion methods via this property:
        
            sl.convert.agent_list()
            sl.convert.dataset()
            sl.convert.survey()
            sl.convert.agent_blueprint()
            sl.convert.agent_traits()
            sl.convert.scenario_of_lists()
            sl.convert.key_value(field)
        
        Created: 2026-01-08
        """
        if not hasattr(self, '_to') or self._to is None:
            self._to = ScenarioListTo(self)
        return self._to

    @property
    def join(self) -> ScenarioListJoin:
        """Namespace for join methods.
        
        Access join methods via this property:
        
            sl.join.left(other, by='key')
            sl.join.inner(other, by='key')
            sl.join.right(other, by='key')
        
        Created: 2026-01-08
        """
        if not hasattr(self, '_join') or self._join is None:
            self._join = ScenarioListJoin(self)
        return self._join

    # @property
    # def codebook(self) -> dict[str, str]:
    #     return self.store.codebook

    # # Intercept method access during conditional recording
    # def __getattribute__(self, name: str):  # noqa: D401
    #     # Fast path for core attributes to avoid recursion
    #     if name in {
    #         "_cond_active",
    #         "_cond_branch",
    #         "_cond_condition",
    #         "_cond_ops",
    #         "when",
    #         "then",
    #         "else_",
    #         "otherwise",
    #         "end",
    #         "cancel",
    #     }:
    #         return object.__getattribute__(self, name)

    #     attr = object.__getattribute__(self, name)

    #     # Only intercept when actively recording and the attribute is a public bound method to record
    #     try:
    #         is_active = object.__getattribute__(self, "_cond_active")
    #         _current_branch = object.__getattribute__(self, "_cond_branch")
    #     except Exception:
    #         return attr

    #     if not is_active:
    #         return attr

    #     # Do not record private/dunder or builder controls
    #     if name.startswith("_"):
    #         return attr

    #     builder_exclusions = {
    #         "when",
    #         "then",
    #         "else_",
    #         "otherwise",
    #         "end",
    #         "cancel",
    #     }

    #     if name in builder_exclusions:
    #         return attr

    #     # Only wrap callables (methods)
    #     import inspect as _inspect

    #     if callable(attr) and _inspect.ismethod(attr):

    #         def recorder(*args, **kwargs):
    #             ops = object.__getattribute__(self, "_cond_ops")
    #             branch = object.__getattribute__(self, "_cond_branch")
    #             ops[branch].append((name, args, kwargs))
    #             return self

    #         return recorder

    #     return attr

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


    @event
    def __setitem__(self, index, value):
        """Set item at index."""
        return UpdateRowEvent(index, self._codec.encode(value))

    @event
    def __delitem__(self, index):
        """Delete item at index."""
        return RemoveRowsEvent(indices=(index,))

    def __len__(self):
        """Return number of items."""
        return len(self.data)

    @event
    def insert(self, index, value):
        """Insert value at index."""
        return InsertRowEvent(index=index, row=self._codec.encode(value))

    @event
    def clear(self) -> ClearEntriesEvent:
        """Remove all scenarios from the list (in-place)."""
        return ClearEntriesEvent()

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

    def unique(self) -> "ScenarioList":
        """Remove duplicate scenarios in-place, keeping first occurrence.

        This is an alias for deduplicate() for backwards compatibility.
        
        Returns:
            self: For method chaining.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> s1 = Scenario({"a": 1})
            >>> s2 = Scenario({"a": 1})  # Same content as s1
            >>> s3 = Scenario({"a": 2})
            >>> sl = ScenarioList([s1, s2, s3])
            >>> sl.unique()
            >>> len(sl)
            2
        """
        return self.deduplicate()

    @event
    def deduplicate(self) -> RemoveRowsEvent:
        """Remove duplicate scenarios in-place, keeping first occurrence.

        This method modifies the ScenarioList in-place using the event sourcing
        pattern. It emits a RemoveRowsEvent containing the indices of duplicate
        scenarios to be removed.

        Returns:
            RemoveRowsEvent: Event containing indices of duplicates to remove.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> s1 = Scenario({"a": 1})
            >>> s2 = Scenario({"a": 1})  # Same content as s1
            >>> s3 = Scenario({"a": 2})
            >>> sl = ScenarioList([s1, s2, s3])
            >>> sl.deduplicate()  # Removes duplicate in-place
            >>> len(sl)
            2

        Notes:
            - Keeps the first occurrence of each unique scenario
            - Uses hash-based comparison for uniqueness
            - For a non-mutating version, use unique() instead
        """
        seen_hashes = set()
        indices_to_remove = []

        for i, scenario in enumerate(self.data):
            scenario_hash = hash(scenario)
            if scenario_hash in seen_hashes:
                indices_to_remove.append(i)
            else:
                seen_hashes.add(scenario_hash)

        return RemoveRowsEvent(indices=tuple(indices_to_remove))

    @event
    def uniquify(self, field: str) -> UniquifyFieldEvent:
        """
        Make all values of a field unique by appending suffixes (_1, _2, etc.) as needed (in-place).

        This method ensures that all values for the specified field are unique across
        all scenarios in the list. When duplicate values are encountered, they are made
        unique by appending suffixes like "_1", "_2", "_3", etc. The first occurrence
        of a value remains unchanged.

        Args:
            field: The name of the field whose values should be made unique.

        Returns:
            UniquifyFieldEvent: Event with pre-computed unique values.

        Raises:
            ScenarioError: If the field does not exist in any scenario.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList([
            ...     Scenario({"id": "item", "value": 1}),
            ...     Scenario({"id": "item", "value": 2}),
            ...     Scenario({"id": "item", "value": 3}),
            ...     Scenario({"id": "other", "value": 4})
            ... ])
            >>> sl.uniquify("id")
            >>> [s["id"] for s in sl]
            ['item', 'item_1', 'item_2', 'other']
        """
        # Check if field exists in at least one scenario
        if not any(field in scenario for scenario in self.data):
            raise ScenarioError(f"Field '{field}' not found in any scenario")

        seen_values = {}  # Maps original value to count of occurrences
        new_values = []

        for scenario in self.data:
            # Keep original if field not present
            if field not in scenario:
                new_values.append(scenario.get(field))
                continue

            original_value = scenario[field]

            # Determine the new unique value
            if original_value not in seen_values:
                # First occurrence - use original value
                new_value = original_value
                seen_values[original_value] = 1
            else:
                # Duplicate - append suffix
                suffix_num = seen_values[original_value]
                new_value = f"{original_value}_{suffix_num}"
                seen_values[original_value] += 1

            new_values.append(new_value)

        return UniquifyFieldEvent(field=field, new_values=tuple(new_values))

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

    @event
    def _convert_jinja_braces(self) -> ReplaceAllEntriesEvent:
        """
        Convert Jinja braces to alternative symbols in all Scenarios in the list.

        This method modifies the ScenarioList in-place, converting all Jinja template 
        braces ({{ and }}) in string values to alternative symbols (<< and >>).
        This is useful when you need to prevent template processing or avoid conflicts
        with other templating systems.

        Returns:
            self for method chaining.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> s = Scenario({"text": "Template with {{variable}}"})
            >>> sl = ScenarioList([s])
            >>> sl._convert_jinja_braces()
            ScenarioList([Scenario({'text': 'Template with <<variable>>'})])
            >>> sl[0]["text"]
            'Template with <<variable>>'

        Notes:
            - This modifies the ScenarioList in-place
            - This is primarily intended for internal use
            - The default replacement symbols are << and >>
        """
        converted_entries = tuple(
            self._codec.encode(scenario._convert_jinja_braces())
            for scenario in self
        )
        return ReplaceAllEntriesEvent(entries=converted_entries)

    @event
    def give_valid_names(self, existing_codebook: dict = None) -> ReplaceEntriesAndMetaEvent:
        """Give valid names to the scenario keys (in-place), using an existing codebook if provided.

        Args:
            existing_codebook (dict, optional): Existing mapping of original keys to valid names.
                Defaults to None.

        Returns:
            ReplaceEntriesAndMetaEvent: Event with renamed entries and updated codebook.

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 2}), Scenario({'a': 1, 'b': 1})])
        >>> s.give_valid_names()
        >>> list(s.data[0].keys())
        ['a', 'b']
        """
        codebook = existing_codebook.copy() if existing_codebook else {}

        new_entries = []
        for scenario in self:
            new_entry = {}
            for key in scenario:
                if is_valid_variable_name(key):
                    new_entry[key] = scenario[key]
                    continue

                if key in codebook:
                    new_key = codebook[key]
                else:
                    new_key = sanitize_string(key)
                    if not is_valid_variable_name(new_key):
                        new_key = f"var_{len(codebook)}"
                    codebook[key] = new_key

                new_entry[new_key] = scenario[key]

            new_entries.append(new_entry)

        return ReplaceEntriesAndMetaEvent(
            entries=tuple(new_entries),
            meta_updates=(("codebook", codebook),)
        )

    @event
    def unpivot(
        self,
        id_vars: Optional[List[str]] = None,
        value_vars: Optional[List[str]] = None,
    ) -> ReplaceAllEntriesEvent:
        """Convert wide-format fields into long format rows (in-place).

        For each Scenario, produces rows of (id_vars..., variable, value) where
        each original field listed in ``value_vars`` becomes a row with its
        field name under ``variable`` and its value under ``value``.

        Args:
            id_vars: Field names to preserve as identifiers on each output row.
            value_vars: Field names to unpivot. Defaults to all non-id_vars.

        Returns:
            ReplaceAllEntriesEvent: Event with unpivoted entries.
        """
        id_vars = id_vars or []
        
        new_entries = []
        for scenario in self.data:
            # Determine value_vars if not specified
            vars_to_unpivot = value_vars or [k for k in scenario.keys() if k not in id_vars]
            
            for var_name in vars_to_unpivot:
                new_entry = {id_var: scenario.get(id_var) for id_var in id_vars}
                new_entry["variable"] = var_name
                new_entry["value"] = scenario.get(var_name)
                new_entries.append(new_entry)
        
        return ReplaceAllEntriesEvent(entries=tuple(new_entries))

    @event
    def apply(
        self, func: Callable, field: str, new_name: Optional[str] = None, replace: bool = False
    ) -> TransformFieldEvent:
        """Apply a function to a field across all scenarios (in-place).

        Evaluates ``func(scenario[field])`` for each Scenario and stores the result
        in ``new_name`` (or the original field name if ``new_name`` is None). If
        ``replace`` is True, the original field is removed (use drop() separately).

        Args:
            func: Function to apply to each value in ``field``.
            field: Existing field name to read from.
            new_name: Optional output field name. Defaults to ``field``.
            replace: If True, drop the original field after (call drop() after this).

        Returns:
            TransformFieldEvent: Event with pre-computed transformed values.
        """
        target_field = new_name if new_name else field
        new_values = []
        for scenario in self.data:
            if field in scenario:
                new_values.append(func(scenario[field]))
            else:
                new_values.append(None)
        
        return TransformFieldEvent(field=field, new_field=target_field, new_values=tuple(new_values))

    @event
    def zip(self, field_a: str, field_b: str, new_name: str) -> AddFieldByIndexEvent:
        """Zip two iterable fields in each Scenario into a dict under a new key (in-place).

        For every Scenario in the list, this method computes
        ``dict(zip(scenario[field_a], scenario[field_b]))`` and stores the result
        in a new key named ``new_name``.

        Args:
            field_a: Name of the first iterable field whose values become dict keys.
            field_b: Name of the second iterable field whose values become dict values.
            new_name: Name of the new field to store the resulting dictionary under.

        Returns:
            AddFieldByIndexEvent: Event with pre-computed zipped dictionaries.

        Examples:
            >>> sl = ScenarioList([
            ...     Scenario({"keys": ["a", "b"], "vals": [1, 2]}),
            ...     Scenario({"keys": ["x", "y"], "vals": [9, 8]}),
            ... ])
            >>> sl.zip("keys", "vals", "mapping")
            >>> sl[0]["mapping"]
            {'a': 1, 'b': 2}
        """
        new_values = []
        for scenario in self.data:
            zipped = dict(zip(scenario[field_a], scenario[field_b]))
            new_values.append(zipped)
        
        return AddFieldByIndexEvent(field=new_name, values=tuple(new_values))

    @event
    def add_scenario_reference(self, key: str, scenario_field_name: str) -> ReplaceAllEntriesEvent:
        """Add a reference to the scenario to a field across all Scenarios (in-place)."""
        new_entries = []
        for scenario in self:
            new_entry = dict(scenario)
            new_entry[key] = new_entry[key] + "{{ scenario." + scenario_field_name + " }}"
            new_entries.append(new_entry)
        return ReplaceAllEntriesEvent(entries=tuple(new_entries))

    @event
    def string_cat(
        self,
        key: str,
        addend: str,
        position: str = "suffix",
    ) -> StringCatFieldEvent:
        """Concatenate a string to a field across all Scenarios (in-place).

        Applies the same behavior as ``Scenario.string_cat`` to each Scenario in the list.

        Args:
            key: The key whose value will be concatenated in each Scenario.
            addend: The string to concatenate to the existing value.
            position: Either "suffix" (default) or "prefix".

        Returns:
            StringCatFieldEvent: Event to concatenate string to field.

        Raises:
            ValueError: If ``position`` is not "suffix" or "prefix".
        """
        if position not in ("suffix", "prefix"):
            raise ValueError(f"position must be 'suffix' or 'prefix', got {position}")
        return StringCatFieldEvent(field=key, addend=addend, position=position)

    def string_cat_if(
        self,
        key: str,
        addend: str,
        condition: Any,
        position: str = "suffix",
    ) -> "ScenarioList":
        """Conditionally concatenate a string to a field across all Scenarios (in-place).

        The condition may be a boolean or a string such as 'yes'/'no', 'true'/'false', '1'/'0'.
        Non-empty strings are coerced using a permissive truthy mapping.
        
        If condition is falsy, no changes are made.
        """
        if not self._cond_to_bool(condition):
            return self
        return self.string_cat(key, addend, position=position)

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


    def __add__(self, other) -> "ScenarioList":
        """Combine this ScenarioList with another Scenario or ScenarioList.
        
        Args:
            other: A Scenario or ScenarioList to add.
            
        Returns:
            A new ScenarioList with the combined entries.
            
        Raises:
            ScenarioError: If other is not a Scenario or ScenarioList.
        """
        if isinstance(other, Scenario):
            other_entries = [self._codec.encode(other)]
        elif isinstance(other, ScenarioList):
            other_entries = [self._codec.encode(item) for item in other]
        else:
            raise ScenarioError("Don't know how to combine!")
        
        # Create new ScenarioList and apply event to it (preserves + semantics)
        new_list = self.duplicate()
        new_entries = tuple(new_list.store.entries) + tuple(other_entries)
        event_obj = ReplaceAllEntriesEvent(entries=new_entries)
        apply_event(event_obj, new_list.store)
        return new_list

    @event
    def pivot(
        self,
        id_vars: List[str] = None,
        var_name: str = "variable",
        value_name: str = "value",
    ) -> ReplaceAllEntriesEvent:
        """Pivot from long format back to wide columns (in-place).

        Groups rows by ``id_vars`` and spreads the values under ``var_name``
        into separate columns whose values come from ``value_name``.

        Args:
            id_vars: Identifier fields to group by.
            var_name: Field holding the output column names (default: "variable").
            value_name: Field holding the output values (default: "value").

        Returns:
            ReplaceAllEntriesEvent: Event with pivoted entries.
        """
        from collections import defaultdict
        
        id_vars = id_vars or []
        
        # Group by id_vars and collect var_name -> value_name mappings
        groups = defaultdict(dict)
        for scenario in self.data:
            key = tuple(scenario.get(id_var) for id_var in id_vars)
            column_name = scenario.get(var_name)
            value = scenario.get(value_name)
            if column_name is not None:
                groups[key][column_name] = value
        
        # Build pivoted entries
        new_entries = []
        for key, values in groups.items():
            new_entry = dict(zip(id_vars, key))
            new_entry.update(values)
            new_entries.append(new_entry)
        
        return ReplaceAllEntriesEvent(entries=tuple(new_entries))

    @event
    def group_by(
        self, id_vars: List[str], variables: List[str], func: Callable
    ) -> ReplaceAllEntriesEvent:
        """Group scenarios and aggregate variables with a custom function (in-place).

        Groups by the values of ``id_vars`` and passes lists of values for each
        field in ``variables`` to ``func``. The function must return a dict whose
        keys are added as fields on the aggregated Scenario.

        Args:
            id_vars: Field names to group by.
            variables: Field names to aggregate and pass to ``func`` as lists.
            func: Callable that accepts len(variables) lists and returns a dict.

        Returns:
            ReplaceAllEntriesEvent: Event with aggregated entries.

        Raises:
            ScenarioError: If the function arity does not match variables or returns non-dict.
        """
        from collections import defaultdict
        
        # Group scenarios by id_vars
        groups = defaultdict(lambda: {var: [] for var in variables})
        for scenario in self.data:
            key = tuple(scenario.get(id_var) for id_var in id_vars)
            for var in variables:
                groups[key][var].append(scenario.get(var))
        
        # Apply function to each group
        new_entries = []
        for key, var_lists in groups.items():
            new_entry = dict(zip(id_vars, key))
            # Pass variable lists to func
            args = [var_lists[var] for var in variables]
            result = func(*args)
            if not isinstance(result, dict):
                raise ValueError(f"group_by function must return a dict, got {type(result)}")
            new_entry.update(result)
            new_entries.append(new_entry)
        
        return ReplaceAllEntriesEvent(entries=tuple(new_entries))

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

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the ScenarioList.

        This representation can be used with eval() to recreate the ScenarioList object.
        Used primarily for doctests and debugging.
        """
        return f"ScenarioList([{', '.join([x._eval_repr_() for x in self.data])}])"


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

        if isinstance(other, Scenario):
            other = ScenarioList([other])
        elif not isinstance(other, ScenarioList):
            from .exceptions import TypeScenarioError
            raise TypeScenarioError(f"Cannot multiply ScenarioList with {type(other)}")

        # Compute cross product entries
        new_entries = [
            self._codec.encode(s1 + s2)
            for s1, s2 in product(self, other)
        ]
        
        # Create new ScenarioList and apply event (preserves * semantics)
        new_list = ScenarioList(data=[], codebook=dict(self.codebook))
        event_obj = ReplaceAllEntriesEvent(entries=tuple(new_entries))
        apply_event(event_obj, new_list.store)
        return new_list

    @event
    def shuffle(self, seed: Optional[str] = None) -> ReorderEntriesEvent:
        """Shuffle the ScenarioList (in-place).

        >>> s = ScenarioList.from_list("a", [1,2,3,4])
        >>> s.shuffle(seed = "1234")
        ScenarioList([Scenario({'a': 1}), Scenario({'a': 4}), Scenario({'a': 3}), Scenario({'a': 2})])
        """
        indices = list(range(len(self.data)))
        if seed:
            random.seed(seed)
        random.shuffle(indices)
        return ReorderEntriesEvent(new_order=tuple(indices))

    @event
    def full_replace(self, other: "ScenarioList") -> ReplaceEntriesAndMetaEvent:
        """Replace the ScenarioList contents with another ScenarioList's contents (in-place).
        
        Args:
            other: The ScenarioList to copy data from.
            
        Returns:
            ReplaceEntriesAndMetaEvent: Event that replaces all entries and metadata.
        """
        # Encode all scenarios from the other list
        new_entries = tuple(self._codec.encode(s) for s in other.data)
        return ReplaceEntriesAndMetaEvent(
            entries=new_entries,
            meta_updates=(("codebook", other.codebook),)
        )

    @event
    def sample(self, n: int, seed: Optional[str] = None) -> ReplaceAllEntriesEvent:
        """Return a random sample from the ScenarioList (in-place).

        >>> s = ScenarioList.from_list("a", [1,2,3,4,5,6])
        >>> s.sample(3, seed = "edsl")
        >>> len(s)
        3
        """
        if seed:
            random.seed(seed)

        # Get random sample of indices
        indices = random.sample(range(len(self.data)), n)
        sampled_entries = [dict(self.data[i]) for i in indices]
        return ReplaceAllEntriesEvent(entries=tuple(sampled_entries))

    def split(
        self, frac_left: float = 0.5, seed: Optional[int] = None
    ) -> tuple[ScenarioList, ScenarioList]:
        """Split the ScenarioList into two random groups.

        Randomly assigns scenarios to two groups (left and right) based on the specified
        fraction. Useful for creating train/test splits or other random partitions.

        Args:
            frac_left: Fraction (0-1) of scenarios to assign to the left group. Defaults to 0.5.
            seed: Optional random seed for reproducibility.

        Returns:
            tuple[ScenarioList, ScenarioList]: A tuple containing (left, right) ScenarioLists.

        Raises:
            ValueError: If frac_left is not between 0 and 1.

        Examples:
            Split a scenario list 50/50 (default):

            >>> from edsl import Scenario, ScenarioList
            >>> sl = ScenarioList([Scenario({'id': i}) for i in range(10)])
            >>> left, right = sl.split(seed=42)
            >>> len(left)
            5
            >>> len(right)
            5

            Split a scenario list 70/30:

            >>> sl = ScenarioList([Scenario({'id': i}) for i in range(10)])
            >>> left, right = sl.split(0.7, seed=42)
            >>> len(left)
            7
            >>> len(right)
            3

            Create reproducible splits:

            >>> sl = ScenarioList([Scenario({'id': i}) for i in range(5)])
            >>> left1, right1 = sl.split(0.6, seed=123)
            >>> left2, right2 = sl.split(0.6, seed=123)
            >>> len(left1) == len(left2) and len(right1) == len(right2)
            True
        """
        return list_split(self, frac_left, seed)


    @event
    def expand(self, *expand_fields: str, number_field: bool = False) -> ReplaceAllEntriesEvent:
        """Expand the ScenarioList by one or more fields (in-place).

        - When a single field is provided, behavior is unchanged: expand rows by that field.
        - When multiple fields are provided, they are expanded in lockstep (aligned). Each
          field must be an iterable (strings are treated as scalars) of equal length; the
          i-th elements across all fields are combined into one expanded row.

        Args:
            *expand_fields: One or more field names to expand. When multiple, lengths must match.
            number_field: Whether to add a per-field index (1-based) for expanded values as
                ``<field>_number``.

        Returns:
            ReplaceAllEntriesEvent: Event with expanded entries.

        Examples:

            Single-field:
            >>> s = ScenarioList([Scenario({'a': 1, 'b': [1, 2]})])
            >>> s.expand('b')
            >>> len(s)
            2
        """
        if not expand_fields:
            raise ScenarioError("expand() requires at least one field name")

        new_entries = []
        
        # Single-field case
        if len(expand_fields) == 1:
            expand_field = expand_fields[0]
            for scenario in self.data:
                values = scenario[expand_field]
                if not isinstance(values, Iterable) or isinstance(values, str):
                    values = [values]
                for index, value in enumerate(values):
                    new_entry = dict(scenario)
                    new_entry[expand_field] = value
                    if number_field:
                        new_entry[expand_field + "_number"] = index + 1
                    new_entries.append(new_entry)
        else:
            # Multi-field aligned expansion
            fields = list(expand_fields)
            for scenario in self.data:
                value_lists = []
                for field in fields:
                    vals = scenario[field]
                    if not isinstance(vals, Iterable) or isinstance(vals, str):
                        vals = [vals]
                    value_lists.append(list(vals))

                lengths = {len(v) for v in value_lists}
                if len(lengths) != 1:
                    lengths_str = ", ".join(
                        f"{fld}:{len(v)}" for fld, v in zip(fields, value_lists)
                    )
                    raise ScenarioError(
                        f"All fields must have equal lengths for aligned expansion; got {lengths_str}"
                    )

                for index, tuple_vals in enumerate(zip(*value_lists)):
                    new_entry = dict(scenario)
                    for field, val in zip(fields, tuple_vals):
                        new_entry[field] = val
                        if number_field:
                            new_entry[field + "_number"] = index + 1
                    new_entries.append(new_entry)

        return ReplaceAllEntriesEvent(entries=tuple(new_entries))

    @event
    def _concatenate(
        self,
        fields: List[str],
        output_type: str = "string",
        separator: str = ";",
        prefix: str = "",
        postfix: str = "",
        new_field_name: Optional[str] = None,
    ) -> ReplaceAllEntriesEvent:
        """Concatenate fields into a new field as string/list/set (in-place).

        Removes the listed ``fields`` from each Scenario, combines their values in
        order, and writes them into ``new_field_name`` (or an auto-generated name).
        Formatting is controlled by ``output_type``, ``separator``, ``prefix``, and
        ``postfix``.

        Args:
            fields: Field names to concatenate, in order.
            output_type: "string" (default), "list", or "set".
            separator: String used when output_type="string".
            prefix: Optional prefix per value before concatenation.
            postfix: Optional postfix per value before concatenation.
            new_field_name: Name of the resulting field. Defaults to "concat_...".

        Returns:
            ReplaceAllEntriesEvent: Event with concatenated entries.
        """
        if new_field_name is None:
            new_field_name = "concat_" + "_".join(fields)
        
        new_entries = []
        for scenario in self.data:
            new_entry = {k: v for k, v in scenario.items() if k not in fields}
            
            # Collect values with prefix/postfix
            values = [f"{prefix}{scenario.get(f, '')}{postfix}" for f in fields]
            
            if output_type == "string":
                new_entry[new_field_name] = separator.join(str(v) for v in values)
            elif output_type == "list":
                new_entry[new_field_name] = values
            elif output_type == "set":
                new_entry[new_field_name] = set(values)
            
            new_entries.append(new_entry)
        
        return ReplaceAllEntriesEvent(entries=tuple(new_entries))

    def concatenate(
        self,
        fields: List[str],
        separator: str = ";",
        prefix: str = "",
        postfix: str = "",
        new_field_name: Optional[str] = None,
    ) -> "ScenarioList":
        """Concatenate fields into a single string field (in-place).

        Equivalent to calling ``_concatenate`` with output_type="string".

        Args:
            fields: Field names to concatenate, in order.
            separator: String used to join values.
            prefix: Optional prefix per value.
            postfix: Optional postfix per value.
            new_field_name: Name of the resulting field; defaults to auto-generated.

        Returns:
            self: For method chaining.
        """
        return self._concatenate(
            fields,
            output_type="string",
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
    ) -> "ScenarioList":
        """Concatenate fields into a single list field (in-place).

        Equivalent to calling ``_concatenate`` with output_type="list".

        Args:
            fields: Field names to collect.
            prefix: Optional prefix per value.
            postfix: Optional postfix per value.
            new_field_name: Name of the resulting field; defaults to auto-generated.

        Returns:
            self: For method chaining.
        """
        return self._concatenate(
            fields,
            output_type="list",
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
    ) -> "ScenarioList":
        """Concatenate fields into a single set field (in-place).

        Equivalent to calling ``_concatenate`` with output_type="set".

        Args:
            fields: Field names to collect.
            prefix: Optional prefix per value.
            postfix: Optional postfix per value.
            new_field_name: Name of the resulting field; defaults to auto-generated.

        Returns:
            self: For method chaining.
        """
        return self._concatenate(
            fields,
            output_type="set",
            prefix=prefix,
            postfix=postfix,
            new_field_name=new_field_name,
        )

    @event
    def unpack_dict(
        self, field: str, prefix: Optional[str] = None, drop_field: bool = False
    ) -> ReplaceAllEntriesEvent:
        """Unpack a dictionary field into separate fields (in-place).

        For each key/value in the dictionary at ``field``, creates a new field on
        each Scenario. If ``prefix`` is provided it is prepended to each new field
        name. When ``drop_field`` is True, removes the original dictionary field.

        Args:
            field: Name of the dict field to unpack.
            prefix: Optional prefix for new field names.
            drop_field: If True, remove the original field after unpacking.

        Returns:
            ReplaceAllEntriesEvent: Event with unpacked entries.
        """
        new_entries = []
        for scenario in self.data:
            new_entry = dict(scenario)
            if field in new_entry and isinstance(new_entry[field], dict):
                dict_value = new_entry[field]
                for key, value in dict_value.items():
                    new_key = f"{prefix}{key}" if prefix else key
                    new_entry[new_key] = value
                if drop_field:
                    del new_entry[field]
            new_entries.append(new_entry)
        
        return ReplaceAllEntriesEvent(entries=tuple(new_entries))

    @event
    def transform(
        self, field: str, func: Callable, new_name: Optional[str] = None
    ) -> TransformFieldEvent:
        """Transform a field's value using a function (in-place).

        Computes ``func(scenario[field])`` for each Scenario and writes the result
        to ``new_name`` if provided, otherwise overwrites ``field``.

        Args:
            field: Existing field name to transform.
            func: Transformation function applied to each value.
            new_name: Optional new field name; if None, overwrite ``field``.

        Returns:
            TransformFieldEvent: Event with pre-computed transformed values.
        """
        target_field = new_name if new_name else field
        new_values = []
        for scenario in self.data:
            if field in scenario:
                new_values.append(func(scenario[field]))
            else:
                new_values.append(None)
        
        return TransformFieldEvent(field=field, new_field=target_field, new_values=tuple(new_values))

    @event
    def mutate(
        self, new_var_string: str, functions_dict: Optional[dict[str, Callable]] = None
    ) -> AddFieldByIndexEvent:
        """Add a new field computed from an expression (in-place).

        Evaluates an expression of the form "new_var = expression" against each
        Scenario using a safe evaluator. Optional ``functions_dict`` provides
        callable helpers usable inside the expression.

        Args:
            new_var_string: String of the form "var_name = expression".
            functions_dict: Optional mapping of function name to callable.

        Returns:
            AddFieldByIndexEvent: Event with pre-computed values.

        Raises:
            ScenarioError: If the var name is invalid or evaluation fails.
        """
        from simpleeval import simple_eval
        
        # Parse "var_name = expression"
        if "=" not in new_var_string:
            raise ScenarioError(f"Invalid mutate expression: {new_var_string}. Expected 'var_name = expression'")
        
        parts = new_var_string.split("=", 1)
        new_var_name = parts[0].strip()
        expression = parts[1].strip()
        
        if not is_valid_variable_name(new_var_name):
            raise ScenarioError(f"Invalid variable name: {new_var_name}")
        
        # Pre-compute values for each scenario
        new_values = []
        functions = functions_dict or {}
        
        for scenario in self.data:
            names = dict(scenario)
            names.update(functions)
            try:
                result = simple_eval(expression, names=names, functions=functions)
            except Exception as e:
                raise ScenarioError(f"Error evaluating '{expression}': {e}")
            new_values.append(result)
        
        return AddFieldByIndexEvent(field=new_var_name, values=tuple(new_values))

    @event
    def order_by(self, *fields: str, reverse: bool = False) -> ReorderEntriesEvent:
        """Order scenarios by one or more fields (in-place).

        Args:
            *fields: Field names to sort by, in priority order.
            reverse: If True, sort in descending order.

        Returns:
            ReorderEntriesEvent: Event containing new order indices.
        """
        # Get indices sorted by the specified fields
        def sort_key(idx):
            scenario = self.data[idx]
            return tuple(scenario.get(f) for f in fields)
        
        indices = list(range(len(self.data)))
        indices.sort(key=sort_key, reverse=reverse)
        return ReorderEntriesEvent(new_order=tuple(indices))

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

    @event
    def filter(self, expression: str) -> RemoveRowsEvent:
        """Filter scenarios by evaluating an expression per row (in-place).

        The expression is evaluated with each Scenario's fields available as
        variables using a safe evaluator. Removes scenarios for which the
        expression evaluates to False.

        Args:
            expression: Boolean expression referencing scenario fields,
                e.g. "age >= 18 and country == 'US'".

        Raises:
            ScenarioError: If the expression references missing fields or evaluation fails.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList([
            ...     Scenario({'age': 20, 'country': 'US'}),
            ...     Scenario({'age': 16, 'country': 'CA'})
            ... ])
            >>> sl.filter("age >= 18 and country == 'US'")
            >>> len(sl)
            1
        """
        from simpleeval import simple_eval
        import re
        
        # Handle dotted field names by replacing dots with a placeholder in both
        # the expression and the names dict
        def escape_dotted_keys(names_dict, expr):
            """Replace dotted keys with underscore versions."""
            escaped_names = {}
            modified_expr = expr
            
            # Sort by length descending to replace longer keys first
            # (e.g., "answer.example.nested" before "answer.example")
            sorted_keys = sorted(names_dict.keys(), key=len, reverse=True)
            
            for key in sorted_keys:
                if '.' in key:
                    # Create escaped version of key
                    escaped_key = key.replace('.', '_DOT_')
                    escaped_names[escaped_key] = names_dict[key]
                    # Replace in expression - use word boundaries to avoid partial matches
                    # Match the dotted key pattern
                    pattern = re.escape(key)
                    modified_expr = re.sub(pattern, escaped_key, modified_expr)
                else:
                    escaped_names[key] = names_dict[key]
            
            return escaped_names, modified_expr
        
        indices_to_remove = []
        for i, scenario in enumerate(self.data):
            names = dict(scenario)
            escaped_names, modified_expr = escape_dotted_keys(names, expression)
            try:
                result = simple_eval(modified_expr, names=escaped_names)
                if not result:
                    indices_to_remove.append(i)
            except Exception as e:
                raise ScenarioError(f"Error evaluating '{expression}' on scenario {i}: {e}")
        
        return RemoveRowsEvent(indices=tuple(indices_to_remove))


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

    @event
    def select(self, *fields: str) -> KeepFieldsEvent:
        """Select only specified fields from all scenarios in the list (in-place).

        This method applies the select operation to each scenario in the list,
        keeping only the specified fields.

        Args:
            *fields: Field names to select from each scenario.

        Returns:
            KeepFieldsEvent to be applied to the store.

        Raises:
            KeyScenarioError: If any specified field doesn't exist in any scenario.

        Examples:
            >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
            >>> s.select('a')
            ScenarioList([Scenario({'a': 1}), Scenario({'a': 1})])
        """
        # Validate that all fields exist in at least one scenario
        all_keys = set()
        for scenario in self:
            all_keys.update(scenario.keys())
        
        missing = set(fields) - all_keys
        if missing:
            from .exceptions import KeyScenarioError
            raise KeyScenarioError(f"Keys {missing} not found in any scenario")
        
        return KeepFieldsEvent(fields=tuple(fields))

    @event
    def drop(self, *fields: str) -> DropFieldsEvent:
        """Drop fields from the scenarios (in-place).

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        >>> s.drop('a')
        ScenarioList([Scenario({'b': 1}), Scenario({'b': 2})])
        """
        return DropFieldsEvent(fields=tuple(fields))

    @event
    def keep(self, *fields: str) -> KeepFieldsEvent:
        """Keep only the specified fields in the scenarios (in-place).

        :param fields: The fields to keep.

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        >>> s.keep('a')
        ScenarioList([Scenario({'a': 1}), Scenario({'a': 1})])
        """
        return KeepFieldsEvent(fields=tuple(fields))

    @event
    def numberify(self) -> NumberifyEvent:
        """Convert string values to numeric types where possible (in-place).

        This method attempts to convert string values to integers or floats
        for all fields across all scenarios. It's particularly useful when loading
        data from CSV files where numeric fields may be stored as strings.

        Conversion rules:
        - None values remain None
        - Already numeric values (int, float) remain unchanged
        - String values that can be parsed as integers are converted to int
        - String values that can be parsed as floats are converted to float
        - String values that cannot be parsed remain as strings
        - Empty strings remain as empty strings

        Returns:
            NumberifyEvent: Event with pre-computed numeric conversions.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList([
            ...     Scenario({'age': '30', 'height': '5.5', 'name': 'Alice'}),
            ...     Scenario({'age': '25', 'height': '6.0', 'name': 'Bob'})
            ... ])
            >>> sl.numberify()
            >>> sl[0]
            Scenario({'age': 30, 'height': 5.5, 'name': 'Alice'})
        """
        def try_convert(val):
            if val is None or isinstance(val, (int, float)):
                return val
            if isinstance(val, str):
                if val == "":
                    return val
                try:
                    return int(val)
                except ValueError:
                    try:
                        return float(val)
                    except ValueError:
                        return val
            return val
        
        conversions = []
        for i, scenario in enumerate(self.data):
            for key, value in scenario.items():
                new_value = try_convert(value)
                if new_value != value:
                    conversions.append((i, key, new_value))
        
        return NumberifyEvent(conversions=tuple(conversions))

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

    @event
    def reorder_keys(self, new_order: List[str]) -> ReorderKeysEvent:
        """Reorder keys in each Scenario according to the provided list (in-place).

        Ensures the new order contains exactly the same keys as present in
        the scenarios, then rewrites each Scenario with that ordering.

        Args:
            new_order: Desired key order; must be a permutation of existing keys.

        Returns:
            ReorderKeysEvent: Event with new key order.
        """
        return ReorderKeysEvent(new_order=tuple(new_order))

    @event
    def unpack(
        self, field: str, new_names: Optional[List[str]] = None, keep_original=True
    ) -> ReplaceAllEntriesEvent:
        """Unpack a list-like field into multiple fields (in-place).

        Splits the value under ``field`` into multiple fields named by
        ``new_names`` (or auto-generated names). If ``keep_original`` is False,
        the original field is removed.

        Args:
            field: Field to unpack (list-like).
            new_names: Optional list of output field names; defaults to indexes.
            keep_original: Whether to retain the original field.

        Returns:
            ReplaceAllEntriesEvent: Event with unpacked entries.
        """
        new_entries = []
        for scenario in self.data:
            new_entry = dict(scenario)
            if field in new_entry:
                values = new_entry[field]
                if isinstance(values, (list, tuple)):
                    names = new_names if new_names else [f"{field}_{i}" for i in range(len(values))]
                    for name, value in zip(names, values):
                        new_entry[name] = value
                if not keep_original:
                    del new_entry[field]
            new_entries.append(new_entry)
        
        return ReplaceAllEntriesEvent(entries=tuple(new_entries))

    @event
    def add_list(self, name: str, values: List[Any]) -> AddFieldByIndexEvent:
        """Add a list of values to a ScenarioList (in-place).

        Example:

        >>> s = ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
        >>> s.add_list('age', [30, 25])
        ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
        """
        if len(values) != len(self.data):
            raise ScenarioError(
                f"Length of values ({len(values)}) does not match length of ScenarioList ({len(self)})"
            )
        return AddFieldByIndexEvent(field=name, values=tuple(values))

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

    @event
    def add_value(self, name: str, value: Any) -> AddFieldToAllEntriesEvent:
        """Add a value to all scenarios in a ScenarioList (in-place).

        Example:

        >>> s = ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
        >>> s.add_value('age', 30)
        ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 30})])
        """
        return AddFieldToAllEntriesEvent(field=name, value=value)

    @event
    def tack_on(self, replacements: dict[str, Any], index: int = -1) -> AppendRowEvent:
        """Add a duplicate of an existing scenario with optional value replacements (in-place).

        This method duplicates the scenario at *index* (default ``-1`` which refers to the
        last scenario), applies the key/value pairs provided in *replacements*, and
        appends the modified scenario to this ScenarioList.

        Args:
            replacements: Mapping of field names to new values to overwrite in the cloned
                scenario.
            index: Index of the scenario to duplicate. Supports negative indexing just
                like normal Python lists (``-1`` is the last item).

        Returns:
            self for method chaining.

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

        return AppendRowEvent(row=self._codec.encode(new_scenario))

    @event
    def rename(self, replacement_dict: dict) -> RenameFieldsEvent:
        """Rename the fields in the scenarios (in-place).

        :param replacement_dict: A dictionary with the old names as keys and the new names as values.

        Raises:
            KeyScenarioError: If any key in replacement_dict is not present in any scenario.

        Example:

        >>> s = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
        >>> s.rename({'name': 'first_name', 'age': 'years'})
        ScenarioList([Scenario({'first_name': 'Alice', 'years': 30}), Scenario({'first_name': 'Bob', 'years': 25})])

        """
        from .exceptions import KeyScenarioError

        # Collect all keys present across all scenarios
        all_keys = set()
        for scenario in self:
            all_keys.update(scenario.keys())

        # Check for keys in replacement_dict that are not present in any scenario
        missing_keys = [key for key in replacement_dict.keys() if key not in all_keys]
        if missing_keys:
            raise KeyScenarioError(
                f"The following keys in replacement_dict are not present in any scenario: {', '.join(missing_keys)}"
            )

        return RenameFieldsEvent(rename_map=tuple(replacement_dict.items()))

    @event
    def snakify(self) -> RenameFieldsEvent:
        """Convert all scenario keys to valid Python identifiers (snake_case) in-place.

        This method transforms all keys to lowercase, replaces spaces and special 
        characters with underscores, and ensures all keys are valid Python identifiers. 
        If multiple keys would map to the same snakified name, numbers are appended 
        to ensure uniqueness.

        Returns:
            self for method chaining.

        Examples:
            >>> s = ScenarioList([Scenario({'First Name': 'Alice', 'Age Group': '30s'})])
            >>> s.snakify()
            ScenarioList([Scenario({'first_name': 'Alice', 'age_group': '30s'})])
            >>> sorted(s[0].keys())
            ['age_group', 'first_name']

            >>> s = ScenarioList([Scenario({'name': 'Alice', 'Name': 'Bob', 'NAME': 'Charlie'})])
            >>> s.snakify()
            ScenarioList([Scenario({'name': 'Alice', 'name_1': 'Bob', 'name_2': 'Charlie'})])

            >>> s = ScenarioList([Scenario({'User-Name': 'Alice', '123field': 'test', 'valid_key': 'keep'})])
            >>> s.snakify()
            ScenarioList([Scenario({'user_name': 'Alice', '_123field': 'test', 'valid_key': 'keep'})])
        """
        from .scenario_snakifier import ScenarioSnakifier

        replacement_dict = ScenarioSnakifier(self).create_key_mapping()
        return RenameFieldsEvent(rename_map=tuple(replacement_dict.items()))

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

    @event
    def chunk(
        self,
        field,
        num_words: Optional[int] = None,
        num_lines: Optional[int] = None,
        include_original=False,
        hash_original=False,
    ) -> ReplaceAllEntriesEvent:
        """Chunk the scenarios based on a field (in-place).

        Example:

        >>> s = ScenarioList([Scenario({'text': 'The quick brown fox jumps over the lazy dog.'})])
        >>> s.chunk('text', num_words=3)
        >>> len(s)
        3
        """
        new_entries = []
        for scenario in self.data:
            # Use the Scenario's chunk method to get replacement scenarios
            replacement_scenarios = scenario.chunk(
                field,
                num_words=num_words,
                num_lines=num_lines,
                include_original=include_original,
                hash_original=hash_original,
            )
            # Convert each scenario to a dict for the event
            for s in replacement_scenarios:
                new_entries.append(self._codec.encode(s))
        return ReplaceAllEntriesEvent(entries=tuple(new_entries))

    @event
    def choose_k(self, k: int, order_matters: bool = False) -> ReplaceAllEntriesEvent:
        """Create all choose-k selections with suffixed keys (in-place).

        The input must be a ScenarioList where each scenario has exactly one key, e.g.:
        ``ScenarioList.from_list('item', ['a', 'b', 'c'])``.

        Example:
            >>> s = ScenarioList.from_list('x', ['a', 'b', 'c'])
            >>> s.choose_k(2)
            >>> len(s)
            3

        Args:
            k: Number of items to choose for each scenario.
            order_matters: If True, use ordered selections (permutations). If False, use
                unordered selections (combinations).

        Returns:
            ReplaceAllEntriesEvent: Event with choose-k combinations.
        """
        new_entries = [
            dict(scenario)
            for scenario in self._iter_choose_k(k=k, order_matters=order_matters)
        ]
        return ReplaceAllEntriesEvent(entries=tuple(new_entries))

    def _iter_choose_k(self, k: int, order_matters: bool = False):
        """Delegate generator for choose-k to the ScenarioCombinator module.

        Returns a generator yielding `Scenario` instances.
        """
        from importlib import import_module

        ScenarioCombinator = import_module(
            "edsl.scenarios.scenario_combinator"
        ).ScenarioCombinator
        return ScenarioCombinator.iter_choose_k(self, k=k, order_matters=order_matters)

    @event
    def collapse(
        self,
        field: str,
        separator: Optional[str] = None,
        prefix: str = "",
        postfix: str = "",
        add_count: bool = False,
    ) -> ReplaceAllEntriesEvent:
        """Collapse rows by collecting values of one field (in-place).

        Groups by all fields other than ``field`` and aggregates the values of
        ``field`` either as a list or as a string joined with ``separator``.
        Optionally appends a count of collapsed rows.

        Args:
            field: Field to collect.
            separator: If provided, join with this string; otherwise keep as list.
            prefix: Optional prefix applied to each value before join.
            postfix: Optional postfix applied to each value before join.
            add_count: If True, add "num_collapsed_rows" to each Scenario.

        Returns:
            ReplaceAllEntriesEvent: Event with collapsed entries.
        """
        from collections import defaultdict
        
        # Group scenarios by all fields except the target field
        groups = defaultdict(list)
        for scenario in self.data:
            # Create key from all fields except the one being collapsed
            key_dict = {k: v for k, v in scenario.items() if k != field}
            # Make key hashable
            key = tuple(sorted(key_dict.items()))
            groups[key].append(scenario.get(field))
        
        # Build collapsed entries
        new_entries = []
        for key, values in groups.items():
            new_entry = dict(key)
            
            # Apply prefix/postfix and format values
            formatted_values = [f"{prefix}{v}{postfix}" for v in values]
            
            if separator is not None:
                new_entry[field] = separator.join(str(v) for v in formatted_values)
            else:
                new_entry[field] = formatted_values
            
            if add_count:
                new_entry["num_collapsed_rows"] = len(values)
            
            new_entries.append(new_entry)
        
        return ReplaceAllEntriesEvent(entries=tuple(new_entries))

    @event
    def create_comparisons(
        self,
        bidirectional: bool = False,
        num_options: int = 2,
        option_prefix: str = "option_",
        use_alphabet: bool = False,
    ) -> ReplaceAllEntriesEvent:
        """Generate pairwise or N-way comparison scenarios (in-place).

        Produces new scenarios that bundle multiple original scenarios under
        option keys (e.g., "option_1", "option_2", ... or letters when
        ``use_alphabet`` is True). Can generate ordered pairs when
        ``bidirectional`` is True.

        Args:
            bidirectional: If True, generate ordered comparisons (permutations).
            num_options: Number of options per comparison (>= 2).
            option_prefix: Prefix for option field names when not using alphabet.
            use_alphabet: If True, label options with A, B, C, ...

        Returns:
            ReplaceAllEntriesEvent: Event with comparison scenarios.

        Raises:
            ValueError: For invalid num_options or alphabet size overflow.
        """
        import itertools
        import string
        
        if num_options < 2:
            raise ValueError("num_options must be at least 2")
        
        if use_alphabet and num_options > 26:
            raise ValueError("num_options cannot exceed 26 when use_alphabet is True")
        
        # Get all scenarios as dicts
        scenarios = list(self.data)
        
        # Generate combinations or permutations
        if bidirectional:
            combos = itertools.permutations(range(len(scenarios)), num_options)
        else:
            combos = itertools.combinations(range(len(scenarios)), num_options)
        
        # Build comparison entries
        new_entries = []
        for combo in combos:
            new_entry = {}
            for i, idx in enumerate(combo):
                if use_alphabet:
                    key = string.ascii_uppercase[i]
                else:
                    key = f"{option_prefix}{i + 1}"
                # Flatten the scenario into the comparison entry with prefix
                for field, value in scenarios[idx].items():
                    new_entry[f"{key}_{field}"] = value
            new_entries.append(new_entry)
        
        return ReplaceAllEntriesEvent(entries=tuple(new_entries))

    @event
    def replace_values(self, replacements: dict) -> ReplaceValuesEvent:
        """
        Replace values in scenarios according to the provided replacement dictionary (in-place).

        Args:
            replacements (dict): Dictionary of values to replace {old_value: new_value}

        Returns:
            ReplaceValuesEvent: Event to replace values.

        Examples:
            >>> scenarios = ScenarioList([
            ...     Scenario({'a': 'nan', 'b': 1}),
            ...     Scenario({'a': 2, 'b': 'nan'})
            ... ])
            >>> scenarios.replace_values({'nan': None})
            >>> print(scenarios)
            ScenarioList([Scenario({'a': None, 'b': 1}), Scenario({'a': 2, 'b': None})])
        """
        return ReplaceValuesEvent(replacements=tuple(replacements.items()))

    @event
    def fillna(self, value: Any = "") -> FillNaEvent:
        """
        Fill None/NaN values in all scenarios with a specified value (in-place).

        This method is equivalent to pandas' df.fillna() functionality, allowing you to
        replace None, NaN, or other null-like values across all scenarios in the list.

        Args:
            value: The value to use for filling None/NaN values. Defaults to empty string "".

        Returns:
            FillNaEvent: Event to fill NA values.

        Examples:
            >>> scenarios = ScenarioList([
            ...     Scenario({'a': None, 'b': 1, 'c': 'hello'}),
            ...     Scenario({'a': 2, 'b': None, 'c': None}),
            ...     Scenario({'a': None, 'b': 3, 'c': 'world'})
            ... ])
            >>> scenarios.fillna()
            >>> print(scenarios)
            ScenarioList([Scenario({'a': '', 'b': 1, 'c': 'hello'}), Scenario({'a': 2, 'b': '', 'c': ''}), Scenario({'a': '', 'b': 3, 'c': 'world'})])
            >>> scenarios2 = ScenarioList([Scenario({'a': None})])
            >>> scenarios2.fillna(value="N/A")
            >>> print(scenarios2)
            ScenarioList([Scenario({'a': 'N/A'})])
        """
        return FillNaEvent(fill_value=value)

    @event
    def filter_na(self, fields: Union[str, List[str]] = "*") -> RemoveRowsEvent:
        """
        Remove scenarios where specified fields contain None or NaN values (in-place).

        This method filters out scenarios that have null/NaN values in the specified
        fields. It's similar to pandas' dropna() functionality. Values considered as
        NA include: None, float('nan'), and string representations like 'nan', 'none', 'null'.

        Args:
            fields: Field name(s) to check for NA values. Can be:
                    - "*" (default): Check all fields in each scenario
                    - A single field name (str): Check only that field
                    - A list of field names: Check all specified fields

                    A scenario is kept only if NONE of the specified fields contain NA values.

        Returns:
            RemoveRowsEvent: Event containing indices of rows with NA values to remove.

        Examples:
            Remove scenarios with any NA values in any field:
            >>> scenarios = ScenarioList([
            ...     Scenario({'a': 1, 'b': 2}),
            ...     Scenario({'a': None, 'b': 3}),
            ...     Scenario({'a': 4, 'b': 5})
            ... ])
            >>> scenarios.filter_na()
            >>> len(scenarios)
            2

            Remove scenarios with NA in specific field:
            >>> scenarios = ScenarioList([
            ...     Scenario({'name': 'Alice', 'age': 30}),
            ...     Scenario({'name': None, 'age': 25}),
            ...     Scenario({'name': 'Bob', 'age': None})
            ... ])
            >>> scenarios.filter_na('name')
            >>> len(scenarios)
            2
        """
        import math

        def is_na(val):
            """Check if a value is considered NA (None or NaN)."""
            if val is None:
                return True
            # Check for float NaN
            if isinstance(val, float) and math.isnan(val):
                return True
            # Check for string representations of null values
            if hasattr(val, "__str__"):
                str_val = str(val).lower()
                if str_val in ["nan", "none", "null"]:
                    return True
            return False

        # Determine which fields to check
        if fields == "*":
            # Check all fields - need to collect all unique keys across scenarios
            check_fields = set()
            for scenario in self:
                check_fields.update(scenario.keys())
            check_fields = list(check_fields)
        elif isinstance(fields, str):
            check_fields = [fields]
        else:
            check_fields = list(fields)

        # Find indices of scenarios with NA values
        indices_to_remove = []
        for i, scenario in enumerate(self.data):
            has_na = False
            for field in check_fields:
                if field in scenario:
                    if is_na(scenario[field]):
                        has_na = True
                        break
            if has_na:
                indices_to_remove.append(i)

        return RemoveRowsEvent(indices=tuple(indices_to_remove))


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
