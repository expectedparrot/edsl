import logging
import math
import time

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
        start_time = time.time()

        # Calculate character counts and piping multipliers
        char_calc_start = time.time()
        user_prompt_chars = len(str(self.user_prompt)) * self.get_piping_multiplier(
            str(self.user_prompt)
        )
        system_prompt_chars = len(str(self.system_prompt)) * self.get_piping_multiplier(
            str(self.system_prompt)
        )
        # Convert into tokens (1 token approx. equals 4 characters)
        input_tokens = (user_prompt_chars + system_prompt_chars) // self.CHARS_PER_TOKEN
        output_tokens = math.ceil(self.OUTPUT_TOKENS_PER_INPUT_TOKEN * input_tokens)
        char_calc_time = time.time() - char_calc_start

        # Get pricing information
        price_lookup_start = time.time()
        relevant_prices = self.price_retriever.get_price(
            self.inference_service, self.model
        )

        input_price_per_million_tokens = (
            self.price_retriever.get_price_per_million_tokens(relevant_prices, "input")
        )
        output_price_per_million_tokens = (
            self.price_retriever.get_price_per_million_tokens(relevant_prices, "output")
        )
        price_lookup_time = time.time() - price_lookup_start

        # Calculate final costs
        cost_calc_start = time.time()
        input_price_per_token = input_price_per_million_tokens / 1_000_000
        output_price_per_token = output_price_per_million_tokens / 1_000_000

        input_cost = input_tokens * input_price_per_token
        output_cost = output_tokens * output_price_per_token
        cost = input_cost + output_cost
        cost_calc_time = time.time() - cost_calc_start

        total_time = time.time() - start_time
        print(
            f"DEBUG - PromptCostEstimator.__call__: char_calc={char_calc_time:.4f}s, "
            f"price_lookup={price_lookup_time:.4f}s, cost_calc={cost_calc_time:.4f}s, "
            f"total={total_time:.4f}s (tokens: input={input_tokens}, output={output_tokens})"
        )

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
        start_time = time.time()
        print(f"DEBUG - JobsPrompts.from_jobs called")

        interviews_start = time.time()
        interviews = jobs.interviews()
        interviews_time = time.time() - interviews_start

        attrs_start = time.time()
        agents = jobs.agents
        scenarios = jobs.scenarios
        survey = jobs.survey
        attrs_time = time.time() - attrs_start

        create_start = time.time()
        instance = cls(
            interviews=interviews, agents=agents, scenarios=scenarios, survey=survey
        )
        create_time = time.time() - create_start

        total_time = time.time() - start_time
        print(
            f"DEBUG - JobsPrompts.from_jobs: interviews={interviews_time:.4f}s, "
            f"attrs={attrs_time:.4f}s, create={create_time:.4f}s, total={total_time:.4f}s"
        )

        return instance

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
        print(prompts)
        print("DEBUG ########", len(files_list))
        if files_list:
            # Sort hashes to ensure consistent cache keys regardless of file order
            files_hash = "+".join(sorted([str(hash(file)) for file in files_list]))
            user_prompt_with_hashes = user_prompt + f" {files_hash}"
        cache_keys = []

        for iteration in range(iterations):
            cache_key = CacheEntry.gen_key(
                model=model,
                parameters=invigilator.model.parameters,
                system_prompt=system_prompt,
                user_prompt=user_prompt_with_hashes if files_list else user_prompt,
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
        from ..dataset import Dataset

        print("CALLING prompts")
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
                data = self._process_one_invigilator(
                    invigilator, interview_index, iterations
                )
                for k in self.relevant_keys:
                    dataset_of_prompts[k].append(data[k])

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
        start_time = time.time()

        estimator_creation_start = time.time()
        estimator = PromptCostEstimator(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            price_lookup=price_lookup,
            inference_service=inference_service,
            model=model,
        )
        estimator_creation_time = time.time() - estimator_creation_start

        estimation_start = time.time()
        result = estimator()
        estimation_time = time.time() - estimation_start

        total_time = time.time() - start_time
        print(
            f"DEBUG - estimate_prompt_cost: creation={estimator_creation_time:.4f}s, "
            f"calculation={estimation_time:.4f}s, total={total_time:.4f}s"
        )

        return result

    @staticmethod
    def _extract_prompt_details(invigilator: FetchInvigilator) -> dict:
        """Extracts the prompt details from the invigilator.

        >>> from edsl.invigilators import InvigilatorAI
        >>> invigilator = InvigilatorAI.example()
        >>> JobsPrompts._extract_prompt_details(invigilator)
        {'user_prompt': ...
        """
        start_time = time.time()

        prompts_start = time.time()
        prompts = invigilator.get_prompts()
        prompts_time = time.time() - prompts_start

        user_prompt = prompts["user_prompt"]
        system_prompt = prompts["system_prompt"]
        inference_service = invigilator.model._inference_service_
        model = invigilator.model.model

        total_time = time.time() - start_time
        print(
            f"DEBUG - _extract_prompt_details: get_prompts={prompts_time:.4f}s, total={total_time:.4f}s"
        )

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
        total_start_time = time.time()
        print(
            f"DEBUG - Starting estimate_job_cost_from_external_prices with {len(self.interviews)} interviews, {iterations} iterations"
        )

        # Collect all prompt data
        data_collection_start = time.time()
        data = []

        for interview_idx, interview in enumerate(self.interviews):
            interview_start_time = time.time()

            invigilators_creation_start = time.time()
            invigilators = [
                FetchInvigilator(interview)(question)
                for question in self.survey.questions
            ]
            invigilators_creation_time = time.time() - invigilators_creation_start
            print(
                f"DEBUG - Interview {interview_idx}: Created {len(invigilators)} invigilators in {invigilators_creation_time:.4f}s"
            )

            for invig_idx, invigilator in enumerate(invigilators):
                invigilator_start_time = time.time()

                # Extract prompt details
                prompt_extract_start = time.time()
                prompt_details = self._extract_prompt_details(invigilator)
                prompt_extract_time = time.time() - prompt_extract_start

                # Calculate prompt cost
                prompt_cost_start = time.time()
                prompt_cost = self.estimate_prompt_cost(
                    **prompt_details, price_lookup=price_lookup
                )
                prompt_cost_time = time.time() - prompt_cost_start

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

                invigilator_total_time = time.time() - invigilator_start_time
                print(
                    f"DEBUG - Interview {interview_idx}, Invigilator {invig_idx}: "
                    f"extract={prompt_extract_time:.4f}s, cost_calc={prompt_cost_time:.4f}s, "
                    f"total={invigilator_total_time:.4f}s"
                )

            interview_total_time = time.time() - interview_start_time
            print(
                f"DEBUG - Interview {interview_idx}: Completed in {interview_total_time:.4f}s"
            )

        data_collection_time = time.time() - data_collection_start
        print(
            f"DEBUG - Data collection phase completed in {data_collection_time:.4f}s. Collected {len(data)} items"
        )

        # Group by service, model, token type, and price
        grouping_start_time = time.time()
        detailed_groups = {}
        for item in data:
            for token_type in ["input", "output"]:
                key, group_data = self.process_token_type(item, token_type)
                if key not in detailed_groups:
                    detailed_groups[key] = group_data
                else:
                    detailed_groups[key]["tokens"] += group_data["tokens"]
                    detailed_groups[key]["cost_usd"] += group_data["cost_usd"]
        grouping_time = time.time() - grouping_start_time
        print(
            f"DEBUG - Grouping phase completed in {grouping_time:.4f}s. Created {len(detailed_groups)} groups"
        )

        # Apply iterations and prepare final output
        iterations_start_time = time.time()
        detailed_costs = []
        for group in detailed_groups.values():
            group["tokens"] *= iterations
            group["cost_usd"] *= iterations
            detailed_costs.append(group)
        iterations_time = time.time() - iterations_start_time
        print(f"DEBUG - Iterations application completed in {iterations_time:.4f}s")

        # Convert to credits
        credits_start_time = time.time()
        from ..coop.utils import CostConverter

        converter = CostConverter()
        for group in detailed_costs:
            group["credits_hold"] = converter.usd_to_credits(group["cost_usd"])
        credits_time = time.time() - credits_start_time
        print(f"DEBUG - Credits conversion completed in {credits_time:.4f}s")

        # Calculate totals
        totals_start_time = time.time()
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
        totals_time = time.time() - totals_start_time
        print(f"DEBUG - Totals calculation completed in {totals_time:.4f}s")

        output = {
            "estimated_total_cost_usd": estimated_total_cost_usd,
            "total_credits_hold": total_credits_hold,
            "estimated_total_input_tokens": estimated_total_input_tokens,
            "estimated_total_output_tokens": estimated_total_output_tokens,
            "detailed_costs": detailed_costs,
        }

        total_time = time.time() - total_start_time
        print(
            f"DEBUG - estimate_job_cost_from_external_prices completed in {total_time:.4f}s"
        )
        print(
            f"DEBUG - Timing breakdown: data_collection={data_collection_time:.4f}s ({data_collection_time/total_time*100:.1f}%), "
            f"grouping={grouping_time:.4f}s ({grouping_time/total_time*100:.1f}%), "
            f"iterations={iterations_time:.4f}s ({iterations_time/total_time*100:.1f}%), "
            f"credits={credits_time:.4f}s ({credits_time/total_time*100:.1f}%), "
            f"totals={totals_time:.4f}s ({totals_time/total_time*100:.1f}%)"
        )

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
