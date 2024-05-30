from abc import ABC, abstractmethod
import os
import random

from typing import Dict, Any, List, Callable, Optional
from collections import UserDict

from pydantic import ValidationError

from edsl.utilities.utilities import create_valid_var_name
from edsl.surveys.Survey import Survey

from edsl.conjure.RawResponseColumn import RawResponseColumn, get_replacement_name, CustomDict


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
    """A ABC class to represent the process of building a survey from an external format"""

    datafile_name = ValidFilename()

    def lookup_dict(self):
        return get_replacement_name.lookup_dict

    def __init__(
        self, datafile_name: str, 
        sample_size: Optional[int] = None, 
        compute_results=True
    ):
        """Initialize the SurveyBuilder with the given datafile_name.
        
        :param datafile_name: The name of the datafile to be used.
        :param sample_size: The number of observations to sample from the dataset.
        
        """
        self.datafile_name = datafile_name

        self.responses = CustomDict(self.get_responses())
        self.question_name_to_text = CustomDict(self.get_question_name_to_text())
        self.question_name_to_answer_book = CustomDict(
            self.get_question_name_to_answer_book()
        )

        self.data = {}
        for question_name, raw_responses in self.responses.items():
            raw_question_response = RawResponseColumn(
                question_name=question_name,
                raw_responses=raw_responses,
                answer_codebook=self.question_name_to_answer_book[question_name],
                question_text=self.question_name_to_text[question_name],
            )
            self.data[question_name] = raw_question_response

        self.survey, self.survey_failures = self.create_survey()

        if compute_results:
            self.agents, self.agent_failures = self.create_agents(sample_size)
            self.results = self.create_results()

    @property
    def list_of_dicts(self):
        observations = []
        for question_name, question_responses in self.items():
            for index, response in enumerate(question_responses.responses):
                if len(observations) <= index:
                    observations.append({question_name: response})
                else:
                    observations[index][question_name] = response
        return observations

    def create_agents(
        self, sample_size=None, question_keys_as_traits: List[str] = None
    ):
        """Returns a list of agents, and a dictionary of failures.

        These agents are special in that they have an 'answer_question_directly'
        method that allows them to answer questions directly when presented with
        the question_name. This is useful because in self.Agents, these agents can
        bypass the LLM call.
        """
        if question_keys_as_traits is None:
            question_keys_as_traits = []

        from edsl.agents.Agent import Agent
        from edsl.agents.AgentList import AgentList

        failures = {}

        def construct_answer_dict_function(answer_dict) -> Callable:
            def func(question, scenario = None):
                return answer_dict.get(question.question_name, None)

            return func

        agent_list = AgentList()
        observations = self.list_of_dicts
        for observation in observations:
            traits = {}
            for trait_name in question_keys_as_traits:
                if trait_name not in observation:
                    failures[trait_name] = f"Question name {trait_name} not found."
                    continue
                else:
                    traits[trait_name] = observation[trait_name]

            agent = Agent(traits=traits)
            agent.answer_question_directly = construct_answer_dict_function(
                observation.copy()
            )
            agent_list.append(agent)

        if sample_size is not None and len(agent_list) >= sample_size:
            return random.sample(agent_list, sample_size), failures
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


if __name__ == "__main__":
    q = RawResponseColumn(question_name="Sample question")
