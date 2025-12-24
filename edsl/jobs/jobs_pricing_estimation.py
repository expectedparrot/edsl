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
    from ..dataset import Dataset

from .fetch_invigilator import FetchInvigilator

logger = logging.getLogger(__name__)


class PromptCostEstimator:
    CHARS_PER_TOKEN = 4
    OUTPUT_TOKENS_PER_INPUT_TOKEN = 0.75
    PIPING_MULTIPLIER = 2

    def __init__(
        self,
        system_prompt: str,
        user_prompt: str,
        price_lookup: dict,
        inference_service: str,
        model: str,
    ):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        from ..language_models.price_manager import PriceRetriever

        self.price_retriever = PriceRetriever(price_lookup)
        self.inference_service = inference_service
        self.model = model

    @staticmethod
    def get_piping_multiplier(prompt: str):
        """Returns 2 if a prompt includes Jinja braces, and 1 otherwise."""

        if "{{" in prompt and "}}" in prompt:
            return PromptCostEstimator.PIPING_MULTIPLIER
        return 1

    def __call__(self):
        # Calculate character counts and piping multipliers
        user_prompt_chars = len(str(self.user_prompt)) * self.get_piping_multiplier(
            str(self.user_prompt)
        )
        system_prompt_chars = len(str(self.system_prompt)) * self.get_piping_multiplier(
            str(self.system_prompt)
        )
        # Convert into tokens (1 token approx. equals 4 characters)
        input_tokens = (user_prompt_chars + system_prompt_chars) // self.CHARS_PER_TOKEN
        output_tokens = math.ceil(self.OUTPUT_TOKENS_PER_INPUT_TOKEN * input_tokens)

        # Get pricing information
        relevant_prices = self.price_retriever.get_price(
            self.inference_service, self.model
        )

        input_price_per_million_tokens = (
            self.price_retriever.get_price_per_million_tokens(relevant_prices, "input")
        )
        output_price_per_million_tokens = (
            self.price_retriever.get_price_per_million_tokens(relevant_prices, "output")
        )

        # Calculate final costs
        input_price_per_token = input_price_per_million_tokens / 1_000_000
        output_price_per_token = output_price_per_million_tokens / 1_000_000

        input_cost = input_tokens * input_price_per_token
        output_cost = output_tokens * output_price_per_token
        cost = input_cost + output_cost

        return {
            "input_price_per_million_tokens": input_price_per_million_tokens,
            "output_price_per_million_tokens": output_price_per_million_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_cost_usd": input_cost,
            "output_cost_usd": output_cost,
            "cost_usd": cost,
        }


class JobsPrompts:
    relevant_keys = [
        "user_prompt",
        "system_prompt",
        "interview_index",
        "question_name",
        "scenario_index",
        "agent_index",
        "model",
        "estimated_cost",
        "cache_keys",
    ]

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
            interviews=interviews, agents=agents, scenarios=scenarios, survey=survey
        )

    def __init__(
        self,
        interviews: List["Interview"],
        agents: "AgentList",
        scenarios: "ScenarioList",
        survey: "Survey",
    ):
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

    def _process_one_invigilator(
        self, invigilator: "Invigilator", interview_index: int, iterations: int = 1
    ) -> dict:
        """Process a single invigilator and return a dictionary with all needed data fields."""
        from ..caching import CacheEntry

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
        files_list = prompts.get("files_list", None)
        if files_list:
            # Sort hashes to ensure consistent cache keys regardless of file order
            files_hash = "+".join(sorted([str(hash(file)) for file in files_list]))
            user_prompt_with_hashes = user_prompt + f" {files_hash}"
        cache_keys = []

        # Calculate salt for cache keys
        from ..coop.coop import Coop
        import hashlib
        c = Coop()
        salt = hashlib.sha256(c.api_key.encode()).hexdigest() if c.api_key else None

        for iteration in range(iterations):
            cache_key = CacheEntry.gen_key(
                model=model,
                parameters=invigilator.model.parameters,
                system_prompt=system_prompt,
                user_prompt=user_prompt_with_hashes if files_list else user_prompt,
                iteration=iteration,
                salt=salt,
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
        from ..dataset import Dataset

        # Initialize dataset
        dataset_of_prompts = {k: [] for k in self.relevant_keys}

        # Process interviews
        for interview_index, interview in enumerate(self.interviews):
            # Create invigilators
            invigilators = [
                FetchInvigilator(interview)(question)
                for question in interview.survey.questions
            ]

            # Process invigilators
            for invigilator in invigilators:
                # Process the invigilator and get all data as a dictionary
                data = self._process_one_invigilator(
                    invigilator, interview_index, iterations
                )
                for k in self.relevant_keys:
                    dataset_of_prompts[k].append(data[k])

        # Create final dataset
        return Dataset([{k: dataset_of_prompts[k]} for k in self.relevant_keys])

    @staticmethod
    def estimate_prompt_cost(
        system_prompt: str,
        user_prompt: str,
        price_lookup: dict,
        inference_service: str,
        model: str,
    ) -> dict:
        """Estimates the cost of a prompt, taking piping into account."""
        estimator = PromptCostEstimator(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            price_lookup=price_lookup,
            inference_service=inference_service,
            model=model,
        )
        return estimator()

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

    def process_token_type(self, item: dict, token_type: str) -> tuple:
        """
        Helper function to process a single token type (input or output) for price estimation.
        """
        price = item[f"estimated_{token_type}_price_per_million_tokens"]
        tokens = item[f"estimated_{token_type}_tokens"]
        cost = item[f"estimated_{token_type}_cost_usd"]

        return (
            (item["inference_service"], item["model"], token_type, price),
            {
                "inference_service": item["inference_service"],
                "model": item["model"],
                "token_type": token_type,
                "price_per_million_tokens": price,
                "tokens": tokens,
                "cost_usd": cost,
            },
        )

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
        # Collect all prompt data
        data = []

        for interview_idx, interview in enumerate(self.interviews):
            invigilators = [
                FetchInvigilator(interview)(question)
                for question in self.survey.questions
            ]

            for invig_idx, invigilator in enumerate(invigilators):
                # Extract prompt details
                prompt_details = self._extract_prompt_details(invigilator)

                # Calculate prompt cost
                prompt_cost = self.estimate_prompt_cost(
                    **prompt_details, price_lookup=price_lookup
                )

                price_estimates = {
                    "estimated_input_price_per_million_tokens": prompt_cost[
                        "input_price_per_million_tokens"
                    ],
                    "estimated_output_price_per_million_tokens": prompt_cost[
                        "output_price_per_million_tokens"
                    ],
                    "estimated_input_tokens": prompt_cost["input_tokens"],
                    "estimated_output_tokens": prompt_cost["output_tokens"],
                    "estimated_input_cost_usd": prompt_cost["input_cost_usd"],
                    "estimated_output_cost_usd": prompt_cost["output_cost_usd"],
                    "estimated_cost_usd": prompt_cost["cost_usd"],
                }
                data.append(
                    {
                        **prompt_details,
                        **price_estimates,
                    }
                )

        # Group by service, model, token type, and price
        detailed_groups = {}
        for item in data:
            for token_type in ["input", "output"]:
                key, group_data = self.process_token_type(item, token_type)
                if key not in detailed_groups:
                    detailed_groups[key] = group_data
                else:
                    detailed_groups[key]["tokens"] += group_data["tokens"]
                    detailed_groups[key]["cost_usd"] += group_data["cost_usd"]

        # Apply iterations and prepare final output
        detailed_costs = []
        for group in detailed_groups.values():
            group["tokens"] *= iterations
            group["cost_usd"] *= iterations
            detailed_costs.append(group)

        # Convert to credits
        from ..coop.utils import CostConverter

        converter = CostConverter()
        for group in detailed_costs:
            group["credits_hold"] = converter.usd_to_credits(group["cost_usd"])

        # Calculate totals
        estimated_total_cost_usd = sum(group["cost_usd"] for group in detailed_costs)
        total_credits_hold = sum(group["credits_hold"] for group in detailed_costs)
        estimated_total_input_tokens = sum(
            group["tokens"]
            for group in detailed_costs
            if group["token_type"] == "input"
        )
        estimated_total_output_tokens = sum(
            group["tokens"]
            for group in detailed_costs
            if group["token_type"] == "output"
        )

        output = {
            "estimated_total_cost_usd": estimated_total_cost_usd,
            "total_credits_hold": total_credits_hold,
            "estimated_total_input_tokens": estimated_total_input_tokens,
            "estimated_total_output_tokens": estimated_total_output_tokens,
            "detailed_costs": detailed_costs,
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
