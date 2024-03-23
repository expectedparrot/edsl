"""
The Results object is the result of running a survey. 
It is not typically instantiated directly, but is returned by the run method of a `Job` object.

.. code-block:: python

    job = Job.example()
    results = job.run()

It is a list of Result objects, each of which represents a single response to the survey and can be manipulated like a list.

Creating tables by selecting and printing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A results object has many 'columns' that can be selected and printed.
For example, to print a table of the `how_feeling` column:

.. code-block:: python

    results = Results.example()
    results.select("how_feeling").print()

This will print a table of the `how_feeling` column.

.. code-block:: text

    ┏━━━━━━━━━━━━━━┓
    ┃ answer       ┃
    ┃ .how_feeling ┃
    ┡━━━━━━━━━━━━━━┩
    │ OK           │
    ├──────────────┤
    │ Great        │
    ├──────────────┤
    │ Terrible     │
    ├──────────────┤
    │ OK           │
    └──────────────┘

Filtering
^^^^^^^^^

You can filter the results by using the `filter` method.

.. code-block:: python

    results = Results.example()
    results.filter("how_feeling == 'Great'").select("how_feeling").print()

which will print a table of the `how_feeling` column where the value is 'Great'.

.. code-block:: text

    ┏━━━━━━━━━━━━━━┓
    ┃ answer       ┃
    ┃ .how_feeling ┃
    ┡━━━━━━━━━━━━━━┩
    │ Great        │
    └──────────────┘    


Interacting via SQL
^^^^^^^^^^^^^^^^^^^
You can interact with the results via SQL.

.. code-block:: python

    results = Results.example()
    results.sql("select data_type, key, value from self where data_type = 'answer' limit 3", shape="long")


Exporting to other formats (pandas, csv, etc.)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can export the results to other formats, such as pandas DataFrames or csv files.

.. code-block:: python

    results = Results.example()
    results.to_pandas()

"""
from __future__ import annotations
import json
import io
from collections import UserList, defaultdict
from typing import Optional
from rich.console import Console

from simpleeval import EvalWithCompoundTypes
from typing import Any, Type, Union

from edsl.exceptions.results import (
    ResultsBadMutationstringError,
    ResultsColumnNotFoundError,
    ResultsInvalidNameError,
    ResultsMutateError,
    ResultsFilterError,
)
from edsl.agents import Agent
from edsl.data import CRUD
from edsl.language_models.LanguageModel import LanguageModel
from edsl.results.Dataset import Dataset
from edsl.results.Result import Result
from edsl.results.ResultsExportMixin import ResultsExportMixin
from edsl.scenarios import Scenario
from edsl.surveys import Survey
from edsl.utilities import (
    is_gzipped,
    is_valid_variable_name,
    print_public_methods_with_doc,
    shorten_string,
    is_notebook,
)

from edsl.results.ResultsDBMixin import ResultsDBMixin


class Mixins(ResultsExportMixin, ResultsDBMixin):
    pass


# These are only made available if the user has installed
# our package from pip with the [report] option
try:
    from edsl.report.RegressionMixin import RegressionMixin

    Mixins = type("Mixins", (RegressionMixin, Mixins), {})
except (ImportError, ModuleNotFoundError):
    pass

try:
    from edsl.report.ResultsFetchMixin import ResultsFetchMixin

    Mixins = type("Mixins", (ResultsFetchMixin, Mixins), {})
except (ImportError, ModuleNotFoundError):
    pass

try:
    from edsl.report.ResultsOutputMixin import ResultsOutputMixin

    Mixins = type("Mixins", (ResultsOutputMixin, Mixins), {})
except (ImportError, ModuleNotFoundError):
    pass

from edsl.Base import Base


class Results(UserList, Mixins, Base):
    """
    This class is a UserList of Result objects.

    It is instantiated with a `Survey` and a list of `Result` objects. 
    It can be manipulated in various ways with select, filter, mutate, etc.
    It also has a list of created_columns, which are columns that have been created with `mutate` and are not part of the original data.
    """

    known_data_types = [
        "answer",
        "scenario",
        "agent",
        "model",
        "prompt",
        "raw_model_response",
        "iteration",
    ]

    def __init__(
        self,
        survey: Optional[Survey] = None,
        data: Optional[list[Result]] = None,
        created_columns: Optional[list[str]] = None,
        job_uuid: Optional[str] = None,
        total_results: Optional[int] = None,
    ):
        """Instantiate a `Results` object with a survey and a list of `Result` objects.

        :param survey: A Survey object.
        :param data: A list of Result objects.
        :param created_columns: A list of strings that are created columns.
        :param job_uuid: A string representing the job UUID.
        :param total_results: An integer representing the total number of results.
        """
        super().__init__(data)
        self.survey = survey
        self.created_columns = created_columns or []
        self._job_uuid = job_uuid
        self._total_results = total_results

        if hasattr(self, "_add_output_functions"):
            self._add_output_functions()

    ######################
    # Streaming methods
    ######################

    def code(self):
        raise NotImplementedError

    def __getitem__(self, i):
        if isinstance(i, slice):
            # Return a sliced view of the list
            return self.__class__(survey=self.survey, data=self.data[i])
        else:
            # Return a single item
            return self.data[i]

    def _update_results(self) -> None:
        if self._job_uuid and len(self.data) < self._total_results:
            results = [
                Result(
                    agent=Agent.from_dict(json.loads(r.agent)),
                    scenario=Scenario.from_dict(json.loads(r.scenario)),
                    model=LanguageModel.from_dict(json.loads(r.model)),
                    iteration=1,
                    answer=json.loads(r.answer),
                )
                for r in CRUD.read_results(self._job_uuid)
            ]
            self.data = results

    def __repr__(self) -> str:
        self._update_results()
        if self._job_uuid and len(self.data) < self._total_results:
            print(f"Completeness: {len(self.data)}/{self._total_results}")
        data = [repr(result) for result in self.data]
        if is_notebook():
            return self.rich_print()
        else:
            return f"Results(data = {data}, survey = {repr(self.survey)}, created_columns = {self.created_columns})"

    def to_dict(self) -> dict[str, Any]:
        """Converts the Results object to a dictionary.
        
        The dictionary can be quite large, as it includes all of the data in the Results object.

        Example: Illustrating just the keys of the dictionary.

        >>> r = Results.example()
        >>> r.to_dict().keys()
        dict_keys(['data', 'survey', 'created_columns'])
        """
        return {
            "data": [result.to_dict() for result in self.data],
            "survey": self.survey.to_dict(),
            "created_columns": self.created_columns,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Results:
        """Converts a dictionary to a Results object.
        
        :param data: A dictionary representation of a Results object.

        Example:
        
        >>> r = Results.example()
        >>> d = r.to_dict()
        >>> r2 = Results.from_dict(d)
        >>> r == r2
        True
        """
        results = cls(
            survey=Survey.from_dict(data["survey"]),
            data=[Result.from_dict(r) for r in data["data"]],
            created_columns=data.get("created_columns", None),
        )
        return results

    ######################
    ## Convenience methods
    ## & Report methods
    ######################
    @property
    def _key_to_data_type(self) -> dict[str, str]:
        """
        Return a mapping of keys (how_feeling, status, etc.) to strings representing data types.
         
        Objects such as Agent, Answer, Model, Scenario, etc.
        - Uses the key_to_data_type property of the Result class.
        - Includes any columns that the user has created with `mutate`
        """
        d = {}
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
        {'agent': {'agent_name', 'status'}, 'answer': {'how_feeling', 'how_feeling_comment', 'how_feeling_yesterday', 'how_feeling_yesterday_comment'}, 'model': {'frequency_penalty', 'use_cache', 'temperature', 'max_tokens', 'presence_penalty', 'top_p', 'model'}, 'prompt': {'how_feeling_system_prompt', 'how_feeling_user_prompt', 'how_feeling_yesterday_system_prompt', 'how_feeling_yesterday_user_prompt'}, 'raw_model_response': {'how_feeling_raw_model_response', 'how_feeling_yesterday_raw_model_response'}, 'scenario': {'period'}}

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
        ['agent.agent_name', 'agent.status', 'answer.how_feeling', 'answer.how_feeling_comment', 'answer.how_feeling_yesterday', 'answer.how_feeling_yesterday_comment', 'iteration.iteration', 'model.frequency_penalty', 'model.max_tokens', 'model.model', 'model.presence_penalty', 'model.temperature', 'model.top_p', 'model.use_cache', 'prompt.how_feeling_system_prompt', 'prompt.how_feeling_user_prompt', 'prompt.how_feeling_yesterday_system_prompt', 'prompt.how_feeling_yesterday_user_prompt', 'raw_model_response.how_feeling_raw_model_response', 'raw_model_response.how_feeling_yesterday_raw_model_response', 'scenario.period']
        """
        column_names = [f"{v}.{k}" for k, v in self._key_to_data_type.items()]
        return sorted(column_names)

    @property
    def answer_keys(self) -> dict[str, str]:
        """Return a mapping of answer keys to question text.
        
        Example: 

        >>> r = Results.create_example()
        >>> r.answer_keys
        {'how_feeling': 'How are you this {{ period }}?', 'how_feeling_yesterday': 'How were you feeling yesterday {{ period }}?'}   
        """
        if not self.survey:
            raise Exception("Survey is not defined so no answer keys are available.")
        
        answer_keys = self._data_type_to_keys["answer"]
        answer_keys = {k for k in answer_keys if "_comment" not in k}
        questions_text = [
            self.survey.get_question(k).question_text for k in answer_keys
        ]
        short_question_text = [shorten_string(q, 80) for q in questions_text]
        return dict(zip(answer_keys, short_question_text))

    @property
    def agents(self) -> list[Agent]:
        """Return a list of all of the agents in the Results.
        
        Example:
        
        >>> r = Results.example()
        >>> r.agents
        [Agent(traits = {'status': 'Joyful'}), Agent(traits = {'status': 'Joyful'}), Agent(traits = {'status': 'Sad'}), Agent(traits = {'status': 'Sad'})]

        """
        return [r.agent for r in self.data]

    @property
    def models(self) -> list[Type[LanguageModel]]:
        """Return a list of all of the models in the Results.
        
        Example:

        >>> r = Results.example()
        >>> r.models[0]
        LanguageModelOpenAIFour(model = 'gpt-4-1106-preview', parameters={'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1, 'frequency_penalty': 0, 'presence_penalty': 0, 'use_cache': True})
        
        """
        return [r.model for r in self.data]

    @property
    def scenarios(self) -> list[Scenario]:
        """Return a list of all of the scenarios in the Results.
    
        >>> r.scenarios
        [{'period': 'morning'}, {'period': 'afternoon'}, {'period': 'morning'}, {'period': 'afternoon'}]
    
        """
        return [r.scenario for r in self.data]

    @property
    def agent_keys(self) -> set[str]:
        """Return a set of all of the keys that are in the Agent data.

        Example:

        >>> r.agent_keys
        {'agent_name', 'status'}
        """
        return self._data_type_to_keys["agent"]

    @property
    def model_keys(self) -> set[str]:
        """Return a set of all of the keys that are in the LanguageModel data.
        
        >>> r = Results.create_example()
        >>> r.model_keys
        {'frequency_penalty', 'use_cache', 'temperature', 'max_tokens', 'presence_penalty', 'top_p', 'model'}
        """
        return self._data_type_to_keys["model"]

    @property
    def scenario_keys(self) -> set[str]:
        """Return a set of all of the keys that are in the Scenario data.
        
        >>> r = Results.example()
        >>> r.scenario_keys
        {'period'}
        """
        return self._data_type_to_keys["scenario"]

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
        return list(self.survey.question_names)

    @property
    def all_keys(self) -> set[str]:
        """Returns a set of all of the keys that are in the Results.
        
        Example:

        >>> r = Results.example()
        >>> r.all_keys
        {'agent.agent_name', 'agent.status', 'answer.how_feeling', 'answer.how_feeling_comment', 'answer.how_feeling_yesterday', 'answer.how_feeling_yesterday_comment', 'iteration.iteration', 'model.frequency_penalty', 'model.max_tokens', 'model.model', 'model.presence_penalty', 'model.temperature', 'model.top_p', 'model.use_cache', 'prompt.how_feeling_system_prompt', 'prompt.how_feeling_user_prompt', 'prompt.how_feeling_yesterday_system_prompt', 'prompt.how_feeling_yesterday_user_prompt', 'raw_model_response.how_feeling_raw_model_response', 'raw_model_response.how_feeling_yesterday_raw_model_response', 'scenario.period'}      
        """
        answer_keys = set(self.answer_keys)
        return (
            answer_keys.union(self.agent_keys)
            .union(self.scenario_keys)
            .union(self.model_keys)
        )

    def relevant_columns(self) -> set[str]:
        """Return all of the columns that are in the Results.
        
        Example:

        >>> r = Results.example()
        >>> r.relevant_columns()
        {'agent.agent_name', 'agent.status', 'answer.how_feeling', 'answer.how_feeling_comment', 'answer.how_feeling_yesterday', 'answer.how_feeling_yesterday_comment', 'iteration.iteration', 'model.frequency_penalty', 'model.max_tokens', 'model.model', 'model.presence_penalty', 'model.temperature', 'model.top_p', 'model.use_cache', 'prompt.how_feeling_system_prompt', 'prompt.how_feeling_user_prompt', 'prompt.how_feeling_yesterday_system_prompt', 'prompt.how_feeling_yesterday_user_prompt', 'raw_model_response.how_feeling_raw_model_response', 'raw_model_response.how_feeling_yesterday_raw_model_response', 'scenario.period'}
        
        """
        return set().union(
            *(observation.combined_dict.keys() for observation in self.data)
        )

    def _parse_column(self, column: str) -> tuple[str, str]:
        """
        Parses a column name into a tuple containing a data type and a key.

        >>> r = Results.create_example()
        >>> r._parse_column("answer.how_feeling")
        ('answer', 'how_feeling')

        The standard way a column is specified is with a dot-separated string, e.g. _parse_column("agent.status")
        But you can also specify a single key, e.g. "status", in which case it will look up the data type.
        """
        if "." in column:
            data_type, key = column.split(".")
        else:
            try:
                data_type, key = self._key_to_data_type[column], column
            except KeyError:
                raise ResultsColumnNotFoundError(f"Column {column} not found in data")
        return data_type, key

    def first(self) -> Result:
        """Return the first observation in the results.

        Example:

        >>> r = Results.example()
        >>> r.first()
        Result(agent = Agent(traits = {'status': 'Joyful'}), scenario = {'period': 'morning'}, model = LanguageModelOpenAIFour(model = 'gpt-4-1106-preview', parameters = {'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1, 'frequency_penalty': 0, 'presence_penalty': 0, 'use_cache': True}), iteration = 1, answer = {'how_feeling': 'OK'})

        """
        return self.data[0]

    def mutate(self, new_var_string: str, functions_dict: Optional[dict] = None) -> Results:
        """
        Creates a value in the Results object as if has been asked as part of the survey.

        :param new_var_string: A string that is a valid Python expression.
        :param functions_dict: A dictionary of functions that can be used in the expression. The keys are the function names and the values are the functions themselves.

        It splits the new_var_string at the "=" and uses simple_eval

        Example:

        >>> r = Results.example()
        >>> r.mutate('how_feeling_x = how_feeling + "x"').select('how_feeling_x')
        [{'answer.how_feeling_x': ['Badx', 'Badx', 'Greatx', 'Greatx']}]
        """
        # extract the variable name and the expression
        if "=" not in new_var_string:
            raise ResultsBadMutationstringError(
                f"Mutate requires an '=' in the string, but '{new_var_string}' doesn't have one."
            )
        raw_var_name, expression = new_var_string.split("=", 1)
        var_name = raw_var_name.strip()
        if not is_valid_variable_name(var_name):
            raise ResultsInvalidNameError(f"{var_name} is not a valid variable name.")

        # create the evaluator
        functions_dict = functions_dict or {}

        def create_evaluator(result: Result) -> EvalWithCompoundTypes:
            return EvalWithCompoundTypes(
                names=result.combined_dict, functions=functions_dict
            )

        def new_result(old_result: Result, var_name: str) -> Result:
            evaluator = create_evaluator(old_result)
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

    def select(self, *columns: Union[str, list[str]]) -> Dataset:
        """
        This selects data from the results and turns it into a format like so:

        :param columns: A list of strings, each of which is a column name. The column name can be a single key, e.g. "how_feeling", or a dot-separated string, e.g. "answer.how_feeling".

        Example:

        >>> results = Results.create_example()
        >>> results.select('how_feeling')
        [{'answer.how_feeling': ['Bad', 'Bad', 'Great', 'Great']}]
        """

        if not columns or columns == ("*",) or columns == (None,):
            columns = ("*.*",)

        if isinstance(columns[0], list):
            columns = tuple(columns[0])

        def get_data_types_to_return(parsed_data_type):
            if parsed_data_type == "*":  # they want all of the columns
                return self.known_data_types
            else:
                if parsed_data_type not in self.known_data_types:
                    raise Exception(
                        f"Data type {parsed_data_type} not found in data. Did you mean one of {self.known_data_types}"
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

    def sort_by(self, column, reverse: bool=False) -> Results:
        """Sort the results by a column.

        :param column: A string that is a column name. 
        :param reverse: A boolean that determines whether to sort in reverse order.

        The column name can be a single key, e.g. "how_feeling", or a dot-separated string, e.g. "answer.how_feeling".
        
        Example:

        >>> r = Results.example()
        >>> r.sort_by('how_feeling', reverse = False).select('how_feeling').print()
        ┏━━━━━━━━━━━━━━┓
        ┃ answer       ┃
        ┃ .how_feeling ┃
        ┡━━━━━━━━━━━━━━┩
        │ Great        │
        ├──────────────┤
        │ OK           │
        ├──────────────┤
        │ OK           │
        ├──────────────┤
        │ Terrible     │
        └──────────────┘
        >>> r.sort_by('how_feeling', reverse = True).select('how_feeling').print()
        ┏━━━━━━━━━━━━━━┓
        ┃ answer       ┃
        ┃ .how_feeling ┃
        ┡━━━━━━━━━━━━━━┩
        │ Terrible     │
        ├──────────────┤
        │ OK           │
        ├──────────────┤
        │ OK           │
        ├──────────────┤
        │ Great        │
        └──────────────┘

        """

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

    def filter(self, expression: str) -> Results:
        """
        Filter based on the given expression and returns the filtered `Results`.

        :param expression: A string expression that evaluates to a boolean. The expression is applied to each element in `Results` to determine whether it should be included in the filtered results.

        The `expression` parameter is a string that must resolve to a boolean value when evaluated against each element in `Results`.
        This expression is used to determine which elements to include in the returned `Results`.

        Example usage: Create an example `Results` instance and apply filters to it:

        >>> r = Results.example()
        >>> r.filter("how_feeling == 'Great'").select('how_feeling').print()
        ┏━━━━━━━━━━━━━━┓
        ┃ answer       ┃
        ┃ .how_feeling ┃
        ┡━━━━━━━━━━━━━━┩
        │ Great        │
        └──────────────┘

        Example usage: Using an OR operator in the filter expression.
        
        >>> r.filter("how_feeling == 'Great' or how_feeling == 'Terrible'").select('how_feeling').print()
        ┏━━━━━━━━━━━━━━┓
        ┃ answer       ┃
        ┃ .how_feeling ┃
        ┡━━━━━━━━━━━━━━┩
        │ Great        │
        ├──────────────┤
        │ Terrible     │
        └──────────────┘        
        """

        def create_evaluator(result):
            """Create an evaluator for the given result.
            The 'combined_dict' is a mapping of all values for that Result object.
            """
            return EvalWithCompoundTypes(names=result.combined_dict)

        try:
            # iterates through all the results and evaluates the expression
            new_data = [
                result
                for result in self.data
                if create_evaluator(result).eval(expression)
            ]
        except Exception as e:
            print(f"Exception:{e}")
            raise ResultsFilterError(f"Error in filter. Exception:{e}")

        return Results(survey=self.survey, data=new_data, created_columns=None)

    @classmethod
    def example(cls, debug: bool = False) -> Results:
        """Return an example `Results` object.

        Example usage:
        
        >>> r = Results.example()
       
        :param debug: if False, uses actual API calls
        """
        from edsl.jobs import Jobs

        job = Jobs.example()
        results = job.run(debug=debug)
        return results

    def rich_print(self):
        """Displays an object as a table."""
        with io.StringIO() as buf:
            console = Console(file=buf, record=True)

            for index, result in enumerate(self):
                console.print(f"Result {index}")
                console.print(result.rich_print())

            return console.export_text()

    def __str__(self):
        return self.rich_print()


def main():  # pragma: no cover
    """Calls the OpenAI API credits"""
    from edsl.results.Results import Results

    results = Results.example(debug=True)
    print(results.filter("how_feeling == 'Great'").select("how_feeling"))
    print(results.mutate("how_feeling_x = how_feeling + 'x'").select("how_feeling_x"))


if __name__ == "__main__":
    print(Results.example())

    r = Results.example()
    # db_row = list(r[0].rows(1))
    db_rows = list(r._rows())

    print(r.columns)
