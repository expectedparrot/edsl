"""A list of Scenarios to be used in a survey."""

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

try:
    from typing import TypeAlias
except ImportError:
    from typing_extensions import TypeAlias

import csv
import random
from io import StringIO
import inspect
from collections import UserList, defaultdict
from collections.abc import Iterable

if TYPE_CHECKING:
    from urllib.parse import ParseResult
    from edsl.results.Dataset import Dataset
    from edsl.jobs.Jobs import Jobs
    from edsl.surveys.Survey import Survey
    from edsl.questions.QuestionBase import QuestionBase


from simpleeval import EvalWithCompoundTypes, NameNotDefined  # type: ignore

from tabulate import tabulate_formats

from edsl.Base import Base
from edsl.utilities.remove_edsl_version import remove_edsl_version

from edsl.scenarios.Scenario import Scenario
from edsl.scenarios.ScenarioListPdfMixin import ScenarioListPdfMixin
from edsl.scenarios.ScenarioListExportMixin import ScenarioListExportMixin
from edsl.utilities.naming_utilities import sanitize_string
from edsl.utilities.is_valid_variable_name import is_valid_variable_name
from edsl.exceptions.scenarios import ScenarioError

from edsl.scenarios.directory_scanner import DirectoryScanner


class ScenarioListMixin(ScenarioListPdfMixin, ScenarioListExportMixin):
    pass


if TYPE_CHECKING:
    from edsl.results.Dataset import Dataset

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


class ScenarioList(Base, UserList, ScenarioListMixin):
    """Class for creating a list of scenarios to be used in a survey."""

    __documentation__ = (
        "https://docs.expectedparrot.com/en/latest/scenarios.html#scenariolist"
    )

    def __init__(
        self, data: Optional[list] = None, codebook: Optional[dict[str, str]] = None
    ):
        """Initialize the ScenarioList class."""
        if data is not None:
            super().__init__(data)
        else:
            super().__init__([])
        self.codebook = codebook or {}

    def unique(self) -> ScenarioList:
        """Return a list of unique scenarios.

        >>> s = ScenarioList([Scenario({'a': 1}), Scenario({'a': 1}), Scenario({'a': 2})])
        >>> s.unique()
        ScenarioList([Scenario({'a': 1}), Scenario({'a': 2})])
        """
        return ScenarioList(list(set(self)))

    @property
    def has_jinja_braces(self) -> bool:
        """Check if the ScenarioList has Jinja braces."""
        return any([scenario.has_jinja_braces for scenario in self])

    def _convert_jinja_braces(self) -> ScenarioList:
        """Convert Jinja braces to Python braces."""
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
        from edsl import QuestionYesNo

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
        from edsl.utilities.utilities import dict_hash

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

    def concatenate(self, fields: List[str], separator: str = ";") -> ScenarioList:
        """Concatenate specified fields into a single field.

        :param fields: The fields to concatenate.
        :param separator: The separator to use.

        Returns:
            ScenarioList: A new ScenarioList with concatenated fields.

        Example:
            >>> s = ScenarioList([Scenario({'a': 1, 'b': 2, 'c': 3}), Scenario({'a': 4, 'b': 5, 'c': 6})])
            >>> s.concatenate(['a', 'b', 'c'])
            ScenarioList([Scenario({'concat_a_b_c': '1;2;3'}), Scenario({'concat_a_b_c': '4;5;6'})])
        """
        new_scenarios = []
        for scenario in self:
            new_scenario = scenario.copy()
            concat_values = []
            for field in fields:
                if field in new_scenario:
                    concat_values.append(str(new_scenario[field]))
                    del new_scenario[field]

            new_field_name = f"concat_{'_'.join(fields)}"
            new_scenario[new_field_name] = separator.join(concat_values)
            new_scenarios.append(new_scenario)

        return ScenarioList(new_scenarios)

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
        from edsl.utilities.utilities import is_valid_variable_name

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
        from edsl.scenarios.scenario_selector import ScenarioSelector

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
            func = lambda x: x
        return cls([Scenario({name: func(value)}) for value in values])

    def table(
        self,
        *fields: str,
        tablefmt: Optional[TableFormat] = None,
        pretty_labels: Optional[dict[str, str]] = None,
    ) -> str:
        """Return the ScenarioList as a table."""

        from tabulate import tabulate_formats

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

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 2}), Scenario({'a': 3, 'b': 4})])
        >>> s.reorder_keys(['b', 'a'])
        ScenarioList([Scenario({'b': 2, 'a': 1}), Scenario({'b': 4, 'a': 3})])
        >>> s.reorder_keys(['a', 'b', 'c'])
        Traceback (most recent call last):
        ...
        AssertionError
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
        from edsl.results.Dataset import Dataset

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
    def from_list_of_tuples(self, *names: str, values: List[Tuple]) -> ScenarioList:
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
    def from_sqlite(cls, filepath: str, table: str):
        """Create a ScenarioList from a SQLite database."""
        import sqlite3

        with sqlite3.connect(filepath) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table}")
            columns = [description[0] for description in cursor.description]
            data = cursor.fetchall()
        return cls([Scenario(dict(zip(columns, row))) for row in data])

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
        from docx import Document

        if "/edit" in url:
            doc_id = url.split("/d/")[1].split("/edit")[0]
        else:
            raise ValueError("Invalid Google Doc URL format.")

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
        cls, filename: str, sheet_name: Optional[str] = None
    ) -> ScenarioList:
        """Create a ScenarioList from an Excel file.

        If the Excel file contains multiple sheets and no sheet_name is provided,
        the method will print the available sheets and require the user to specify one.

        Example:

        >>> import tempfile
        >>> import os
        >>> import pandas as pd
        >>> with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as f:
        ...     df1 = pd.DataFrame({
        ...         'name': ['Alice', 'Bob'],
        ...         'age': [30, 25],
        ...         'location': ['New York', 'Los Angeles']
        ...     })
        ...     df2 = pd.DataFrame({
        ...         'name': ['Charlie', 'David'],
        ...         'age': [35, 40],
        ...         'location': ['Chicago', 'Boston']
        ...     })
        ...     with pd.ExcelWriter(f.name) as writer:
        ...         df1.to_excel(writer, sheet_name='Sheet1', index=False)
        ...         df2.to_excel(writer, sheet_name='Sheet2', index=False)
        ...     temp_filename = f.name
        >>> scenario_list = ScenarioList.from_excel(temp_filename, sheet_name='Sheet1')
        >>> len(scenario_list)
        2
        >>> scenario_list[0]['name']
        'Alice'
        >>> scenario_list = ScenarioList.from_excel(temp_filename)  # Should raise an error and list sheets
        Traceback (most recent call last):
        ...
        ValueError: Please provide a sheet name to load data from.
        """
        from edsl.scenarios.Scenario import Scenario
        import pandas as pd

        # Get all sheets
        all_sheets = pd.read_excel(filename, sheet_name=None)

        # If no sheet_name is provided and there is more than one sheet, print available sheets
        if sheet_name is None:
            if len(all_sheets) > 1:
                print("The Excel file contains multiple sheets:")
                for name in all_sheets.keys():
                    print(f"- {name}")
                raise ValueError("Please provide a sheet name to load data from.")
            else:
                # If there is only one sheet, use it
                sheet_name = list(all_sheets.keys())[0]

        # Load the specified or determined sheet
        df = pd.read_excel(filename, sheet_name=sheet_name)

        observations = []
        for _, row in df.iterrows():
            observations.append(Scenario(row.to_dict()))

        return cls(observations)

    @classmethod
    def from_google_sheet(cls, url: str, sheet_name: str = None) -> ScenarioList:
        """Create a ScenarioList from a Google Sheet.

        This method downloads the Google Sheet as an Excel file, saves it to a temporary file,
        and then reads it using the from_excel class method.

        Args:
            url (str): The URL to the Google Sheet.
            sheet_name (str, optional): The name of the sheet to load. If None, the method will behave
                                        the same as from_excel regarding multiple sheets.

        Returns:
            ScenarioList: An instance of the ScenarioList class.

        """
        import pandas as pd
        import tempfile
        import requests

        if "/edit" in url:
            sheet_id = url.split("/d/")[1].split("/edit")[0]
        else:
            raise ValueError("Invalid Google Sheet URL format.")

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

        # Call the from_excel class method with the temporary file
        return cls.from_excel(temp_filename, sheet_name=sheet_name)

    @classmethod
    def from_delimited_file(
        cls, source: Union[str, "ParseResult"], delimiter: str = ","
    ) -> ScenarioList:
        """Create a ScenarioList from a delimited file (CSV/TSV) or URL."""
        import requests
        from edsl.scenarios.Scenario import Scenario
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
                file_obj = open(source, "r")

            reader = csv.reader(file_obj, delimiter=delimiter)
            header = next(reader)
            observations = [Scenario(dict(zip(header, row))) for row in reader]

        finally:
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
        from edsl.scenarios.scenario_join import ScenarioJoin

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
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = self.__class__.__name__
        return d

    def to(self, survey: Union["Survey", "QuestionBase"]) -> "Jobs":
        """Create a Jobs object from a ScenarioList and a Survey object.

        :param survey: The Survey object to use for the Jobs object.

        Example:
        >>> from edsl import Survey
        >>> from edsl.jobs.Jobs import Jobs
        >>> from edsl import ScenarioList
        >>> isinstance(ScenarioList.example().to(Survey.example()), Jobs)
        True
        """
        from edsl.surveys.Survey import Survey
        from edsl.questions.QuestionBase import QuestionBase
        from edsl.jobs.Jobs import Jobs

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
        from edsl.scenarios.Scenario import Scenario

        return cls([Scenario(s) for s in scenario_dicts_list])

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data) -> ScenarioList:
        """Create a `ScenarioList` from a dictionary."""
        from edsl.scenarios.Scenario import Scenario

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
            "from edsl.scenarios.Scenario import Scenario",
            "from edsl.scenarios.ScenarioList import ScenarioList",
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

    # def rich_print(self) -> None:
    #     """Display an object as a table."""
    #     from rich.table import Table

    #     table = Table(title="ScenarioList")
    #     table.add_column("Index", style="bold")
    #     table.add_column("Scenario")
    #     for i, s in enumerate(self):
    #         table.add_row(str(i), s.rich_print())
    #     return table

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
        from edsl.agents.AgentList import AgentList
        from edsl.agents.Agent import Agent
        import warnings

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
        ScenarioList([Scenario({'text': 'The quick brown', 'text_chunk': 0}), Scenario({'text': 'fox jumps over', 'text_chunk': 1}), Scenario({'text': 'the lazy dog.', 'text_chunk': 2})])
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


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
