import random
from typing import List, Optional, Callable

from edsl.conjure.RawResponses import RawResponses
from edsl.agents import Agent, AgentList

class CreateAgents:
        
    def __init__(self, data: RawResponses, sample_size: Optional[int] = None):
        self.data = data
        self.sample_size = sample_size

    def __call__(self, question_keys_as_traits: List[str] = None):
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

        failures = {}

        def construct_answer_dict_function(answer_dict: dict) -> Callable:
            def func(self, question, scenario=None):
                return answer_dict.get(question.question_name, None)

            return func

        agent_list = AgentList()

        for observation in self.data.get_observations():  # iterate through the observations
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
