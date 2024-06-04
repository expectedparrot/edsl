from abc import ABC, abstractmethod
import os
import random
from typing import Dict, Any, List, Callable, Optional
from collections import UserDict

from pydantic import ValidationError

from edsl.utilities.utilities import create_valid_var_name
from edsl.surveys.Survey import Survey
from edsl.conjure.RawResponseColumn import (
    RawResponseColumn,
    get_replacement_name,
    CustomDict,
)


class ValidFilename:
    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        return instance.__dict__.get(self.name, None)

    def __set__(self, instance, value):
        if not isinstance(value, str):
            raise ValueError(
                f"The filename must be a string, not {type(value).__name__}"
            )

        if not os.path.exists(value):
            raise ValueError(f"The file '{value}' does not exist.")

        instance.__dict__[self.name] = value


class SurveyBuilder(ABC, UserDict):
    """A ABC class to represent the process of building a survey and results from an external format"""

    datafile_name = ValidFilename()

    def lookup_dict(self):
        return get_replacement_name.lookup_dict

    def __init__(
        self,
        datafile_name: str,
        sample_size: Optional[int] = None,
        compute_results: bool = True,
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
        self.sample_size = sample_size
        self.responses = CustomDict(self.get_responses())

        self.question_name_to_text = CustomDict(self.get_question_name_to_text())

        self.question_name_to_answer_book = CustomDict(
            self.get_question_name_to_answer_book()
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

    def get_observations(self) -> List[Dict[str, Any]]:
        """Returns a list of dictionaries, where each dictionary is an observation.

        >>> sb = SurveyBuilder.example()
        >>> sb.get_observations()
        [{'q1': '1', 'q2': '2', 'q3': '3'}, {'q1': '4', 'q2': '5', 'q3': '6'}]

        """
        observations = []
        for question_name, question_responses in self.items():
            for index, response in enumerate(question_responses.responses):
                if len(observations) <= index:
                    observations.append({question_name: response})
                else:
                    observations[index][question_name] = response
        return observations

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

    def create_survey(self):
        "Iterates through the question keys and creates a survey."
        questions = []
        failures = {}
        for question_responses in self.values():
            try:
                proposed_question = question_responses.to_question()
            except Exception as e:
                print(f"Could not convert to question: {question_responses}: {e}")
                failures[question_responses.question_name] = e
                continue
            else:
                questions.append(proposed_question)
        if len(failures) > 0:
            print(
                f"Attempted {len(self.keys())} questions; there were {len(failures)} failures."
            )
        return Survey(questions), failures

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
                    if col in self.lookup_dict():
                        d[col] = self.lookup_dict()[col]
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

    def to_dict(self):
        return {
            "datafile_name": self.datafile_name,
            "survey": self.survey.to_dict(),
            "agents": None if self.agents is None else self.agents.to_dict(),
            "results": None if self.results is None else self.results.to_dict(),
            "sample_size": self.sample_size,
            "num_survey_failures": len(self.survey_failures),
        }

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
