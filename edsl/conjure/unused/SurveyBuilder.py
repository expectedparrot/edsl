from abc import ABC, abstractmethod
import os
import random
from typing import Dict, Any, List, Callable, Optional
from collections import UserDict

from pydantic import ValidationError

from edsl.utilities.utilities import create_valid_var_name
from edsl.surveys.Survey import Survey
from edsl.conjure.RawResponseColumn import RawResponseColumn

from edsl.conjure.SurveyResponses import SurveyResponses
from edsl.conjure.DictWithIdentifierKeys import DictWithIdentifierKeys
from edsl.conjure.ReplacementFinder import ReplacementFinder

from edsl.conjure.utilities import ValidFilename

from edsl.agents.Agent import Agent
from edsl.agents.AgentList import AgentList

from edsl.conjure.RawResponses import RawResponses
from edsl.conjure.CreateAgents import CreateAgents
from edsl.conjure.CreateSurvey import CreateSurvey
from edsl.conjure.CreateResults import CreateResults


class FileHandlerABC(ABC):
    dataset_name = ValidFilename()

    def __init__(
        self,
        datafile_name: str,
        skiprows: Optional[int] = None,
        question_row: Optional[int] = None,
        verbose: bool = False,
    ):
        self.datafile_name = datafile_name
        self.skiprows = skiprows
        self.question_row = question_row
        self.verbose = verbose

    @abstractmethod
    def get_responses(self) -> Dict:
        """Returns all of the raw responses, as a dataframe"""
        pass

    @abstractmethod
    def get_question_name_to_text(self) -> Dict[str, str]:
        pass

    @abstractmethod
    def get_question_name_to_answer_book(self) -> Dict[str, Dict[str, str]]:
        pass


class SurveyBuilder(UserDict, ABC):
    """A ABC class to represent the process of building a survey and results from an external format"""

    datafile_name = ValidFilename()

    def __init__(
        self,
        datafile_name: str,
        skiprows: Optional[int] = None,
        question_row: Optional[int] = None,
        verbose: bool = False,
        raw_responses: Optional[dict] = None,
        responses: Optional[dict] = None,
        data: Optional[dict] = None,
    ):
        """Initialize the SurveyBuilder with the given datafile_name.

        :param datafile_name: The name of the datafile to be used.
        :param sample_size: The number of observations to sample from the dataset.
        :param compute_results: Whether to compute the results or not.

        The SurveyBuilder will read the datafile_name and create a survey from it.

        >>> sb = SurveyBuilder.example()
        >>> sb.responses
        {'q1': ['1', '4'], 'q2': ['2', '5'], 'q3': ['3', '6']}
        >>> sb.question_name_to_text
        {'q1': 'Q1', 'q2': 'Q2', 'q3': 'Q3'}

        >>> sb.data['q1']
        RawResponseColumn(question_name="q1", question_text="Q1", raw_responses=['1', '4'], responses=['1', '4'], unqiue_responses=defaultdict(<class 'int'>, {'1': 1, '4': 1}), answer_codebook={})
        """
        self.datafile_name = datafile_name
        self.skiprows = skiprows
        self.verbose = verbose
        self.question_row = question_row

        self.replacement_finder = ReplacementFinder({})

        self.raw_responses = raw_responses
        self.responses = responses
        self.data = data

    @property
    def raw_responses(self):
        """Return the raw responses as a dictionary.
        e.g.,
        {'How are you?': ['Good', 'Bad', 'Ugly'], 'What is your name?': ['John', 'Jane']}
        """
        return self._raw_responses

    @raw_responses.setter
    def raw_responses(self, value):
        if value is None:
            self._raw_responses = self.get_responses()
        else:
            self._raw_responses = value

    @property
    def responses(self):
        """Return the responses as a dictionary with valid Python identifiers as keys.
        e.g.,
        {'how_are_you': ['Good', 'Bad', 'Ugly'], 'what_is_your_name': ['John', 'Jane']}
        """
        return self._responses

    @responses.setter
    def responses(self, value):
        if value is None:
            self._responses = DictWithIdentifierKeys(
                self.raw_responses,
                verbose=self.verbose,
                replacement_finder=self.replacement_finder,
            )
        else:
            self._responses = value
        return self._responses

    @property
    def question_names(self) -> List[str]:
        """Return the question names"""
        return list(self.responses.keys())

    @property
    def question_texts(self) -> List[str]:
        """Return the the question texts"""
        return list(self.raw_responses.keys())

    @property
    def question_text_to_question_name(self) -> dict:
        """Return a dictionary mapping question text's to question names"""
        if not hasattr(self, "_question_text_to_question_name"):
            self._question_text_to_question_name = dict(
                zip(self.question_texts, self.question_names)
            )
        return self._question_text_to_question_name

    @property
    def question_name_to_question_text(self):
        if not hasattr(self, "_question_name_to_text"):
            self._question_name_to_question_text = dict(
                zip(self.question_names, self.question_texts)
            )
        return self._question_name_to_question_text

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        if value is None:
            self._data = RawResponses(
                responses=self.responses,
                answer_codebook={},
                question_name_to_question_text=self.question_name_to_question_text,
            )
        else:
            self._data = value

    def generate_survey(self):
        """Generate the survey from the data."""
        survey, survey_failures = CreateSurvey(self)()
        return survey, survey_failures

    def generate_agents(self):
        """Generate the agents from the data."""

        agents, agent_failures = CreateAgents(self.data)()
        return agents, agent_failures

    def generate_results(self):
        """Generate the results from the survey and agents."""
        return CreateResults(self.survey, self.agents)()

        # self.results = self.create_results()

    def to_dict(self):
        return {
            "datafile_name": self.datafile_name,
            #            "survey": self.survey.to_dict(),
            # "agents": None if self.agents is None else self.agents.to_dict(),
            # "results": None if self.results is None else self.results.to_dict(),
            "sample_size": self.sample_size,
            # "num_survey_failures": len(self.survey_failures),
            "raw_responses": self.raw_responses,
            "responses": self.responses,
            # "question_name_to_question_text": self.question_name_to_question_text,
            # "question_text_to_question_name": self.question_text_to_question_name
        }

    @classmethod
    def from_dict(cls, d):
        cls(**d)

    def to_dataset(self):
        from edsl.results.Dataset import Dataset

        return Dataset([{k: v} for k, v in self.raw_responses.items()])

    def placeholder(
        self, datafile_name: str, compute_results: bool = True, verbose: bool = False
    ):
        self.replacement_finder = ReplacementFinder({})

        raw_responses: SurveyResponses = self.get_responses()

        if self.verbose:
            print("\n\n\nNow getting responses")

        self.responses = DictWithIdentifierKeys(
            raw_responses,
            verbose=self.verbose,
            replacement_finder=self.replacement_finder,
        )

        if self.verbose:
            print("\n\n\nResponses completed")

        if self.verbose:
            print("The replacement_finder is", self.replacement_finder)

        if self.verbose:
            print("Now getting question name to text")
        self.question_name_to_text = DictWithIdentifierKeys(
            self.get_question_name_to_text(),
            verbose=self.verbose,
            replacement_finder=self.replacement_finder,
        )

        # This should be a dictionary mapping question names to question text e.g.,
        # {'q1': 'How are you?'}

        self.question_name_to_answer_book = DictWithIdentifierKeys(
            self.get_question_name_to_answer_book(),
            verbose=self.verbose,
            replacement_finder=self.replacement_finder,
        )
        self.compute_results = compute_results

        data = {}
        for question_name, raw_responses in self.responses.items():
            raw_question_response = RawResponseColumn(
                question_name=question_name,
                raw_responses=raw_responses,
                answer_codebook=self.question_name_to_answer_book[question_name],
                question_text=self.question_name_to_text[question_name],
            )
            data[question_name] = raw_question_response

        super().__init__(data)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.datafile_name})"

    def process(self) -> None:
        self.survey, self.survey_failures = self.create_survey()

        if self.compute_results:
            self.agents, self.agent_failures = self.create_agents()
            self.results = self.create_results()
            # remove the direct question answering method
            [agent.remove_direct_question_answering_method() for agent in self.agents]
        else:
            self.agents = None
            self.results = None

    def create_agents(self, question_keys_as_traits: List[str] = None):
        """Returns a list of agents, and a dictionary of failures.

        :param sample_size: The number of agents to sample from the dataset.
        :param question_keys_as_traits: A list of question keys to use as traits.

        These agents are special in that they have an 'answer_question_directly'
        method that allows them to answer questions directly when presented with
        the question_name. This is useful because in self.Agents, these agents can
        bypass the LLM call.
        """
        if question_keys_as_traits is None:
            question_keys_as_traits = list(self.data.keys())

        from edsl.agents.Agent import Agent
        from edsl.agents.AgentList import AgentList

        failures = {}

        def construct_answer_dict_function(answer_dict: dict) -> Callable:
            def func(self, question, scenario=None):
                return answer_dict.get(question.question_name, None)

            return func

        agent_list = AgentList()

        for observation in self.get_observations():  # iterate through the observations
            traits = {}
            for trait_name in question_keys_as_traits:
                if trait_name not in observation:
                    failures[trait_name] = f"Question name {trait_name} not found."
                    continue
                else:
                    traits[trait_name] = observation[trait_name]

            agent = Agent(traits=traits)
            f = construct_answer_dict_function(observation.copy())
            agent.add_direct_question_answering_method(f)
            agent_list.append(agent)

        if self.sample_size is not None and len(agent_list) >= self.sample_size:
            return random.sample(agent_list, self.sample_size), failures
        else:
            return agent_list, failures

    @classmethod
    def from_url(cls, url: str):
        """Create a SurveyBuilder from a URL."""
        import tempfile
        import requests

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
            "Accept": "text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/csv;q=0.9,application/excel;q=0.8",
        }

        with tempfile.NamedTemporaryFile(delete=False, mode="wb") as localfile:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                localfile.write(response.content)
                localfile_path = localfile.name
            else:
                raise Exception(
                    f"Failed to fetch the file from {url}, status code: {response.status_code}"
                )

        print("Data saved to", localfile_path)
        return cls(localfile_path)

    def create_results(self):
        return self.survey.by(self.agents).run()

    @abstractmethod
    def get_responses(self) -> Dict:
        """Returns all of the raw responses, as a dataframe"""
        pass

    @abstractmethod
    def get_question_name_to_text(self) -> Dict[str, str]:
        pass

    @abstractmethod
    def get_question_name_to_answer_book(self) -> Dict[str, Dict[str, str]]:
        pass

    @classmethod
    def example(cls):
        class SurveyBuilderExample(SurveyBuilder):
            @staticmethod
            def get_dataframe(datafile_name):
                import pandas as pd

                return pd.DataFrame(
                    {"Q1": ["1", "4"], "Q2": ["2", "5"], "Q3": ["3", "6"]}
                )

            def get_responses(self) -> Dict:
                df = self.get_dataframe(self.datafile_name)
                df.fillna("", inplace=True)
                df = df.astype(str)
                data_dict = df.to_dict(orient="list")
                return {k.lower(): v for k, v in data_dict.items()}

            def get_question_name_to_text(self) -> Dict:
                d = {}
                df = self.get_dataframe(self.datafile_name)
                for col in df.columns:
                    if col in self.replacement_finder:
                        d[col] = self.replacement_finder[col]
                    else:
                        d[col] = col

                return d

            def get_question_name_to_answer_book(self):
                d = self.get_question_name_to_text()
                return {k: {} for k, v in d.items()}

        import tempfile

        named_temp_file = tempfile.NamedTemporaryFile(delete=False)
        named_temp_file.write(b"Q1,Q2,Q3\n1,2,3\n4,5,6\n")

        return SurveyBuilderExample(named_temp_file.name)

    def save(self, filename: str):
        if self.survey is None:
            import warnings

            warnings.warn("The survey has not been created yet.")
        else:
            full_filename = filename + "_survey.json.gz"
            print("Saving survey to", full_filename)
            self.survey.save(full_filename)

        if self.agents is None:
            import warnings

            warnings.warn("The agents have not been created yet.")
        else:
            full_filename = filename + "_agents.json.gz"
            print("Saving agents to", full_filename)
            self.agents.save(full_filename)

        if self.results is None:
            import warnings

            warnings.warn("The results have not been created yet.")
        else:
            full_filename = filename + "_results.json.gz"
            print("Saving results to", full_filename)
            self.results.save(full_filename)


if __name__ == "__main__":
    # q = RawResponseColumn(question_name="Sample question")
    import doctest

    doctest.testmod()
