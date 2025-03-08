import logging
from typing import List, TYPE_CHECKING

from edsl.results.Dataset import Dataset

if TYPE_CHECKING:
    from .Jobs import Jobs

from .FetchInvigilator import FetchInvigilator
from edsl.data.CacheEntry import CacheEntry

logger = logging.getLogger(__name__)

class JobsPrompts:
    """This generates the prompts for a job for price estimation purposes. 
    
    It does *not* do the full job execution---that requires an LLM. 
    So assumptions are made about expansion of Jinja braces, etc.
    """
    def __init__(self, jobs: "Jobs"):
        self.interviews = jobs.interviews()
        self.agents = jobs.agents
        self.scenarios = jobs.scenarios
        self.survey = jobs.survey
        self._price_lookup = None
        self._agent_lookup = {agent: idx for idx, agent in enumerate(self.agents)}
        self._scenario_lookup = {
            scenario: idx for idx, scenario in enumerate(self.scenarios)
        }

    @property
    def price_lookup(self) -> dict:
        """Fetches the price lookup from Coop if it is not already cached."""
        if self._price_lookup is None:
            from edsl.coop.coop import Coop

            c = Coop()
            self._price_lookup = c.fetch_prices()
        return self._price_lookup

    def prompts(self, iterations=1) -> "Dataset":
        """Return a Dataset of prompts that will be used.

        >>> from edsl.jobs import Jobs
        >>> Jobs.example().prompts()
        Dataset(...)
        """
        interviews = self.interviews
        interview_indices = []
        question_names = []
        user_prompts = []
        system_prompts = []
        scenario_indices = []
        agent_indices = []
        models = []
        costs = []
        cache_keys = []

        for interview_index, interview in enumerate(interviews):
            invigilators = [
                FetchInvigilator(interview)(question)
                for question in interview.survey.questions
            ]

            for _, invigilator in enumerate(invigilators):
                prompts = invigilator.get_prompts()
                user_prompt = prompts["user_prompt"]
                system_prompt = prompts["system_prompt"]
                user_prompts.append(user_prompt)
                system_prompts.append(system_prompt)

                agent_index = self._agent_lookup[invigilator.agent]
                agent_indices.append(agent_index)
                interview_indices.append(interview_index)
                scenario_index = self._scenario_lookup[invigilator.scenario]
                scenario_indices.append(scenario_index)

                models.append(invigilator.model.model)
                question_names.append(invigilator.question.question_name)

                prompt_cost = self.estimate_prompt_cost(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    price_lookup=self.price_lookup,
                    inference_service=invigilator.model._inference_service_,
                    model=invigilator.model.model,
                )
                costs.append(prompt_cost["cost_usd"])

                for iteration in range(iterations):
                    cache_key = CacheEntry.gen_key(
                        model=invigilator.model.model,
                        parameters=invigilator.model.parameters,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        iteration=iteration,
                    )
                    cache_keys.append(cache_key)

        d = Dataset(
            [
                {"user_prompt": user_prompts},
                {"system_prompt": system_prompts},
                {"interview_index": interview_indices},
                {"question_name": question_names},
                {"scenario_index": scenario_indices},
                {"agent_index": agent_indices},
                {"model": models},
                {"estimated_cost": costs},
                {"cache_key": cache_keys},
            ]
        )
        return d

    @staticmethod
    def estimate_prompt_cost(
        system_prompt: str,
        user_prompt: str,
        price_lookup: dict,
        inference_service: str,
        model: str,
    ) -> dict:
        """Estimates the cost of a prompt, taking piping into account."""
        import math

        def get_piping_multiplier(prompt: str):
            """Returns 2 if a prompt includes Jinja braces, and 1 otherwise."""

            if "{{" in prompt and "}}" in prompt:
                return 2
            return 1

        # Look up prices per token
        key = (inference_service, model)

        try:
            relevant_prices = price_lookup[key]

            service_input_token_price = float(
                relevant_prices["input"]["service_stated_token_price"]
            )
            service_input_token_qty = float(
                relevant_prices["input"]["service_stated_token_qty"]
            )
            input_price_per_token = service_input_token_price / service_input_token_qty

            service_output_token_price = float(
                relevant_prices["output"]["service_stated_token_price"]
            )
            service_output_token_qty = float(
                relevant_prices["output"]["service_stated_token_qty"]
            )
            output_price_per_token = (
                service_output_token_price / service_output_token_qty
            )

        except KeyError:
            # A KeyError is likely to occur if we cannot retrieve prices (the price_lookup dict is empty)
            # Use a sensible default

            import warnings

            warnings.warn(
                "Price data could not be retrieved. Using default estimates for input and output token prices. Input: $1.00 / 1M tokens; Output: $1.00 / 1M tokens"
            )
            input_price_per_token = 0.000001  # $1.00 / 1M tokens
            output_price_per_token = 0.000001  # $1.00 / 1M tokens

        # Compute the number of characters (double if the question involves piping)
        user_prompt_chars = len(str(user_prompt)) * get_piping_multiplier(
            str(user_prompt)
        )
        system_prompt_chars = len(str(system_prompt)) * get_piping_multiplier(
            str(system_prompt)
        )

        # Convert into tokens (1 token approx. equals 4 characters)
        input_tokens = (user_prompt_chars + system_prompt_chars) // 4

        output_tokens = math.ceil(0.75 * input_tokens)

        cost = (
            input_tokens * input_price_per_token
            + output_tokens * output_price_per_token
        )

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
        }
    
    @staticmethod
    def _extract_prompt_details(invigilator: FetchInvigilator) -> dict:
        """Extracts the prompt details from the invigilator.
        
        >>> from edsl.agents.Invigilator import InvigilatorAI
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
