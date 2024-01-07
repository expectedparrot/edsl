"""
Results is a UserList of Result objects. 
It is instantiated with a survey and a list of observations.

The Results object can then be manipulated in various ways with select, filter, mutate, etc. 
"""
from __future__ import annotations
import io
import json
import sys
from collections import UserList, defaultdict
from simpleeval import EvalWithCompoundTypes
from typing import Union
from edsl.exceptions import (
    ResultsBadMutationstringError,
    ResultsColumnNotFoundError,
    ResultsInvalidNameError,
)
from edsl.results.Dataset import Dataset
from edsl.results.ResultsExportMixin import ResultsExportMixin
from edsl.results.RegressionMixin import RegressionMixin
from edsl.results.ResultsOutputMixin import ResultsOutputMixin
from edsl.results.ResultsFetchMixin import ResultsFetchMixin
from edsl.utilities import is_gzipped, is_valid_variable_name, shorten_string


class Results(
    UserList, ResultsFetchMixin, ResultsExportMixin, ResultsOutputMixin, RegressionMixin
):
    def __init__(self, survey, data, created_columns=None):
        """
        The Results object is a list of Result objects, stored in data.
        It is instantiated with a survey and a list of observations.
        It also has a list of created_columns, which is a list of columns that have been created with `mutate`
        """
        super().__init__(data)
        self.survey = survey
        if created_columns is None:
            self.created_columns = []
        else:
            self.created_columns = created_columns

    def __repr__(self):
        return f"Results(data = {self.data}, survey = {self.survey}, created_columns = {self.created_columns})"

    @property
    def _key_to_data_type(self):
        """Maps keys (how_feeling, status, etc.) to data types (result, agent, scenario, etc.)"""
        """E.g.,
        {'temperature': 'model',
        'max_tokens': 'model',
        'top_p': 'model',
        'frequency_penalty': 'model',
        'presence_penalty': 'model',
        'use_cache': 'model',
        'model': 'model',
        'baseline': 'result'}

        >>> results = Results.create_example()
        >>> d = results._key_to_data_type
        >>> mapping = {'status': 'agent', 'period': 'scenario', 'temperature': 'model', 'max_tokens': 'model', 'top_p': 'model', 'frequency_penalty': 'model', 'presence_penalty': 'model', 'use_cache': 'model', 'model': 'model', 'how_feeling': 'answer', 'elapsed': 'answer'}
        >>> d == mapping
        True
        """
        d = {}
        for result in self.data:
            d.update(result.key_to_data_type)

        # The user could have created columns using 'mutate'
        for column in self.created_columns:
            d[column] = "answer"

        return d

    @property
    def _data_type_to_keys(self) -> dict:
        """Maps data types (result, agent, scenario, etc.) to keys (how_feeling, status, etc.)

        >>> r = Results.create_example()
        >>> mapping = r._data_type_to_keys.keys()
        >>> mapping
        dict_keys(['answer', 'agent', 'scenario', 'model'])
        """
        d = defaultdict(set)
        for result in self.data:
            for key, value in result.key_to_data_type.items():
                d[value] = d[value].union(set({key}))

        for column in self.created_columns:
            d["answer"] = d["answer"].union(set({column}))
        return d

    ######################
    ## Convenience methods
    ######################

    @property
    def answer_keys(self) -> dict:
        answer_keys = self._data_type_to_keys["answer"]
        answer_keys = {k for k in answer_keys if "_comment" not in k}
        questions_text = [
            self.survey.get_question(k).question_text for k in answer_keys
        ]
        short_question_text = [shorten_string(q, 80) for q in questions_text]
        return dict(zip(answer_keys, short_question_text))

    @property
    def agent_keys(self):
        return self._data_type_to_keys["agent"]

    @property
    def scenario_keys(self):
        return self._data_type_to_keys["scenario"]

    @property
    def model_keys(self):
        return self._data_type_to_keys["model"]

    @property
    def question_names(self):
        return list(self.survey.question_names)

    @property
    def agents(self):
        return [r.agent for r in self.data]

    @property
    def all_keys(self):
        answer_keys = set(self.answer_keys)
        return (
            answer_keys.union(self.agent_keys)
            .union(self.scenario_keys)
            .union(self.model_keys)
        )

    def relevant_columns(self) -> set:
        """
        This returns all of the columns that are in the results.

        >>> r = Results.create_example()
        >>> keys = r.relevant_columns()
        >>> keys == {'elapsed', 'temperature', 'agent', 'scenario', 'answer', 'use_cache', 'how_feeling', 'frequency_penalty', 'max_tokens', 'model', 'status', 'top_p', 'period', 'presence_penalty'}
        True
        """
        return set().union(
            *(observation.combined_dict.keys() for observation in self.data)
        )

    def _parse_column(self, column: str) -> tuple[str, str]:
        """
        Utility function to parse a column name into a data type and a key.

        >>> r = Results.create_example()
        >>> r._parse_column("answer.how_feeling")
        ('answer', 'how_feeling')

        The standard way a column is specified is with a dot-separated string, e.g. "agent.status".
        >> self._parse_column("agent.status")
        ("agent", "status")

        But you can also specify a single key, e.g. "status", in which case it will look up the data type.
        This relies on the key_to_data_type property of the Results class.
        """
        if "." in column:  # they passed it as, say, "answer.how_feeling"
            data_type, key = column.split(".")
        else:
            try:
                data_type, key = self._key_to_data_type[column], column
            except KeyError:
                raise ResultsColumnNotFoundError(f"Column {column} not found in data")

        return data_type, key

    def first(self):
        """
        This returns the first observation in the results.
        """
        return self.data[0]

    def mutate(self, new_var_string, functions_dict=None) -> Results:
        """
        Creates a value value in 'results' as if has been asked as part of the survey.
        It splits the new_var_string at the "=" and uses simple_eval

        The functions dict is...

        >>> r = Results.create_example()
        >>> r.mutate('how_feeling_x = how_feeling + "x"').select('how_feeling_x')
        [{'answer.how_feeling_x': ['Badx', 'Badx', 'Greatx', 'Greatx']}]
        """
        if "=" not in new_var_string:
            raise ResultsBadMutationstringError(
                f"Mutate requires an '=' in the string, but '{new_var_string}' doesn't have one."
            )
        raw_var_name, expression = new_var_string.split("=", 1)
        var_name = raw_var_name.strip()

        if not is_valid_variable_name(var_name):
            raise ResultsInvalidNameError(f"{var_name} is not a valid variable name.")

        if functions_dict is None:
            functions_dict = {}

        def create_evaluator(result):
            return EvalWithCompoundTypes(
                names=result.combined_dict, functions=functions_dict
            )

        def new_result(old_result, var_name):
            evaluator = create_evaluator(old_result)
            value = evaluator.eval(expression)
            new_result = old_result.copy()
            new_result["answer"][var_name] = value
            return new_result

        try:
            new_data = [new_result(result, var_name) for result in self.data]
        except Exception as e:
            print(f"Exception:{e}")

        return Results(
            survey=self.survey,
            data=new_data,
            created_columns=self.created_columns + [var_name],
        )

    def select(self, *columns: Union[str, list[str]]) -> Dataset:
        """
        This selects data from the results and turns it into a format like so:
        >>> results = Results.create_example()
        >>> results.select('how_feeling')
        [{'answer.how_feeling': ['Bad', 'Bad', 'Great', 'Great']}]
        """

        if not columns or columns == ("*",) or columns == (None,):
            columns = ("*.*",)

        if isinstance(columns[0], list):
            columns = tuple(columns[0])

        known_data_types = ["answer", "scenario", "agent", "model"]

        def get_data_types_to_return(parsed_data_type):
            if parsed_data_type == "*":  # they want all of the columns
                return known_data_types
            else:
                if parsed_data_type not in known_data_types:
                    raise Exception(
                        f"Data type {parsed_data_type} not found in data. Did you mean one of {known_data_types}"
                    )
                return [parsed_data_type]

        # we're doing to populate this with the data we want to fetch
        to_fetch = defaultdict(list)

        new_data = []
        items_in_order = []
        # iterate through the passed columns
        for column in columns:
            # a user could pass 'result.how_feeling' or just 'how_feeling'
            parsed_data_type, parsed_key = self._parse_column(column)
            data_types = get_data_types_to_return(parsed_data_type)
            found_once = False  # we need to track this to make sure we found the key at least once

            for data_type in data_types:
                # the keys for that data_type e.g.,# if data_type is 'answer', then the keys are 'how_feeling', 'how_feeling_comment', etc.
                relevant_keys = self._data_type_to_keys[data_type]

                for key in relevant_keys:
                    if key == parsed_key or parsed_key == "*":
                        found_once = True
                        to_fetch[data_type].append(key)
                        items_in_order.append(data_type + "." + key)

            if not found_once:
                raise Exception(f"Key {parsed_key} not found in data.")

        for data_type in to_fetch:
            for key in to_fetch[data_type]:
                entries = self._fetch_list(data_type, key)
                new_data.append({data_type + "." + key: entries})

        def sort_by_key_order(dictionary):
            # Extract the single key from the dictionary
            single_key = next(iter(dictionary))
            # Return the index of this key in the list_of_keys
            return items_in_order.index(single_key)

        sorted(new_data, key=sort_by_key_order)

        return Dataset(new_data)

    def sort_by(self, column, reverse=True) -> Results:
        "Sorts the results by a column"

        data_type, key = self._parse_column(column)

        def to_numeric_if_possible(v):
            try:
                return float(v)
            except:
                return v

        new_data = sorted(
            self.data,
            key=lambda x: to_numeric_if_possible(x.get_value(data_type, key)),
            reverse=reverse,
        )
        return Results(survey=self.survey, data=new_data, created_columns=None)

    def filter(self, expression) -> Results:
        """
        This filters a result based on the expression that is passed in.
        >>> r = Results.create_example()
        >>> r.filter("how_feeling == 'Great'").select('how_feeling')
        [{'answer.how_feeling': ['Great', 'Great']}]
        >>> r.filter("how_feeling == 'Nothing'").select('how_feeling')
        [{'answer.how_feeling': []}]
        """

        def create_evaluator(result):
            return EvalWithCompoundTypes(names=result.combined_dict)

        try:
            new_data = [
                result
                for result in self.data
                if create_evaluator(result).eval(expression)
            ]
        except Exception as e:
            print(f"Exception:{e}")

        return Results(survey=self.survey, data=new_data, created_columns=None)

    def to_dict(self):
        return {
            "data": [observation.to_dict() for observation in self.data],
            "survey": self.survey.to_dict(),
            "created_columns": self.created_columns,
        }

    @classmethod
    def from_dict(cls, data: dict):
        from edsl.surveys.Survey import Survey
        from edsl.results.Result import Result

        survey = Survey.from_dict(data["survey"])
        observations = [Result.from_dict(r) for r in data["data"]]
        created_columns = data.get("created_columns", None)
        new_cls = cls(survey=survey, data=observations, created_columns=created_columns)
        return new_cls

    @classmethod
    def load(cls, json_file) -> Results:
        "Froma stored JSON representation of the Results object, return the object"
        if is_gzipped(json_file):
            import gzip

            with gzip.open(json_file, "rb") as f:
                data = json.load(f)
        else:
            with open(json_file, "r") as f:
                data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def create_example(cls, refresh=False, debug=False):
        from edsl.utilities.data.Registry import EXAMPLE_RESULTS_PATH

        file_path = EXAMPLE_RESULTS_PATH

        if refresh:
            from edsl.jobs.Jobs import create_example_jobs, Jobs

            j = create_example_jobs()
            r = j.run(n=1, debug=debug)
            with open(file_path, "w") as file:
                json.dump(
                    r.to_dict(), file
                )  # Assuming r has a to_dict method to serialize the results

            return r

        else:
            original_stdout = (
                sys.stdout
            )  # Save a reference to the original standard output

            with io.StringIO() as buffer:
                sys.stdout = buffer  # Redirect stdout to buffer
                results = cls.from_dict(json.load(open(file_path, "r")))
                captured_output = buffer.getvalue()  # Get printed content from buffer

            sys.stdout = original_stdout  # Restore original stdout

            return results

    def show_methods(self):
        public_methods_with_docstrings = [
            (method, getattr(self, method).__doc__)
            for method in dir(self)
            if callable(getattr(self, method)) and not method.startswith("_")
        ]

        return [x[0] for x in public_methods_with_docstrings]


def create_example_results(debug=False, refresh=False) -> Results:
    print("Change to using class method directly")
    return Results.create_example(refresh=refresh, debug=debug)


if __name__ == "__main__":
    results = Results.create_example(refresh=False)

    print(results.filter("how_feeling == 'Great'").select("how_feeling"))

    print(results.mutate("how_feeling_x = how_feeling + 'x'").select("how_feeling_x"))

    # import doctest
    # doctest.testmod()
