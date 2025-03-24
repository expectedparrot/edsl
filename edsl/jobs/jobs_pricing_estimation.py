import logging
import math

from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .jobs import Jobs
    from ..agents import AgentList
    from ..scenarios import ScenarioList
    from ..surveys import Survey
    from ..interviews import Interview
    from ..invigilators.invigilator_base import Invigilator

from .fetch_invigilator import FetchInvigilator
from ..caching import CacheEntry
from ..dataset import Dataset

logger = logging.getLogger(__name__)


class PromptCostEstimator:

    DEFAULT_INPUT_PRICE_PER_TOKEN = 0.000001
    DEFAULT_OUTPUT_PRICE_PER_TOKEN = 0.000001
    CHARS_PER_TOKEN = 4
    OUTPUT_TOKENS_PER_INPUT_TOKEN = 0.75
    PIPING_MULTIPLIER = 2

    def __init__(self,      
        system_prompt: str,
        user_prompt: str,
        price_lookup: dict,
        inference_service: str,
        model: str):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.price_lookup = price_lookup
        self.inference_service = inference_service
        self.model = model

    @staticmethod    
    def get_piping_multiplier(prompt: str):
        """Returns 2 if a prompt includes Jinja braces, and 1 otherwise."""

        if "{{" in prompt and "}}" in prompt:
            return PromptCostEstimator.PIPING_MULTIPLIER
        return 1
    
    @property
    def key(self):
        return (self.inference_service, self.model)
    
    @property
    def relevant_prices(self):
        try:
            return self.price_lookup[self.key]
        except KeyError:
            return {}
    
    def input_price_per_token(self):
        try:
            return self.relevant_prices["input"]["service_stated_token_price"] / self.relevant_prices["input"]["service_stated_token_qty"]
        except KeyError:
            import warnings
            warnings.warn(
                "Price data could not be retrieved. Using default estimates for input and output token prices. Input: $1.00 / 1M tokens; Output: $1.00 / 1M tokens"
            )
            return self.DEFAULT_INPUT_PRICE_PER_TOKEN

    def output_price_per_token(self):
        try:
            return self.relevant_prices["output"]["service_stated_token_price"] / self.relevant_prices["output"]["service_stated_token_qty"]
        except KeyError:
            return self.DEFAULT_OUTPUT_PRICE_PER_TOKEN
        
    def __call__(self):
        user_prompt_chars = len(str(self.user_prompt)) * self.get_piping_multiplier(
            str(self.user_prompt)
        )
        system_prompt_chars = len(str(self.system_prompt)) * self.get_piping_multiplier(
            str(self.system_prompt)
        )
        # Convert into tokens (1 token approx. equals 4 characters)
        input_tokens = (user_prompt_chars + system_prompt_chars) // self.CHARS_PER_TOKEN
        output_tokens = math.ceil(self.OUTPUT_TOKENS_PER_INPUT_TOKEN * input_tokens)

        cost = (
            input_tokens * self.input_price_per_token()
            + output_tokens * self.output_price_per_token()
        )
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
        }


class JobsPrompts:

    relevant_keys = ["user_prompt", "system_prompt", "interview_index", "question_name", "scenario_index", "agent_index", "model", "estimated_cost", "cache_keys"]

    """This generates the prompts for a job for price estimation purposes. 
    
    It does *not* do the full job execution---that requires an LLM. 
    So assumptions are made about expansion of Jinja braces, etc.
    """


    @classmethod
    def from_jobs(cls, jobs: "Jobs"):
        """Construct a JobsPrompts object from a Jobs object."""
        interviews = jobs.interviews()
        agents = jobs.agents
        scenarios = jobs.scenarios
        survey = jobs.survey
        return cls(
            interviews=interviews,
            agents=agents,
            scenarios=scenarios,
            survey=survey
        )
    
    def __init__(self, interviews: List['Interview'], agents:'AgentList', scenarios: 'ScenarioList', survey: 'Survey'):
        """Initialize with extracted components rather than a Jobs object."""
        self.interviews = interviews
        self.agents = agents
        self.scenarios = scenarios
        self.survey = survey
        self._price_lookup = None

        self._agent_lookup = {agent: idx for idx, agent in enumerate(self.agents)}
        self._scenario_lookup = {
            scenario: idx for idx, scenario in enumerate(self.scenarios)
        }

    @property
    def price_lookup(self) -> dict:
        """Fetches the price lookup from Coop if it is not already cached."""
        if self._price_lookup is None:
            from ..coop.coop import Coop

            c = Coop()
            self._price_lookup = c.fetch_prices()
        return self._price_lookup

    def _process_one_invigilator(self, invigilator: 'Invigilator', interview_index: int, iterations: int = 1) -> dict:
        """Process a single invigilator and return a dictionary with all needed data fields."""
        prompts = invigilator.get_prompts()
        user_prompt = prompts["user_prompt"]
        system_prompt = prompts["system_prompt"]
        
        agent_index = self._agent_lookup[invigilator.agent]
        scenario_index = self._scenario_lookup[invigilator.scenario]
        model = invigilator.model.model
        question_name = invigilator.question.question_name
        
        # Calculate prompt cost
        prompt_cost = self.estimate_prompt_cost(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            price_lookup=self.price_lookup,
            inference_service=invigilator.model._inference_service_,
            model=model,
        )
        cost = prompt_cost["cost_usd"]
        
        # Generate cache keys for each iteration
        cache_keys = []
        for iteration in range(iterations):
            cache_key = CacheEntry.gen_key(
                model=model,
                parameters=invigilator.model.parameters,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                iteration=iteration,
            )
            cache_keys.append(cache_key)
        
        d = {
            "user_prompt": user_prompt,
            "system_prompt": system_prompt,
            "interview_index": interview_index,
            "question_name": question_name,
            "scenario_index": scenario_index,
            "agent_index": agent_index,
            "model": model,
            "estimated_cost": cost,
            "cache_keys": cache_keys,
        }
        assert list(d.keys()) == self.relevant_keys
        return d

    def prompts(self, iterations=1) -> "Dataset":
        """Return a Dataset of prompts that will be used.

        >>> from edsl.jobs import Jobs
        >>> Jobs.example().prompts()
        Dataset(...)
        """
        dataset_of_prompts = {k: [] for k in self.relevant_keys}

        interviews = self.interviews
        
        # Process each interview and invigilator
        for interview_index, interview in enumerate(interviews):
            invigilators = [
                FetchInvigilator(interview)(question)
                for question in interview.survey.questions
            ]

            for invigilator in invigilators:
                # Process the invigilator and get all data as a dictionary
                data = self._process_one_invigilator(invigilator, interview_index, iterations)
                for k in self.relevant_keys:
                    dataset_of_prompts[k].append(data[k])
                
        return Dataset([{k:dataset_of_prompts[k]} for k in self.relevant_keys])

    @staticmethod
    def estimate_prompt_cost(
        system_prompt: str,
        user_prompt: str,
        price_lookup: dict,
        inference_service: str,
        model: str,
    ) -> dict:
        """Estimates the cost of a prompt, taking piping into account."""
        return PromptCostEstimator(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            price_lookup=price_lookup,
            inference_service=inference_service,
            model=model
        )()
    
    @staticmethod
    def _extract_prompt_details(invigilator: FetchInvigilator) -> dict:
        """Extracts the prompt details from the invigilator.
        
        >>> from edsl.invigilators import InvigilatorAI
        >>> invigilator = InvigilatorAI.example()
        >>> JobsPrompts._extract_prompt_details(invigilator)
        {'user_prompt': ...
        """
        prompts = invigilator.get_prompts()
        user_prompt = prompts["user_prompt"]
        system_prompt = prompts["system_prompt"]
        inference_service = invigilator.model._inference_service_
        model = invigilator.model.model
        return {
            "user_prompt": user_prompt,
            "system_prompt": system_prompt,
            "inference_service": inference_service,
            "model": model,
        }

    def estimate_job_cost_from_external_prices(
        self, price_lookup: dict, iterations: int = 1
    ) -> dict:
        """
        Estimates the cost of a job.

        :param price_lookup: An external pricing dictionary.
        :param iterations: The number of times to iterate over the job.

        Key assumptions:
        - 1 token = 4 characters.
        - For each prompt, output tokens = input tokens * 0.75, rounded up to the nearest integer.
        """
        interviews = self.interviews
        data = []
        for interview in interviews:
            invigilators = [
                FetchInvigilator(interview)(question)
                for question in self.survey.questions
            ]
            for invigilator in invigilators:
                prompt_details = self._extract_prompt_details(invigilator)
                prompt_cost = self.estimate_prompt_cost(**prompt_details, price_lookup=price_lookup)
                price_estimates = {
                    'estimated_input_tokens': prompt_cost['input_tokens'],
                    'estimated_output_tokens': prompt_cost['output_tokens'],
                    'estimated_cost_usd': prompt_cost['cost_usd']
                }
                data.append({**price_estimates, **prompt_details})

        model_groups = {}
        for item in data:
            key = (item["inference_service"], item["model"])
            if key not in model_groups:
                model_groups[key] = {
                    "inference_service": item["inference_service"],
                    "model": item["model"],
                    "estimated_cost_usd": 0,
                    "estimated_input_tokens": 0,
                    "estimated_output_tokens": 0
                }
            
            # Accumulate values
            model_groups[key]["estimated_cost_usd"] += item["estimated_cost_usd"]
            model_groups[key]["estimated_input_tokens"] += item["estimated_input_tokens"]
            model_groups[key]["estimated_output_tokens"] += item["estimated_output_tokens"]
        
        # Apply iterations and convert to list
        estimated_costs_by_model = []
        for group_data in model_groups.values():
            group_data["estimated_cost_usd"] *= iterations
            group_data["estimated_input_tokens"] *= iterations
            group_data["estimated_output_tokens"] *= iterations
            estimated_costs_by_model.append(group_data)

        # Calculate totals
        estimated_total_cost = sum(
            model["estimated_cost_usd"] for model in estimated_costs_by_model
        )
        estimated_total_input_tokens = sum(
            model["estimated_input_tokens"] for model in estimated_costs_by_model
        )
        estimated_total_output_tokens = sum(
            model["estimated_output_tokens"] for model in estimated_costs_by_model
        )

        output = {
            "estimated_total_cost_usd": estimated_total_cost,
            "estimated_total_input_tokens": estimated_total_input_tokens,
            "estimated_total_output_tokens": estimated_total_output_tokens,
            "model_costs": estimated_costs_by_model,
        }

        return output

    def estimate_job_cost(self, iterations: int = 1) -> dict:
        """
        Estimates the cost of a job according to the following assumptions:

        - 1 token = 4 characters.
        - For each prompt, output tokens = input tokens * 0.75, rounded up to the nearest integer.

        Fetches prices from Coop.
        """
        return self.estimate_job_cost_from_external_prices(
            price_lookup=self.price_lookup, iterations=iterations
        )


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
