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
from io import StringIO
import inspect
from collections import UserList, defaultdict
from collections.abc import Iterable

from simpleeval import EvalWithCompoundTypes, NameNotDefined  # type: ignore
from tabulate import tabulate_formats

try:
    from typing import TypeAlias
except ImportError:
    from typing_extensions import TypeAlias

if TYPE_CHECKING:
    from urllib.parse import ParseResult
    from ..dataset import Dataset
    from ..jobs import Jobs
    from ..surveys import Survey
    from ..questions import QuestionBase


from ..base import Base
from ..utilities import remove_edsl_version, sanitize_string, is_valid_variable_name, dict_hash
from ..dataset import ScenarioListOperationsMixin

from .exceptions import ScenarioError
from .scenario import Scenario
from .scenario_list_pdf_tools import PdfTools
from .directory_scanner import DirectoryScanner
from .file_store import FileStore


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

class ScenarioList(Base, UserList, ScenarioListOperationsMixin):
    """
    A collection of Scenario objects with advanced operations for manipulation and analysis.
    
    ScenarioList extends Python's UserList to provide specialized functionality for
    working with collections of Scenario objects. It inherits from Base to integrate
    with EDSL's object model and from ScenarioListOperationsMixin to provide
    powerful data manipulation capabilities.
    
    The class provides methods for filtering, sorting, joining, transforming, and
    analyzing collections of Scenarios. It's designed to work seamlessly with other
    EDSL components like Surveys, Jobs, and Questions.
    
    Attributes:
        data (list): The underlying list of Scenario objects.
        codebook (dict): Optional metadata describing the fields in the scenarios.
        
    Examples:
        Create a ScenarioList from Scenario objects:
        >>> from edsl.scenarios import Scenario, ScenarioList
        >>> s1 = Scenario({"product": "apple", "price": 1.99})
        >>> s2 = Scenario({"product": "banana", "price": 0.99})
        >>> sl = ScenarioList([s1, s2])
        
        Filter scenarios based on a condition:
        >>> cheap_fruits = sl.filter("price < 1.50")
        >>> len(cheap_fruits)
        1
        >>> cheap_fruits[0]["product"]
        'banana'
        
        Add a new column based on existing data:
        >>> sl_with_tax = sl.mutate("tax = price * 0.08")
        >>> sl_with_tax[0]["tax"]
        0.1592
    """

    __documentation__ = (
        "https://docs.expectedparrot.com/en/latest/scenarios.html#scenariolist"
    )

    def __init__(
        self, data: Optional[list] = None, codebook: Optional[dict[str, str]] = None
    ):
        """
        Initialize a new ScenarioList with optional data and codebook.
        
        Args:
            data: A list of Scenario objects. If None, an empty list is used.
            codebook: A dictionary mapping field names to descriptions or metadata.
                     Used for documentation and to provide context for fields.
                     
        Examples:
            >>> sl = ScenarioList()  # Empty list
            >>> s1 = Scenario({"product": "apple"})
            >>> s2 = Scenario({"product": "banana"})
            >>> sl = ScenarioList([s1, s2])  # With data
            
            >>> # With a codebook
            >>> codebook = {"product": "Fruit name", "price": "Price in USD"}
            >>> sl = ScenarioList([s1, s2], codebook=codebook)
        """
        if data is not None:
            super().__init__(data)
        else:
            super().__init__([])
        self.codebook = codebook or {}

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
        """
        return ScenarioList(list(set(self)))

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
        return any([scenario.has_jinja_braces for scenario in self])

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
        return ScenarioList([scenario._convert_jinja_braces() for scenario in self])

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
        new_scenarios = []

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

        return ScenarioList(new_scenarios, codebook)

    def unpivot(
        self,
        id_vars: Optional[List[str]] = None,
        value_vars: Optional[List[str]] = None,
    ) -> ScenarioList:
        """
        Unpivot the ScenarioList, allowing for id variables to be specified.

        Parameters:
        id_vars (list): Fields to use as identifier variables (kept in each entry)
        value_vars (list): Fields to unpivot. If None, all fields not in id_vars will be used.

        Example:
        >>> s = ScenarioList([
        ...     Scenario({'id': 1, 'year': 2020, 'a': 10, 'b': 20}),
        ...     Scenario({'id': 2, 'year': 2021, 'a': 15, 'b': 25})
        ... ])
        >>> s.unpivot(id_vars=['id', 'year'], value_vars=['a', 'b'])
        ScenarioList([Scenario({'id': 1, 'year': 2020, 'variable': 'a', 'value': 10}), Scenario({'id': 1, 'year': 2020, 'variable': 'b', 'value': 20}), Scenario({'id': 2, 'year': 2021, 'variable': 'a', 'value': 15}), Scenario({'id': 2, 'year': 2021, 'variable': 'b', 'value': 25})])
        """
        if id_vars is None:
            id_vars = []
        if value_vars is None:
            value_vars = [field for field in self[0].keys() if field not in id_vars]

        new_scenarios = []
        for scenario in self:
            for var in value_vars:
                new_scenario = {id_var: scenario[id_var] for id_var in id_vars}
                new_scenario["variable"] = var
                new_scenario["value"] = scenario[var]
                new_scenarios.append(Scenario(new_scenario))

        return ScenarioList(new_scenarios)

    def sem_filter(self, language_predicate: str) -> ScenarioList:
        """Filter the ScenarioList based on a language predicate.

        :param language_predicate: The language predicate to use.

        Inspired by:
        @misc{patel2024semanticoperators,
            title={Semantic Operators: A Declarative Model for Rich, AI-based Analytics Over Text Data},
            author={Liana Patel and Siddharth Jha and Parth Asawa and Melissa Pan and Carlos Guestrin and Matei Zaharia},
            year={2024},
            eprint={2407.11418},
            archivePrefix={arXiv},
            primaryClass={cs.DB},
            url={https://arxiv.org/abs/2407.11418},
            }
        """
        from ..questions import QuestionYesNo

        new_scenario_list = self.duplicate()
        q = QuestionYesNo(
            question_text=language_predicate, question_name="binary_outcome"
        )
        results = q.by(new_scenario_list).run(verbose=False)
        new_scenario_list = new_scenario_list.add_list(
            "criteria", results.select("binary_outcome").to_list()
        )
        return new_scenario_list.filter("criteria == 'Yes'").drop("criteria")

    def pivot(
        self,
        id_vars: List[str] = None,
        var_name="variable",
        value_name="value",
    ) -> ScenarioList:
        """
        Pivot the ScenarioList from long to wide format.

        Parameters:
        id_vars (list): Fields to use as identifier variables
        var_name (str): Name of the variable column (default: 'variable')
        value_name (str): Name of the value column (default: 'value')

        Example:
        >>> s = ScenarioList([
        ...     Scenario({'id': 1, 'year': 2020, 'variable': 'a', 'value': 10}),
        ...     Scenario({'id': 1, 'year': 2020, 'variable': 'b', 'value': 20}),
        ...     Scenario({'id': 2, 'year': 2021, 'variable': 'a', 'value': 15}),
        ...     Scenario({'id': 2, 'year': 2021, 'variable': 'b', 'value': 25})
        ... ])
        >>> s.pivot(id_vars=['id', 'year'])
        ScenarioList([Scenario({'id': 1, 'year': 2020, 'a': 10, 'b': 20}), Scenario({'id': 2, 'year': 2021, 'a': 15, 'b': 25})])
        """
        pivoted_dict = {}

        for scenario in self:
            # Create a tuple of id values to use as a key
            id_key = tuple(scenario[id_var] for id_var in id_vars)

            # If this combination of id values hasn't been seen before, initialize it
            if id_key not in pivoted_dict:
                pivoted_dict[id_key] = {id_var: scenario[id_var] for id_var in id_vars}

            # Add the variable-value pair to the dict
            variable = scenario[var_name]
            value = scenario[value_name]
            pivoted_dict[id_key][variable] = value

        # Convert the dict of dicts to a list of Scenarios
        pivoted_scenarios = [
            Scenario(dict(zip(id_vars, id_key), **values))
            for id_key, values in pivoted_dict.items()
        ]

        return ScenarioList(pivoted_scenarios)

    def group_by(
        self, id_vars: List[str], variables: List[str], func: Callable
    ) -> ScenarioList:
        """
        Group the ScenarioList by id_vars and apply a function to the specified variables.

        :param id_vars: Fields to use as identifier variables
        :param variables: Fields to group and aggregate
        :param func: Function to apply to the grouped variables

        Returns:
        ScenarioList: A new ScenarioList with the grouped and aggregated results

        Example:
        >>> def avg_sum(a, b):
        ...     return {'avg_a': sum(a) / len(a), 'sum_b': sum(b)}
        >>> s = ScenarioList([
        ...     Scenario({'group': 'A', 'year': 2020, 'a': 10, 'b': 20}),
        ...     Scenario({'group': 'A', 'year': 2021, 'a': 15, 'b': 25}),
        ...     Scenario({'group': 'B', 'year': 2020, 'a': 12, 'b': 22}),
        ...     Scenario({'group': 'B', 'year': 2021, 'a': 17, 'b': 27})
        ... ])
        >>> s.group_by(id_vars=['group'], variables=['a', 'b'], func=avg_sum)
        ScenarioList([Scenario({'group': 'A', 'avg_a': 12.5, 'sum_b': 45}), Scenario({'group': 'B', 'avg_a': 14.5, 'sum_b': 49})])
        """
        # Check if the function is compatible with the specified variables
        func_params = inspect.signature(func).parameters
        if len(func_params) != len(variables):
            raise ScenarioError(
                f"Function {func.__name__} expects {len(func_params)} arguments, but {len(variables)} variables were provided"
            )

        # Group the scenarios
        grouped: dict[str, list] = defaultdict(lambda: defaultdict(list))
        for scenario in self:
            key = tuple(scenario[id_var] for id_var in id_vars)
            for var in variables:
                grouped[key][var].append(scenario[var])

        # Apply the function to each group
        result = []
        for key, group in grouped.items():
            try:
                aggregated = func(*[group[var] for var in variables])
            except Exception as e:
                raise ScenarioError(f"Error applying function to group {key}: {str(e)}")

            if not isinstance(aggregated, dict):
                raise ScenarioError(
                    f"Function {func.__name__} must return a dictionary"
                )

            new_scenario = dict(zip(id_vars, key))
            new_scenario.update(aggregated)
            result.append(Scenario(new_scenario))

        return ScenarioList(result)

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

        return set.union(*[set(s.keys()) for s in self])

    def __hash__(self) -> int:
        """Return the hash of the ScenarioList.

        >>> s = ScenarioList.example()
        >>> hash(s)
        1262252885757976162
        """
        return dict_hash(self.to_dict(sort=True, add_edsl_version=False))

    def __eq__(self, other: Any) -> bool:
        return hash(self) == hash(other)

    def __repr__(self):
        return f"ScenarioList({self.data})"

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

        new_sl = []
        for s1, s2 in list(product(self, other)):
            new_sl.append(s1 + s2)
        return ScenarioList(new_sl)

    def times(self, other: ScenarioList) -> ScenarioList:
        """Takes the cross product of two ScenarioLists.

        Example:

        >>> s1 = ScenarioList([Scenario({'a': 1}), Scenario({'a': 2})])
        >>> s2 = ScenarioList([Scenario({'b': 1}), Scenario({'b': 2})])
        >>> s1.times(s2)
        ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2}), Scenario({'a': 2, 'b': 1}), Scenario({'a': 2, 'b': 2})])
        """
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
        >>> s.sample(3, seed = "edsl")
        ScenarioList([Scenario({'a': 2}), Scenario({'a': 1}), Scenario({'a': 3})])
        """
        if seed:
            random.seed(seed)

        sl = self.duplicate()
        return ScenarioList(random.sample(sl.data, n))

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

    def _concatenate(self, fields: List[str], output_type: str = "string", separator: str = ";", new_field_name: Optional[str] = None) -> ScenarioList:
        """Private method to handle concatenation logic for different output types.
        
        :param fields: The fields to concatenate.
        :param output_type: The type of output ("string", "list", or "set").
        :param separator: The separator to use for string concatenation.
        :param new_field_name: Optional custom name for the concatenated field.
                             If None, defaults to "concat_field1_field2_..."
        
        Returns:
            ScenarioList: A new ScenarioList with concatenated fields.
        """
        # Check if fields is a string and raise an exception
        if isinstance(fields, str):
            raise ScenarioError(
                f"The 'fields' parameter must be a list of field names, not a string. Got '{fields}'."
            )
            
        new_scenarios = []
        for scenario in self:
            new_scenario = scenario.copy()
            values = []
            for field in fields:
                if field in new_scenario:
                    values.append(new_scenario[field])
                    del new_scenario[field]

            field_name = new_field_name if new_field_name is not None else f"concat_{'_'.join(fields)}"
            
            if output_type == "string":
                # Convert all values to strings and join with separator
                new_scenario[field_name] = separator.join(str(v) for v in values)
            elif output_type == "list":
                # Keep as a list
                new_scenario[field_name] = values
            elif output_type == "set":
                # Convert to a set (removes duplicates)
                new_scenario[field_name] = set(values)
            else:
                from .exceptions import ValueScenarioError
                raise ValueScenarioError(f"Invalid output_type: {output_type}. Must be 'string', 'list', or 'set'.")
                
            new_scenarios.append(new_scenario)

        return ScenarioList(new_scenarios)

    def concatenate(self, fields: List[str], separator: str = ";", new_field_name: Optional[str] = None) -> ScenarioList:
        """Concatenate specified fields into a single string field.

        :param fields: The fields to concatenate.
        :param separator: The separator to use.
        :param new_field_name: Optional custom name for the concatenated field.

        Returns:
            ScenarioList: A new ScenarioList with concatenated fields.

        Example:
            >>> s = ScenarioList([Scenario({'a': 1, 'b': 2, 'c': 3}), Scenario({'a': 4, 'b': 5, 'c': 6})])
            >>> s.concatenate(['a', 'b', 'c'])
            ScenarioList([Scenario({'concat_a_b_c': '1;2;3'}), Scenario({'concat_a_b_c': '4;5;6'})])
            >>> s.concatenate(['a', 'b', 'c'], new_field_name='combined')
            ScenarioList([Scenario({'combined': '1;2;3'}), Scenario({'combined': '4;5;6'})])
        """
        return self._concatenate(fields, output_type="string", separator=separator, new_field_name=new_field_name)

    def concatenate_to_list(self, fields: List[str], new_field_name: Optional[str] = None) -> ScenarioList:
        """Concatenate specified fields into a single list field.

        :param fields: The fields to concatenate.
        :param new_field_name: Optional custom name for the concatenated field.

        Returns:
            ScenarioList: A new ScenarioList with fields concatenated into a list.

        Example:
            >>> s = ScenarioList([Scenario({'a': 1, 'b': 2, 'c': 3}), Scenario({'a': 4, 'b': 5, 'c': 6})])
            >>> s.concatenate_to_list(['a', 'b', 'c'])
            ScenarioList([Scenario({'concat_a_b_c': [1, 2, 3]}), Scenario({'concat_a_b_c': [4, 5, 6]})])
            >>> s.concatenate_to_list(['a', 'b', 'c'], new_field_name='values')
            ScenarioList([Scenario({'values': [1, 2, 3]}), Scenario({'values': [4, 5, 6]})])
        """
        return self._concatenate(fields, output_type="list", new_field_name=new_field_name)

    def concatenate_to_set(self, fields: List[str], new_field_name: Optional[str] = None) -> ScenarioList:
        """Concatenate specified fields into a single set field.

        :param fields: The fields to concatenate.
        :param new_field_name: Optional custom name for the concatenated field.

        Returns:
            ScenarioList: A new ScenarioList with fields concatenated into a set.

        Example:
            >>> s = ScenarioList([Scenario({'a': 1, 'b': 2, 'c': 3}), Scenario({'a': 4, 'b': 5, 'c': 6})])
            >>> s.concatenate_to_set(['a', 'b', 'c'])
            ScenarioList([Scenario({'concat_a_b_c': {1, 2, 3}}), Scenario({'concat_a_b_c': {4, 5, 6}})])
            >>> s.concatenate_to_set(['a', 'b', 'c'], new_field_name='unique_values')
            ScenarioList([Scenario({'unique_values': {1, 2, 3}}), Scenario({'unique_values': {4, 5, 6}})])
        """
        return self._concatenate(fields, output_type="set", new_field_name=new_field_name)

    def unpack_dict(
        self, field: str, prefix: Optional[str] = None, drop_field: bool = False
    ) -> ScenarioList:
        """Unpack a dictionary field into separate fields.

        :param field: The field to unpack.
        :param prefix: An optional prefix to add to the new fields.
        :param drop_field: Whether to drop the original field.

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': {'c': 2, 'd': 3}})])
        >>> s.unpack_dict('b')
        ScenarioList([Scenario({'a': 1, 'b': {'c': 2, 'd': 3}, 'c': 2, 'd': 3})])
        >>> s.unpack_dict('b', prefix='new_')
        ScenarioList([Scenario({'a': 1, 'b': {'c': 2, 'd': 3}, 'new_c': 2, 'new_d': 3})])
        """
        new_scenarios = []
        for scenario in self:
            new_scenario = scenario.copy()
            for key, value in scenario[field].items():
                if prefix:
                    new_scenario[prefix + key] = value
                else:
                    new_scenario[key] = value
            if drop_field:
                new_scenario.pop(field)
            new_scenarios.append(new_scenario)
        return ScenarioList(new_scenarios)

    def transform(
        self, field: str, func: Callable, new_name: Optional[str] = None
    ) -> ScenarioList:
        """Transform a field using a function.

        :param field: The field to transform.
        :param func: The function to apply to the field.
        :param new_name: An optional new name for the transformed field.

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 2}), Scenario({'a': 1, 'b': 1})])
        >>> s.transform('b', lambda x: x + 1)
        ScenarioList([Scenario({'a': 1, 'b': 3}), Scenario({'a': 1, 'b': 2})])

        """
        new_scenarios = []
        for scenario in self:
            new_scenario = scenario.copy()
            new_scenario[new_name or field] = func(scenario[field])
            new_scenarios.append(new_scenario)
        return ScenarioList(new_scenarios)

    def mutate(
        self, new_var_string: str, functions_dict: Optional[dict[str, Callable]] = None
    ) -> ScenarioList:
        """
        Return a new ScenarioList with a new variable added.

        :param new_var_string: A string with the new variable assignment.
        :param functions_dict: A dictionary of functions to use in the assignment.

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 2}), Scenario({'a': 1, 'b': 1})])
        >>> s.mutate("c = a + b")
        ScenarioList([Scenario({'a': 1, 'b': 2, 'c': 3}), Scenario({'a': 1, 'b': 1, 'c': 2})])

        """
        if "=" not in new_var_string:
            raise ScenarioError(
                f"Mutate requires an '=' in the string, but '{new_var_string}' doesn't have one."
            )
        raw_var_name, expression = new_var_string.split("=", 1)
        var_name = raw_var_name.strip()

        if not is_valid_variable_name(var_name):
            raise ScenarioError(f"{var_name} is not a valid variable name.")

        # create the evaluator
        functions_dict = functions_dict or {}

        def create_evaluator(scenario) -> EvalWithCompoundTypes:
            return EvalWithCompoundTypes(names=scenario, functions=functions_dict)

        def new_scenario(old_scenario: Scenario, var_name: str) -> Scenario:
            evaluator = create_evaluator(old_scenario)
            value = evaluator.eval(expression)
            new_s = old_scenario.copy()
            new_s[var_name] = value
            return new_s

        try:
            new_data = [new_scenario(s, var_name) for s in self]
        except Exception as e:
            raise ScenarioError(f"Error in mutate. Exception:{e}")

        return ScenarioList(new_data)

    def order_by(self, *fields: str, reverse: bool = False) -> ScenarioList:
        """Order the scenarios by one or more fields.

        :param fields: The fields to order by.
        :param reverse: Whether to reverse the order.
        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 2}), Scenario({'a': 1, 'b': 1})])
        >>> s.order_by('b', 'a')
        ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        """

        def get_sort_key(scenario: Any) -> tuple:
            return tuple(scenario[field] for field in fields)

        return ScenarioList(sorted(self, key=get_sort_key, reverse=reverse))

    def duplicate(self) -> ScenarioList:
        """Return a copy of the ScenarioList.

        >>> sl = ScenarioList.example()
        >>> sl_copy = sl.duplicate()
        >>> sl == sl_copy
        True
        >>> sl is sl_copy
        False
        """
        return ScenarioList([scenario.copy() for scenario in self])

    def filter(self, expression: str) -> ScenarioList:
        """
        Filter a list of scenarios based on an expression.

        :param expression: The expression to filter by.

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        >>> s.filter("b == 2")
        ScenarioList([Scenario({'a': 1, 'b': 2})])
        """
        sl = self.duplicate()
        base_keys = set(self[0].keys())
        keys = set()
        for scenario in sl:
            keys.update(scenario.keys())
        if keys != base_keys:
            import warnings

            warnings.warn(
                "Ragged ScenarioList detected (different keys for different scenario entries). This may cause unexpected behavior."
            )

        def create_evaluator(scenario: Scenario):
            """Create an evaluator for the given result.
            The 'combined_dict' is a mapping of all values for that Result object.
            """
            return EvalWithCompoundTypes(names=scenario)

        try:
            # iterates through all the results and evaluates the expression
            new_data = []
            for scenario in sl:
                if create_evaluator(scenario).eval(expression):
                    new_data.append(scenario)
        except NameNotDefined as e:
            available_fields = ", ".join(self.data[0].keys() if self.data else [])
            raise ScenarioError(
                f"Error in filter: '{e}'\n"
                f"The expression '{expression}' refers to a field that does not exist.\n"
                f"Scenario: {scenario}\n"
                f"Available fields: {available_fields}\n"
                "Check your filter expression or consult the documentation: "
                "https://docs.expectedparrot.com/en/latest/scenarios.html#module-edsl.scenarios.Scenario"
            ) from None
        except Exception as e:
            raise ScenarioError(f"Error in filter. Exception:{e}")

        return ScenarioList(new_data)

    def from_urls(
        self, urls: list[str], field_name: Optional[str] = "text"
    ) -> ScenarioList:
        """Create a ScenarioList from a list of URLs.

        :param urls: A list of URLs.
        :param field_name: The name of the field to store the text from the URLs.

        """
        return ScenarioList([Scenario.from_url(url, field_name) for url in urls])

    def select(self, *fields: str) -> ScenarioList:
        """
        Selects scenarios with only the references fields.

        :param fields: The fields to select.

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        >>> s.select('a')
        ScenarioList([Scenario({'a': 1}), Scenario({'a': 1})])
        """
        from .scenario_selector import ScenarioSelector

        return ScenarioSelector(self).select(*fields)

    def drop(self, *fields: str) -> ScenarioList:
        """Drop fields from the scenarios.

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        >>> s.drop('a')
        ScenarioList([Scenario({'b': 1}), Scenario({'b': 2})])
        """
        sl = self.duplicate()
        return ScenarioList([scenario.drop(fields) for scenario in sl])

    def keep(self, *fields: str) -> ScenarioList:
        """Keep only the specified fields in the scenarios.

        :param fields: The fields to keep.

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        >>> s.keep('a')
        ScenarioList([Scenario({'a': 1}), Scenario({'a': 1})])
        """
        sl = self.duplicate()
        return ScenarioList([scenario.keep(fields) for scenario in sl])

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
        # Handle default case - use current directory
        if path is None:
            directory_path = os.getcwd()
            pattern = None
        else:
            # Special handling for "**" pattern which indicates recursive scanning
            has_recursive_pattern = '**' in path if path else False
            
            # Check if path contains any wildcard
            if path and ('*' in path):
                # Handle "**/*.ext" pattern - find the directory part before the **
                if has_recursive_pattern:
                    # Extract the base directory by finding the part before **
                    parts = path.split('**')
                    if parts and parts[0]:
                        # Remove trailing slash if any
                        directory_path = parts[0].rstrip('/')
                        if not directory_path:
                            directory_path = os.getcwd()
                        # Get the pattern after **
                        pattern = parts[1] if len(parts) > 1 else None
                        if pattern and pattern.startswith('/'):
                            pattern = pattern[1:]  # Remove leading slash
                    else:
                        directory_path = os.getcwd()
                        pattern = None
                # Handle case where path is just a pattern (e.g., "*.py")
                elif os.path.dirname(path) == '':
                    directory_path = os.getcwd()
                    pattern = os.path.basename(path)
                else:
                    # Split into directory and pattern
                    directory_path = os.path.dirname(path)
                    if not directory_path:
                        directory_path = os.getcwd()
                    pattern = os.path.basename(path)
            else:
                # Path is a directory with no pattern
                directory_path = path
                pattern = None
                
        # Ensure directory exists
        if not os.path.isdir(directory_path):
            from .exceptions import FileNotFoundScenarioError
            raise FileNotFoundScenarioError(f"Directory not found: {directory_path}")
        
        # Create a DirectoryScanner for the directory
        scanner = DirectoryScanner(directory_path)
        
        # Configure wildcard pattern filtering
        suffix_allow_list = None
        example_suffix = None
        
        if pattern:
            if pattern.startswith('*.'):
                # Simple extension filter (e.g., "*.py")
                suffix_allow_list = [pattern[2:]]
            elif '*' in pattern:
                # Other wildcard patterns
                example_suffix = pattern
            else:
                # Handle simple non-wildcard pattern (exact match)
                example_suffix = pattern
        
        # Use scanner to find files and create FileStore objects
        file_stores = scanner.scan(
            factory=lambda path: FileStore(path),
            recursive=recursive,
            suffix_allow_list=suffix_allow_list,
            example_suffix=example_suffix
        )
        
        # Convert FileStore objects to Scenario objects with the specified key
        scenarios = [Scenario({key_name: file_store}) for file_store in file_stores]
        
        return cls(scenarios)
                
    @classmethod
    def from_list(
        cls, name: str, values: list, func: Optional[Callable] = None
    ) -> ScenarioList:
        """Create a ScenarioList from a list of values.

        :param name: The name of the field.
        :param values: The list of values.
        :param func: An optional function to apply to the values.

        Example:

        >>> ScenarioList.from_list('name', ['Alice', 'Bob'])
        ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
        """
        if not func:
            def identity(x):
                return x
            func = identity
        return cls([Scenario({name: func(value)}) for value in values])

    def table(
        self,
        *fields: str,
        tablefmt: Optional[TableFormat] = None,
        pretty_labels: Optional[dict[str, str]] = None,
    ) -> str:
        """Return the ScenarioList as a table."""


        if tablefmt is not None and tablefmt not in tabulate_formats:
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

        :param new_order: The new order of the keys.

        Example:

        # Example:
        # s = ScenarioList([Scenario({'a': 1, 'b': 2}), Scenario({'a': 3, 'b': 4})])
        # s.reorder_keys(['b', 'a'])  # Returns a new ScenarioList with reordered keys
        # Attempting s.reorder_keys(['a', 'b', 'c']) would fail as 'c' is not a valid key
        """
        assert set(new_order) == set(self.parameters)

        new_scenarios = []
        for scenario in self:
            new_scenario = Scenario({key: scenario[key] for key in new_order})
            new_scenarios.append(new_scenario)
        return ScenarioList(new_scenarios)

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

        keys = list(self[0].keys())
        for scenario in self:
            new_keys = list(scenario.keys())
            if new_keys != keys:
                keys = list(set(keys + new_keys))
        data = [
            {key: [scenario.get(key, None) for scenario in self.data]} for key in keys
        ]
        return Dataset(data)

    def unpack(
        self, field: str, new_names: Optional[List[str]] = None, keep_original=True
    ) -> ScenarioList:
        """Unpack a field into multiple fields.

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': [2, True]}), Scenario({'a': 3, 'b': [3, False]})])
        >>> s.unpack('b')
        ScenarioList([Scenario({'a': 1, 'b': [2, True], 'b_0': 2, 'b_1': True}), Scenario({'a': 3, 'b': [3, False], 'b_0': 3, 'b_1': False})])
        >>> s.unpack('b', new_names=['c', 'd'], keep_original=False)
        ScenarioList([Scenario({'a': 1, 'c': 2, 'd': True}), Scenario({'a': 3, 'c': 3, 'd': False})])

        """
        new_names = new_names or [f"{field}_{i}" for i in range(len(self[0][field]))]
        new_scenarios = []
        for scenario in self:
            new_scenario = scenario.copy()
            if len(new_names) == 1:
                new_scenario[new_names[0]] = scenario[field]
            else:
                for i, new_name in enumerate(new_names):
                    new_scenario[new_name] = scenario[field][i]

            if not keep_original:
                del new_scenario[field]
            new_scenarios.append(new_scenario)
        return ScenarioList(new_scenarios)

    @classmethod
    def from_list_of_tuples(self, *names: str, values: List[tuple]) -> ScenarioList:
        sl = ScenarioList.from_list(names[0], [value[0] for value in values])
        for index, name in enumerate(names[1:]):
            sl = sl.add_list(name, [value[index + 1] for value in values])
        return sl

    def add_list(self, name: str, values: List[Any]) -> ScenarioList:
        """Add a list of values to a ScenarioList.

        Example:

        >>> s = ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
        >>> s.add_list('age', [30, 25])
        ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
        """
        sl = self.duplicate()
        if len(values) != len(sl):
            raise ScenarioError(
                f"Length of values ({len(values)}) does not match length of ScenarioList ({len(sl)})"
            )
        for i, value in enumerate(values):
            sl[i][name] = value
        return sl

    @classmethod
    def create_empty_scenario_list(cls, n: int) -> ScenarioList:
        """Create an empty ScenarioList with n scenarios.

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
        sl = self.duplicate()
        for scenario in sl:
            scenario[name] = value
        return sl
    
    def rename(self, replacement_dict: dict) -> ScenarioList:
        """Rename the fields in the scenarios.

        :param replacement_dict: A dictionary with the old names as keys and the new names as values.

        Example:

        >>> s = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
        >>> s.rename({'name': 'first_name', 'age': 'years'})
        ScenarioList([Scenario({'first_name': 'Alice', 'years': 30}), Scenario({'first_name': 'Bob', 'years': 25})])

        """
        new_list = ScenarioList([])
        for obj in self:
            new_obj = obj.rename(replacement_dict)
            new_list.append(new_obj)
        return new_list

    

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

    ## NEEDS TO BE FIXED
    # def new_column_names(self, new_names: List[str]) -> ScenarioList:
    #     """Rename the fields in the scenarios.

    #     Example:

    #     >>> s = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
    #     >>> s.new_column_names(['first_name', 'years'])
    #     ScenarioList([Scenario({'first_name': 'Alice', 'years': 30}), Scenario({'first_name': 'Bob', 'years': 25})])

    #     """
    #     new_list = ScenarioList([])
    #     for obj in self:
    #         new_obj = obj.new_column_names(new_names)
    #         new_list.append(new_obj)
    #     return new_list

    @classmethod
    def from_sqlite(cls, filepath: str, table: Optional[str] = None, sql_query: Optional[str] = None):
        """Create a ScenarioList from a SQLite database.
        
        Args:
            filepath (str): Path to the SQLite database file
            table (Optional[str]): Name of table to query. If None, sql_query must be provided.
            sql_query (Optional[str]): SQL query to execute. Used if table is None.
            
        Returns:
            ScenarioList: List of scenarios created from database rows
            
        Raises:
            ValueError: If both table and sql_query are None
            sqlite3.Error: If there is an error executing the database query
        """
        import sqlite3

        if table is None and sql_query is None:
            from .exceptions import ValueScenarioError
            raise ValueScenarioError("Either table or sql_query must be provided")

        try:
            with sqlite3.connect(filepath) as conn:
                cursor = conn.cursor()
                
                if table is not None:
                    cursor.execute(f"SELECT * FROM {table}")
                else:
                    cursor.execute(sql_query)
                    
                columns = [description[0] for description in cursor.description]
                data = cursor.fetchall()
                
            return cls([Scenario(dict(zip(columns, row))) for row in data])
            
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Database error occurred: {str(e)}")

    @classmethod
    def from_latex(cls, tex_file_path: str):
        with open(tex_file_path, "r") as file:
            lines = file.readlines()

        processed_lines = []
        non_blank_lines = [
            (i, line.strip()) for i, line in enumerate(lines) if line.strip()
        ]

        for index, (line_no, text) in enumerate(non_blank_lines):
            entry = {
                "line_no": line_no + 1,  # Using 1-based index for line numbers
                "text": text,
                "num_words": len(text.split()),
                "num_chars": len(text),
                "line_before": non_blank_lines[index - 1][1] if index > 0 else None,
                "line_after": (
                    non_blank_lines[index + 1][1]
                    if index < len(non_blank_lines) - 1
                    else None
                ),
            }
            processed_lines.append(entry)

        return ScenarioList([Scenario(entry) for entry in processed_lines])

    @classmethod
    def from_google_doc(cls, url: str) -> ScenarioList:
        """Create a ScenarioList from a Google Doc.

        This method downloads the Google Doc as a Word file (.docx), saves it to a temporary file,
        and then reads it using the from_docx class method.

        Args:
            url (str): The URL to the Google Doc.

        Returns:
            ScenarioList: An instance of the ScenarioList class.

        """
        import tempfile
        import requests

        if "/edit" in url:
            doc_id = url.split("/d/")[1].split("/edit")[0]
        else:
            from .exceptions import ValueScenarioError
            raise ValueScenarioError("Invalid Google Doc URL format.")

        export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=docx"

        # Download the Google Doc as a Word file (.docx)
        response = requests.get(export_url)
        response.raise_for_status()  # Ensure the request was successful

        # Save the Word file to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as temp_file:
            temp_file.write(response.content)
            temp_filename = temp_file.name

        # Call the from_docx class method with the temporary file
        return cls.from_docx(temp_filename)

    @classmethod
    def from_pandas(cls, df) -> ScenarioList:
        """Create a ScenarioList from a pandas DataFrame.

        Example:

        >>> import pandas as pd
        >>> df = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [30, 25], 'location': ['New York', 'Los Angeles']})
        >>> ScenarioList.from_pandas(df)
        ScenarioList([Scenario({'name': 'Alice', 'age': 30, 'location': 'New York'}), Scenario({'name': 'Bob', 'age': 25, 'location': 'Los Angeles'})])
        """
        return cls([Scenario(row) for row in df.to_dict(orient="records")])
    

    @classmethod
    def from_dta(cls, filepath: str, include_metadata: bool = True) -> ScenarioList:
        """Create a ScenarioList from a Stata file.
        
        Args:
            filepath (str): Path to the Stata (.dta) file
            include_metadata (bool): If True, extract and preserve variable labels and value labels
                                    as additional metadata in the ScenarioList
        
        Returns:
            ScenarioList: A ScenarioList containing the data from the Stata file
        """
        import pandas as pd
        
        # Read the Stata file with pandas
        df = pd.read_stata(filepath)
        
        # Create the basic ScenarioList
        scenario_list = cls.from_pandas(df)
        
        # Extract and preserve metadata if requested
        if include_metadata:
            # Get variable labels (if any)
            variable_labels = {}
            if hasattr(df, 'variable_labels') and df.variable_labels:
                variable_labels = df.variable_labels
            
            # Get value labels (if any)
            value_labels = {}
            if hasattr(df, 'value_labels') and df.value_labels:
                value_labels = df.value_labels
            
            # Store the metadata in the ScenarioList's codebook
            if variable_labels or value_labels:
                scenario_list.codebook = {
                    'variable_labels': variable_labels,
                    'value_labels': value_labels
                }
        
        return scenario_list

    @classmethod
    def from_wikipedia(cls, url: str, table_index: int = 0):
        """
        Extracts a table from a Wikipedia page.

        Parameters:
            url (str): The URL of the Wikipedia page.
            table_index (int): The index of the table to extract (default is 0).

        Returns:
            pd.DataFrame: A DataFrame containing the extracted table.
        # # Example usage
        # url = "https://en.wikipedia.org/wiki/List_of_countries_by_GDP_(nominal)"
        # df = from_wikipedia(url, 0)

        # if not df.empty:
        #     print(df.head())
        # else:
        #     print("Failed to extract table.")


        """
        import pandas as pd
        import requests
        from requests.exceptions import RequestException

        try:
            # Check if the URL is reachable
            response = requests.get(url)
            response.raise_for_status()  # Raises HTTPError for bad responses

            # Extract tables from the Wikipedia page
            tables = pd.read_html(url)

            # Ensure the requested table index is within the range of available tables
            if table_index >= len(tables) or table_index < 0:
                raise IndexError(
                    f"Table index {table_index} is out of range. This page has {len(tables)} table(s)."
                )

            # Return the requested table as a DataFrame
            # return tables[table_index]
            return cls.from_pandas(tables[table_index])

        except RequestException as e:
            print(f"Error fetching the URL: {e}")
        except ValueError as e:
            print(f"Error parsing tables: {e}")
        except IndexError as e:
            print(e)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        # Return an empty DataFrame in case of an error
        # return cls.from_pandas(pd.DataFrame())

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

    @classmethod
    def from_excel(
        cls, filename: str, sheet_name: Optional[str] = None, skip_rows: Optional[List[int]] = None, use_codebook: bool = False
    ) -> ScenarioList:
        """Create a ScenarioList from an Excel file.

        If the Excel file contains multiple sheets and no sheet_name is provided,
        the method will print the available sheets and require the user to specify one.

        Args:
            filename (str): Path to the Excel file
            sheet_name (Optional[str]): Name of the sheet to load. If None and multiple sheets exist,
                                      will raise an error listing available sheets.
            skip_rows (Optional[List[int]]): List of row indices to skip (0-based). If None, all rows are included.

        Example:

        >>> import tempfile
        >>> import os
        >>> import pandas as pd
        >>> with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as f:
        ...     df1 = pd.DataFrame({
        ...         'name': ['Alice', 'Bob', 'Charlie'],
        ...         'age': [30, 25, 35],
        ...         'location': ['New York', 'Los Angeles', 'Chicago']
        ...     })
        ...     df2 = pd.DataFrame({
        ...         'name': ['David', 'Eve'],
        ...         'age': [40, 45],
        ...         'location': ['Boston', 'Seattle']
        ...     })
        ...     with pd.ExcelWriter(f.name) as writer:
        ...         df1.to_excel(writer, sheet_name='Sheet1', index=False)
        ...         df2.to_excel(writer, sheet_name='Sheet2', index=False)
        ...     temp_filename = f.name
        >>> # Load all rows
        >>> scenario_list = ScenarioList.from_excel(temp_filename, sheet_name='Sheet1')
        >>> len(scenario_list)
        3
        >>> # Skip the second row (index 1)
        >>> scenario_list = ScenarioList.from_excel(temp_filename, sheet_name='Sheet1', skip_rows=[1])
        >>> len(scenario_list)
        2
        >>> scenario_list[0]['name']
        'Alice'
        >>> scenario_list[1]['name']
        'Charlie'
        """
        from .scenario import Scenario
        import pandas as pd

        # Get all sheets
        all_sheets = pd.read_excel(filename, sheet_name=None)

        # If no sheet_name is provided and there is more than one sheet, print available sheets
        if sheet_name is None:
            if len(all_sheets) > 1:
                print("The Excel file contains multiple sheets:")
                for name in all_sheets.keys():
                    print(f"- {name}")
                from .exceptions import ValueScenarioError
                raise ValueScenarioError("Please provide a sheet name to load data from.")
            else:
                # If there is only one sheet, use it
                sheet_name = list(all_sheets.keys())[0]

        # Load the specified or determined sheet
        df = pd.read_excel(filename, sheet_name=sheet_name)

        # Skip specified rows if any
        if skip_rows:
            df = df.drop(skip_rows)
            # Reset index to ensure continuous indexing
            df = df.reset_index(drop=True)

        if use_codebook:
            codebook = {f"col_{i}": col for i, col in enumerate(df.columns)}
            koobedoc = {col:f"col_{i}" for i, col in enumerate(df.columns)}

        observations = []
        for _, row in df.iterrows():
            if use_codebook:
                observations.append(Scenario({koobedoc.get(k):v for k,v in row.to_dict().items()}))
            else:
                observations.append(Scenario(row.to_dict()))


        if use_codebook:    
            return cls(observations, codebook=codebook)
        else:
            return cls(observations)

    @classmethod
    def from_google_sheet(cls, url: str, sheet_name: str = None, column_names: Optional[List[str]]= None) -> ScenarioList:
        """Create a ScenarioList from a Google Sheet.

        This method downloads the Google Sheet as an Excel file, saves it to a temporary file,
        and then reads it using the from_excel class method.

        Args:
            url (str): The URL to the Google Sheet.
            sheet_name (str, optional): The name of the sheet to load. If None, the method will behave
                                        the same as from_excel regarding multiple sheets.
            column_names (List[str], optional): If provided, use these names for the columns instead
                                              of the default column names from the sheet.

        Returns:
            ScenarioList: An instance of the ScenarioList class.

        """
        import tempfile
        import requests

        if "/edit" in url:
            sheet_id = url.split("/d/")[1].split("/edit")[0]
        else:
            from .exceptions import ValueScenarioError
            raise ValueScenarioError("Invalid Google Sheet URL format.")

        export_url = (
            f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
        )

        # Download the Google Sheet as an Excel file
        response = requests.get(export_url)
        response.raise_for_status()  # Ensure the request was successful

        # Save the Excel file to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_file:
            temp_file.write(response.content)
            temp_filename = temp_file.name

        # First create the ScenarioList with default column names
        scenario_list = cls.from_excel(temp_filename, sheet_name=sheet_name)

        # If column_names is provided, create a new ScenarioList with the specified names
        if column_names is not None:
            if len(column_names) != len(scenario_list[0].keys()):
                raise ValueError(
                    f"Number of provided column names ({len(column_names)}) "
                    f"does not match number of columns in sheet ({len(scenario_list[0].keys())})"
                )
            
            # Create a codebook mapping original keys to new names
            original_keys = list(scenario_list[0].keys())
            codebook = dict(zip(original_keys, column_names))
            
            # Return new ScenarioList with renamed columns
            return scenario_list.rename(codebook)
        else:
            return scenario_list

    @classmethod
    def from_delimited_file(
        cls, source: Union[str, "ParseResult"], delimiter: str = ","
    ) -> ScenarioList:
        """Create a ScenarioList from a delimited file (CSV/TSV) or URL."""
        import requests
        from .scenario import Scenario
        from urllib.parse import urlparse
        from urllib.parse import ParseResult

        headers = {
            "Accept": "text/csv,application/csv,text/plain",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        def is_url(source):
            try:
                result = urlparse(source)
                return all([result.scheme, result.netloc])
            except ValueError:
                return False

        try:
            if isinstance(source, str) and is_url(source):
                response = requests.get(source, headers=headers)
                response.raise_for_status()
                file_obj = StringIO(response.text)
            elif isinstance(source, ParseResult):
                response = requests.get(source.geturl(), headers=headers)
                response.raise_for_status()
                file_obj = StringIO(response.text)
            else:
                # Try different encodings if the default fails
                encodings_to_try = ["utf-8", "latin-1", "cp1252", "ISO-8859-1"]
                last_exception = None
                file_obj = None
                
                for encoding in encodings_to_try:
                    try:
                        file_obj = open(source, "r", encoding=encoding)
                        # Test reading a bit to verify encoding
                        file_obj.readline()
                        file_obj.seek(0)  # Reset file position
                        break
                    except UnicodeDecodeError as e:
                        last_exception = e
                        if file_obj:
                            file_obj.close()
                            file_obj = None
                
                if file_obj is None:
                    from .exceptions import ValueScenarioError
                    raise ValueScenarioError(f"Could not decode file {source} with any of the attempted encodings. Original error: {last_exception}")

            reader = csv.reader(file_obj, delimiter=delimiter)
            try:
                header = next(reader)
                observations = [Scenario(dict(zip(header, row))) for row in reader]
            except StopIteration:
                from .exceptions import ValueScenarioError
                raise ValueScenarioError(f"File {source} appears to be empty or has an invalid format")

        finally:
            if file_obj:
                file_obj.close()

        return cls(observations)

    # Convenience methods for specific file types
    @classmethod
    def from_csv(cls, source: Union[str, "ParseResult"]) -> ScenarioList:
        """Create a ScenarioList from a CSV file or URL."""
        return cls.from_delimited_file(source, delimiter=",")

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

    @classmethod
    def from_tsv(cls, source: Union[str, "ParseResult"]) -> ScenarioList:
        """Create a ScenarioList from a TSV file or URL."""
        return cls.from_delimited_file(source, delimiter="\t")

    def to_dict(self, sort: bool = False, add_edsl_version: bool = True) -> dict:
        """
        >>> s = ScenarioList([Scenario({'food': 'wood chips'}), Scenario({'food': 'wood-fired pizza'})])
        >>> s.to_dict()
        {'scenarios': [{'food': 'wood chips', 'edsl_version': '...', 'edsl_class_name': 'Scenario'}, {'food': 'wood-fired pizza', 'edsl_version': '...', 'edsl_class_name': 'Scenario'}], 'edsl_version': '...', 'edsl_class_name': 'ScenarioList'}

        """
        if sort:
            data = sorted(self, key=lambda x: hash(x))
        else:
            data = self
        d = {"scenarios": [s.to_dict(add_edsl_version=add_edsl_version) for s in data]}

        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = self.__class__.__name__
        return d

    def to(self, survey: Union["Survey", "QuestionBase"]) -> "Jobs":
        """Create a Jobs object from a ScenarioList and a Survey object.

        :param survey: The Survey object to use for the Jobs object.

        Example:
        >>> from edsl import Survey, Jobs, ScenarioList
        >>> isinstance(ScenarioList.example().to(Survey.example()), Jobs)
        True
        """
        from ..surveys import Survey
        from ..questions import QuestionBase

        if isinstance(survey, QuestionBase):
            return Survey([survey]).by(self)
        else:
            return survey.by(self)

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
    def from_dict(cls, data) -> ScenarioList:
        """Create a `ScenarioList` from a dictionary."""
        from .scenario import Scenario

        return cls([Scenario.from_dict(s) for s in data["scenarios"]])

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

    def __getitem__(self, key: Union[int, slice]) -> Any:
        """Return the item at the given index.

        Example:
        >>> s = ScenarioList([Scenario({'age': 22, 'hair': 'brown', 'height': 5.5}), Scenario({'age': 22, 'hair': 'brown', 'height': 5.5})])
        >>> s[0]
        Scenario({'age': 22, 'hair': 'brown', 'height': 5.5})

        >>> s[:1]
        ScenarioList([Scenario({'age': 22, 'hair': 'brown', 'height': 5.5})])

        """
        if isinstance(key, slice):
            return ScenarioList(super().__getitem__(key))
        elif isinstance(key, int):
            return super().__getitem__(key)
        else:
            return self.to_dict(add_edsl_version=False)[key]

    def to_agent_list(self):
        """Convert the ScenarioList to an AgentList.

        Example:

        >>> s = ScenarioList([Scenario({'age': 22, 'hair': 'brown', 'height': 5.5}), Scenario({'age': 22, 'hair': 'brown', 'height': 5.5})])
        >>> s.to_agent_list()
        AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5}), Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})])
        """
        from ..agents import AgentList, Agent

        agents = []
        for scenario in self:
            new_scenario = scenario.copy().data
            if "name" in new_scenario:
                name = new_scenario.pop("name")
                proposed_agent_name = "agent_name"
                while proposed_agent_name not in new_scenario:
                    proposed_agent_name += "_"
                warnings.warn(
                    f"The 'name' field is reserved for the agent's name---putting this value in {proposed_agent_name}"
                )
                new_scenario[proposed_agent_name] = name
                new_agent = Agent(traits=new_scenario, name=name)
            if "agent_parameters" in new_scenario:
                agent_parameters = new_scenario.pop("agent_parameters")
                instruction = agent_parameters.get("instruction", None)
                name = agent_parameters.get("name", None)
                new_agent = Agent(
                    traits=new_scenario, name=name, instruction=instruction
                )
            else:
                new_agent = Agent(traits=new_scenario)

            agents.append(new_agent)

        return AgentList(agents)

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

    def collapse(self, field: str, separator: Optional[str] = None, add_count: bool = False) -> ScenarioList:
        """Collapse a ScenarioList by grouping on all fields except the specified one,
        collecting the values of the specified field into a list.

        Args:
            field: The field to collapse (whose values will be collected into lists)
            separator: Optional string to join the values with instead of keeping as a list
            add_count: If True, adds a field showing the number of collapsed rows

        Returns:
            ScenarioList: A new ScenarioList with the specified field collapsed into lists

        Example:
        >>> s = ScenarioList([
        ...     Scenario({'category': 'fruit', 'color': 'red', 'item': 'apple'}),
        ...     Scenario({'category': 'fruit', 'color': 'red', 'item': 'cherry'}),
        ...     Scenario({'category': 'vegetable', 'color': 'green', 'item': 'spinach'})
        ... ])
        >>> s.collapse('item', add_count=True)
        ScenarioList([Scenario({'category': 'fruit', 'color': 'red', 'item': ['apple', 'cherry'], 'num_collapsed_rows': 2}), Scenario({'category': 'vegetable', 'color': 'green', 'item': ['spinach'], 'num_collapsed_rows': 1})])
        """
        if not self:
            return ScenarioList([])
        
        # Determine all fields except the one to collapse
        id_vars = [key for key in self[0].keys() if key != field]
        
        # Group the scenarios
        grouped = defaultdict(list)
        for scenario in self:
            # Create a tuple of the values of all fields except the one to collapse
            key = tuple(scenario[id_var] for id_var in id_vars)
            # Add the value of the field to collapse to the list for this key
            grouped[key].append(scenario[field])
        
        # Create a new ScenarioList with the collapsed field
        result = []
        for key, values in grouped.items():
            new_scenario = dict(zip(id_vars, key))
            if separator:
                new_scenario[field] = separator.join(values)
            else:
                new_scenario[field] = values
            if add_count:
                new_scenario['num_collapsed_rows'] = len(values)
            result.append(Scenario(new_scenario))
        
        return ScenarioList(result)

    def create_comparisons(
        self, 
        bidirectional: bool = False, 
        num_options: int = 2,
        option_prefix: str = "option_",
        use_alphabet: bool = False
    ) -> ScenarioList:
        """Create a new ScenarioList with comparisons between scenarios.
        
        Each scenario in the result contains multiple original scenarios as dictionaries,
        allowing for side-by-side comparison.
        
        Args:
            bidirectional (bool): If True, include both (A,B) and (B,A) comparisons.
                If False, only include (A,B) where A comes before B in the original list.
            num_options (int): Number of scenarios to include in each comparison.
                Default is 2 for pairwise comparisons.
            option_prefix (str): Prefix for the keys in the resulting scenarios.
                Default is "option_", resulting in keys like "option_1", "option_2", etc.
                Ignored if use_alphabet is True.
            use_alphabet (bool): If True, use letters as keys (A, B, C, etc.) instead of
                the option_prefix with numbers.
        
        Returns:
            ScenarioList: A new ScenarioList where each scenario contains multiple original
                scenarios as dictionaries.
        
        Example:
            >>> s = ScenarioList([
            ...     Scenario({'id': 1, 'text': 'Option A'}),
            ...     Scenario({'id': 2, 'text': 'Option B'}),
            ...     Scenario({'id': 3, 'text': 'Option C'})
            ... ])
            >>> s.create_comparisons(use_alphabet=True)
            ScenarioList([Scenario({'A': {'id': 1, 'text': 'Option A'}, 'B': {'id': 2, 'text': 'Option B'}}), Scenario({'A': {'id': 1, 'text': 'Option A'}, 'B': {'id': 3, 'text': 'Option C'}}), Scenario({'A': {'id': 2, 'text': 'Option B'}, 'B': {'id': 3, 'text': 'Option C'}})])
            >>> s.create_comparisons(num_options=3, use_alphabet=True)
            ScenarioList([Scenario({'A': {'id': 1, 'text': 'Option A'}, 'B': {'id': 2, 'text': 'Option B'}, 'C': {'id': 3, 'text': 'Option C'}})])
        """
        from itertools import combinations, permutations
        import string
        
        if num_options < 2:
            from .exceptions import ValueScenarioError
            raise ValueScenarioError("num_options must be at least 2")
        
        if num_options > len(self):
            from .exceptions import ValueScenarioError
            raise ValueScenarioError(f"num_options ({num_options}) cannot exceed the number of scenarios ({len(self)})")
        
        if use_alphabet and num_options > 26:
            from .exceptions import ValueScenarioError
            raise ValueScenarioError("When using alphabet labels, num_options cannot exceed 26 (the number of letters in the English alphabet)")
        
        # Convert each scenario to a dictionary
        scenario_dicts = [scenario.to_dict(add_edsl_version=False) for scenario in self]
        
        # Generate combinations or permutations based on bidirectional flag
        if bidirectional:
            # For bidirectional, use permutations to get all ordered arrangements
            if num_options == 2:
                # For pairwise, we can use permutations with r=2
                scenario_groups = permutations(scenario_dicts, 2)
            else:
                # For more than 2 options with bidirectional=True, 
                # we need all permutations of the specified size
                scenario_groups = permutations(scenario_dicts, num_options)
        else:
            # For unidirectional, use combinations to get unordered groups
            scenario_groups = combinations(scenario_dicts, num_options)
        
        # Create new scenarios with the combinations
        result = []
        for group in scenario_groups:
            new_scenario = {}
            for i, scenario_dict in enumerate(group):
                if use_alphabet:
                    # Use uppercase letters (A, B, C, etc.)
                    key = string.ascii_uppercase[i]
                else:
                    # Use the option prefix with numbers (option_1, option_2, etc.)
                    key = f"{option_prefix}{i+1}"
                new_scenario[key] = scenario_dict
            result.append(Scenario(new_scenario))
        
        return ScenarioList(result)

    @classmethod
    def from_parquet(cls, filepath: str) -> ScenarioList:
        """Create a ScenarioList from a Parquet file.
        
        Args:
            filepath (str): Path to the Parquet file
            
        Returns:
            ScenarioList: A ScenarioList containing the data from the Parquet file
            
        Example:
        >>> import pandas as pd
        >>> import tempfile
        >>> df = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [30, 25]})
        >>> # The following would create and read a parquet file if dependencies are installed:
        >>> # with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as f:
        >>> #     df.to_parquet(f.name)
        >>> #     scenario_list = ScenarioList.from_parquet(f.name)
        >>> # Instead, we'll demonstrate the equivalent result:
        >>> scenario_list = ScenarioList.from_pandas(df)
        >>> len(scenario_list)
        2
        >>> scenario_list[0]['name']
        'Alice'
        """
        import pandas as pd
        
        try:
            # Try to read the Parquet file with pandas
            df = pd.read_parquet(filepath)
        except ImportError as e:
            # Handle missing dependencies with a helpful error message
            if "pyarrow" in str(e) or "fastparquet" in str(e):
                raise ImportError(
                    "Missing dependencies for Parquet support. Please install either pyarrow or fastparquet:\n"
                    "  pip install pyarrow\n"
                    "  or\n"
                    "  pip install fastparquet"
                ) from e
            else:
                raise
        
        # Convert the DataFrame to a ScenarioList
        return cls.from_pandas(df)

    def replace_values(self, replacements:dict) -> "ScenarioList":
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
        new_scenarios = []
        for scenario in self:
            new_scenario = {}
            for key, value in scenario.items():
                if str(value) in replacements:
                    new_scenario[key] = replacements[str(value)]
                else:
                    new_scenario[key] = value
            new_scenarios.append(Scenario(new_scenario))
        return ScenarioList(new_scenarios)

    @classmethod
    def from_pdf(cls, filename_or_url, collapse_pages=False):
        return PdfTools.from_pdf(filename_or_url, collapse_pages)
    
    @classmethod
    def from_pdf_to_image(cls, pdf_path, image_format="jpeg"):
        return PdfTools.from_pdf_to_image(pdf_path, image_format)



if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
