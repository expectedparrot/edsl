"""
Results is a UserList with some special methodsBarChart.

It is instantiated with a survey and a list of observations.
The first time called, it copies over that list of observations to self.original_data.

The Results object can then be manipulated in various ways with select, filter, apply, etc. 
In each case, the original data is preserved because it is passed to the __init__ method 
of Results along with the new list of data. 
This way you can pass the results to, say, histogram or wordcloud and it can use "self" as the input. 

Regardless, it can always be restored to its original state with the method ".restore()".

## Goals: 
- filter & where can work with the full list 
- SQL-like, it will make the right inference if the 'table' is missing

"""
from __future__ import annotations
import copy
import io
import jinja2
import json
import markdown2
import sys
import textwrap
from typing import Optional, Union
from collections import UserList, defaultdict
from simpleeval import EvalWithCompoundTypes
from edsl.utilities.interface import (
    print_list_of_dicts_with_rich,
    print_list_of_dicts_as_html_table,
)
from edsl.results.Result import Result
from edsl.utilities.utilities import shorten_string
from edsl.results.ResultsExportMixin import ResultsExportMixin
from edsl.results.RegressionMixin import RegressionMixin
from edsl.results.ResultsOutputMixin import ResultsOutputMixin
from edsl.results.ResultsFetchMixin import ResultsFetchMixin
from edsl.utilities.utilities import is_gzipped


class ResultsStates:
    SELECTED = "selected"
    ORIGINAL = "original"


class Results(
    UserList,
    RegressionMixin,
    ResultsExportMixin,
    ResultsOutputMixin,
    ResultsFetchMixin,
):
    def __init__(
        self,
        survey,
        data,
        original_data=None,
        filtered_data=None,
        report_items=None,
        created_columns=None,
        state=ResultsStates.ORIGINAL,
    ):
        """
        -- self.data - working list
        -- self.original_data - what we started with
        ---self.filtered_data - what we have filtered things down too

        -- If you select a single column, it should just return a list.
        -- If you select multiple columns, it should return a list of dictionaries.
        """
        super().__init__(data)
        self.survey = survey
        self.state = state

        if original_data is None:  # instantiated for the first time
            self.original_data = copy.copy(data)
            self.filtered_data = copy.copy(data)
            self.report_items = []
            self.created_columns = []
        else:
            self.original_data = original_data
            self.filtered_data = filtered_data
            self.report_items = report_items
            self.created_columns = created_columns

        ResultsOutputMixin.add_output_functions(self)

    @property
    def _markdown_reprsentation(self):
        template = jinja2.Template(
            textwrap.dedent(
                """\
            # Results Report
            ## Overview
            - Observations: {{ results | length }}
            - Survey questions: {{ results.survey | length }}

            ## Keys
            - Answer keys: `{{ results.answer_keys }}`
            - Agent trait keys: `{{ results.agent_keys }}`
            - Scenario keys: `{{ results.scenario_keys }}`
            - Model keys: `{{ results.model_keys }}`
            - Created columns: `{{ results.created_columns }}`

            ## Survey questions
            {% for question in questions: %}
            1. (`{{ question.question_name }}`) {{ question.question_text }}
            {% if question.question_type == "multiple_choice": %}
                Type: {{ question.question_type }}
            {% for option in question.question_options %}
                    - {{ option }}
            {% endfor %}
            {% elif question.question_type == "free_text": %}
                Type: {{ question.question_type }}
            {% endif %}
            {% endfor %}
            """
            )
        )
        rendered_markdown = template.render(
            results=self, questions=self.survey._questions
        )
        return rendered_markdown

    def _repr_html_(self):
        rendered_markdown = self._markdown_reprsentation
        rendered_html = markdown2.markdown(rendered_markdown)
        return rendered_html

    def __repr__(self):
        return self._markdown_reprsentation

    @property
    def key_to_data_type(self):
        print("Switch to using _key_to_data_type. This shouldn't be called externally")
        return self._key_to_data_type

    @property
    def _key_to_data_type(self):
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
        for result in self.original_data:
            d.update(result.key_to_data_type)

        # The user could have created columns using 'mutate'
        for column in self.created_columns:
            d[column] = "answer"

        return d

    @property
    def data_type_to_keys(self):
        print("Switch to using _data_type_to_keys. This shouldn't be called externally")
        return self._data_type_to_keys

    @property
    def _data_type_to_keys(self) -> dict:
        """Maps data types (result, agent, scenario, etc.) to keys (how_feeling, status, etc.)

        >>> r = Results.create_example()
        >>> mapping = r._data_type_to_keys.keys()
        """
        d = defaultdict(set)
        for result in self.original_data:
            for key, value in result.key_to_data_type.items():
                d[value] = d[value].union(set({key}))

        for column in self.created_columns:
            d["answer"] = d["answer"].union(set({column}))
        return d

    @property
    def answer_keys(self) -> dict:
        # return self._data_type_to_keys["answer"]
        answer_keys = self._data_type_to_keys["answer"]
        answer_keys = {k for k in answer_keys if "_comment" not in k}
        questions_text = [
            self.survey.get_question(k).question_text for k in answer_keys
        ]
        short_question_text = [shorten_string(q, 80) for q in questions_text]
        return dict(zip(answer_keys, short_question_text))
        return {
            "survey_questions": self._data_type_to_keys["answer"],
            "created": self.created_columns,
        }

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
    def all_keys(self):
        answer_keys = set(self.answer_keys)
        return (
            answer_keys.union(self.agent_keys)
            .union(self.scenario_keys)
            .union(self.model_keys)
        )

    def restore(self) -> None:
        """Restore the data to its original state.

        >>> r = Results.create_example()
        >>> r2 = r.filter("how_feeling == 'Great'").select('how_feeling')
        >>> r = Results.create_example()
        >>> r.filter("how_feeling == 'Great'").select('how_feeling')
        [{'answer.how_feeling': ['Great', 'Great']}]

        Restore the data to its original state.
        >>> r = Results.create_example()
        >>> manipulated_data = r.filter("how_feeling == 'Great'").select('how_feeling')
        >>> r.restore()
        >>> r == manipulated_data
        False
        """
        self.data = self.original_data
        self.filtered_data = self.original_data
        self.state = ResultsStates.ORIGINAL

    def parse_column(self, column: str) -> tuple[str, str]:
        print("Change to using _parse_column here")
        return self._parse_column(column)

    def _parse_column(self, column: str) -> tuple[str, str]:
        """
        Utility function to parse a column name into a data type and a key.
        The standard way a column is specified is with a dot-separated string, e.g. "agent.status".

        But you can also specify a single key, e.g. "status", in which case it will look up the data type.
        This relies on the key_to_data_type property of the Results class.
        """
        if "." in column:
            data_type, key = column.split(".")
        else:
            if column in self._key_to_data_type:
                data_type = self._key_to_data_type[column]
                key = column
            else:
                breakpoint()
                raise Exception(f"Column {column} not found in data")

        return data_type, key

    def first(self):
        """
        This returns the first observation in the results.
        >>> r = Results.create_example()
        >>> r.select('how_feeling').first()
        'Bad'
        """
        return list(self[0].values())[0][0]

    def mutate(
        self, new_var_string, functions_dict=None, in_place=True
    ) -> Union[Results, None]:
        """
        Creates a value value in 'results' as if has been asked as part of the survey.
        It splits the new_var_string at the "=" and uses simple_eval

        >>> r = Results.create_example()
        >>> r.mutate('how_feeling_x = how_feeling + "x"').select('how_feeling_x')
        [{'answer.how_feeling_x': ['Badx', 'Badx', 'Greatx', 'Greatx']}]

        TODO: Make sure left is valid python name
        TODO: Do something smarter than serialize/deserialize the Result
        """
        raw_var_name, expression = new_var_string.split("=", 1)

        var_name = raw_var_name.strip()
        new_data = []
        for result in self.filtered_data:
            try:
                # the combined_dict is a Result-level dictionary mapping keys to values
                # e.g., {'agent': {'status':'OK'}} as well as {'status':'OK'}
                # This can deal w/ the case whree the user uses dot notation
                if functions_dict is not None:
                    evaluator = EvalWithCompoundTypes(
                        names=result.combined_dict, functions=functions_dict
                    )
                else:
                    evaluator = EvalWithCompoundTypes(names=result.combined_dict)

                value = evaluator.eval(expression)

                # this bit of weirdness is done because we need a deep copy
                # but because result is an iterator, it's got a lock on it (i think)

                json_string = json.dumps(result.to_dict())

                ## serialization is noisy so we're going to suppress it
                original_stdout = (
                    sys.stdout
                )  # Save a reference to the original standard output
                with io.StringIO() as buffer:
                    sys.stdout = buffer  # Redirect stdout to buffer
                    new_result = Result.from_dict(json.loads(json_string))
                    captured_output = (
                        buffer.getvalue()
                    )  # Get printed content from buffer

                sys.stdout = original_stdout  # Restore original stdout

                new_result["answer"][var_name] = value
                new_data.append(new_result)
            except Exception as e:
                print(f"Exception:{e}")

        if in_place:
            self.data = new_data
            self.filtered_data = new_data
            self.created_columns = self.created_columns + [var_name]
            return None
        else:
            new_results = Results(
                survey=self.survey,
                data=new_data,
                original_data=self.original_data,
                filtered_data=new_data,
                state=self.state,
                created_columns=self.created_columns + [var_name],
            )

            # if it was in a selected state, keep it that way
            if self.state == ResultsStates.SELECTED:
                relevent_columns = self.relevant_columns()
                new_results = new_results.select(*relevent_columns)

            return new_results

    def select(self, *columns: Union[str, list[str]]) -> Results:
        """
        This selects data from the results and turns it into a format like so:
        >>> results = Results.create_example()
        >>> results.select('how_feeling')
        [{'answer.how_feeling': ['Bad', 'Bad', 'Great', 'Great']}]
        """
        # We start by changing the data back to format where self.data is a list of Result
        # objects. However, it can be filtered, so we need to use self.filtered_data.

        self.data = self.filtered_data

        # we're doing to populate this with the data we want to fetch
        to_fetch = defaultdict(list)

        if not columns or columns == ("*",) or columns == (None,):
            columns = ("*.*",)

        if isinstance(columns[0], list):
            columns = tuple(columns[0])

        new_data = []
        items_in_order = []
        for column in columns:
            # a user could pass 'result.how_feeling' or just 'how_feeling'
            parsed_data_type, parsed_key = self._parse_column(column)
            if parsed_data_type == "*":
                data_types = ["answer", "scenario", "agent", "model"]
            else:
                if parsed_data_type not in ["answer", "scenario", "agent", "model"]:
                    raise Exception(f"Data type {parsed_data_type} not found in data")
                data_types = [parsed_data_type]

            found_once = False  # we need to track this to make sure we found the key at least once
            for data_type in data_types:
                relevant_keys = self._data_type_to_keys[data_type]
                if (
                    parsed_key == "*"
                ):  # wildcard, we'll get all the keys for that data type
                    found_once = True
                    to_fetch[data_type] = relevant_keys
                    items_in_order.extend([data_type + "." + k for k in relevant_keys])
                else:
                    for key in relevant_keys:
                        if key == parsed_key:
                            found_once = True
                            to_fetch[data_type].append(key)
                            items_in_order.append(data_type + "." + key)

            if not found_once:
                raise Exception(f"Key {parsed_key} not found in data")

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

        # print(f"Items in order: {items_in_order}")
        new_results = Results(
            survey=self.survey,
            data=sorted(new_data, key=sort_by_key_order),
            filtered_data=self.filtered_data,
            original_data=self.original_data,
            report_items=self.report_items,
            created_columns=self.created_columns,
            state=ResultsStates.SELECTED,
        )
        return new_results

    def print(
        self,
        pretty_labels=None,
        drop=None,
        sort_by=None,
        reverse=True,
        filename=None,
        html=False,
        interactive=False,
        split_at_dot=True,
    ):
        """
        This prints the results in a nice format. It's not fluent.
        """
        if sort_by is not None:
            self = self.sort_by(sort_by, reverse=reverse)

        if pretty_labels is None:
            pretty_labels = {}

        if self.state == ResultsStates.SELECTED:
            new_data = []
            for entry in self:
                key, list_of_values = list(entry.items())[0]
                new_data.append({pretty_labels.get(key, key): list_of_values})
            else:
                if not html:
                    print_list_of_dicts_with_rich(
                        new_data, filename=filename, split_at_dot=split_at_dot
                    )
                else:
                    print_list_of_dicts_as_html_table(
                        new_data, filename=None, interactive=interactive
                    )

        elif self.state == ResultsStates.ORIGINAL:
            selected_self = self.select()
            selected_self.print(
                pretty_labels=pretty_labels,
                drop=drop,
                sort_by=sort_by,
                reverse=reverse,
                filename=filename,
            )

    def sort_by(self, column, reverse=True) -> Results:
        "Sorts the results by a column"

        data_type, key = self._parse_column(column)

        def to_numeric_if_possible(v):
            try:
                return float(v)
            except:
                return v

        if self.state == ResultsStates.ORIGINAL:
            new_data = sorted(
                self.data,
                key=lambda x: to_numeric_if_possible(x.get_value(data_type, key)),
                reverse=reverse,
            )
            new_filtered_data = sorted(
                self.filtered_data,
                key=lambda x: to_numeric_if_possible(x.get_value(data_type, key)),
                reverse=reverse,
            )
            new_results = Results(
                survey=self.survey,
                data=new_data,
                original_data=self.original_data,
                filtered_data=new_filtered_data,
                report_items=self.report_items,
                created_columns=self.created_columns,
                state=self.state,
            )
            return new_results
        elif self.state == ResultsStates.SELECTED:
            relevant_columns = self.relevant_columns()
            if len(self.filtered_data) < len(self.original_data):
                print("Warning: sorting on a filtered dataset removes filters")
            self.restore()
            return self.sort_by(column, reverse=reverse).select(*relevant_columns)
        else:
            raise Exception("Cannot sort on a tabular dataset yet")

    def filter(self, expression) -> Results:
        """
        This filters a result based on the expression that is passed in.
        >>> r = Results.create_example()
        >>> r.filter("how_feeling == 'Great'").select('how_feeling')
        [{'answer.how_feeling': ['Great', 'Great']}]
        >>> r.filter("how_feeling == 'Nothing'").select('how_feeling')
        [{'answer.how_feeling': []}]
        """
        new_data = []
        for result in self.filtered_data:
            try:
                # the combined_dict is a Result-level dictionary mapping keys to values
                # e.g., {'agent': {'status':'OK'}} as well as {'status':'OK'}
                # This can deal w/ the case whree the user uses dot notation
                evaluator = EvalWithCompoundTypes(names=result.combined_dict)
                if eval_result := evaluator.eval(expression):
                    new_data.append(result)
            except Exception as e:
                print(f"Exception:{e}")

        new_results = Results(
            survey=self.survey,
            data=new_data,
            original_data=self.original_data,
            filtered_data=new_data,
            report_items=self.report_items,
            created_columns=self.created_columns,
            state=self.state,
        )

        # if it was in a selected state, keep it that way
        if self.state == ResultsStates.SELECTED:
            relevent_columns = self.relevant_columns()
            new_results = new_results.select(*relevent_columns)

        return new_results

    def relevant_columns(self) -> set:
        """
        >>> r = Results.create_example()
        >>> keys = r.relevant_columns()
        >>> keys == {'elapsed', 'temperature', 'agent', 'scenario', 'answer', 'use_cache', 'how_feeling', 'frequency_penalty', 'max_tokens', 'model', 'status', 'top_p', 'period', 'presence_penalty'}
        True
        >>> r.select('how_feeling').relevant_columns()
        {'answer.how_feeling'}
        """
        if self.state == ResultsStates.SELECTED:
            keys = set([list(d.keys())[0] for d in self.data])
        else:
            keys = set({})
            for observation in self:
                observation_keys = set(observation.combined_dict.keys())
                keys = keys.union(observation_keys)
        return keys

    def to_dict(self):
        self.restore()  # restore to original state before converting to dict
        new_data = []
        for observation in self:
            new_observation = observation.to_dict()
            new_data.append(new_observation)
        return {
            "data": new_data,
            "survey": self.survey.to_dict(),
            "agents": [a.to_dict() for a in self.agents],
        }

    @classmethod
    def from_dict(cls, data: dict):
        from edsl.surveys.Survey import Survey
        from edsl.results.Result import Result
        from edsl.agents import Agent

        survey = Survey.from_dict(data["survey"])
        # agents = [Agent.from_dict(a) for a in data["agents"]]
        observations = [Result.from_dict(r) for r in data["data"]]
        new_cls = cls(survey=survey, data=observations)
        # new_cls.agents = agents
        return new_cls

    @classmethod
    def load(cls, json_file):
        if is_gzipped(json_file):
            import gzip

            with gzip.open(json_file, "rb") as f:
                data = json.load(f)
        else:
            with open(json_file, "r") as f:
                data = json.load(f)
        return cls.from_dict(data)

    @property
    def question_names(self):
        return list(self.survey.question_names)

    @property
    def agents(self):
        return [r.agent for r in self.original_data]

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

    import doctest

    doctest.testmod()
