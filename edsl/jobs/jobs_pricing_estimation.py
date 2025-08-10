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
from ..coop.utils import CostConverter
from ..caching import CacheEntry
from ..dataset import Dataset
from ..language_models.price_manager import PriceRetriever

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
        user_prompt_chars = len(str(self.user_prompt)) * self.get_piping_multiplier(
            str(self.user_prompt)
        )
        system_prompt_chars = len(str(self.system_prompt)) * self.get_piping_multiplier(
            str(self.system_prompt)
        )
        # Convert into tokens (1 token approx. equals 4 characters)
        input_tokens = (user_prompt_chars + system_prompt_chars) // self.CHARS_PER_TOKEN
        output_tokens = math.ceil(self.OUTPUT_TOKENS_PER_INPUT_TOKEN * input_tokens)

        relevant_prices = self.price_retriever.get_price(
            self.inference_service, self.model
        )

        input_price_per_million_tokens = (
            self.price_retriever.get_price_per_million_tokens(relevant_prices, "input")
        )
        output_price_per_million_tokens = (
            self.price_retriever.get_price_per_million_tokens(relevant_prices, "output")
        )

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
        import time

        start = time.time()
        interviews = jobs.interviews()
        print(f"Creating interviews took {time.time() - start:.2f} seconds")
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
        """Process a single invigilator with detailed timing."""
        import time

        # Get prompts (potentially expensive due to template rendering)
        prompts_start = time.time()
        prompts = invigilator.get_prompts()
        user_prompt = prompts["user_prompt"]
        system_prompt = prompts["system_prompt"]
        prompts_time = time.time() - prompts_start

        # Lookup indices (should be fast)
        lookup_start = time.time()
        agent_index = self._agent_lookup[invigilator.agent]
        scenario_index = self._scenario_lookup[invigilator.scenario]
        model = invigilator.model.model
        question_name = invigilator.question.question_name
        lookup_time = time.time() - lookup_start

        # Calculate prompt cost (involves API call or lookup)
        cost_start = time.time()
        prompt_cost = self.estimate_prompt_cost(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            price_lookup=self.price_lookup,
            inference_service=invigilator.model._inference_service_,
            model=model,
        )
        cost = prompt_cost["cost_usd"]
        cost_time = time.time() - cost_start

        # Generate cache keys for each iteration
        cache_start = time.time()
        file_hash_time = time.time()
        files_list = prompts.get("files_list", None)
        if files_list:
            files_hash = "+".join([str(hash(file)) for file in files_list])
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
        cache_time = time.time() - cache_start

        # Create result dictionary
        dict_start = time.time()
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
        dict_time = time.time() - dict_start

        # Log if any component is slow
        total_time = prompts_time + lookup_time + cost_time + cache_time + dict_time
        if total_time > 0.005:  # Log if > 5ms
            print(
                f"    _process_one_invigilator timing: "
                f"prompts={prompts_time:.6f}s, lookup={lookup_time:.6f}s, "
                f"cost={cost_time:.6f}s, cache={cache_time:.6f}s, "
                f"dict={dict_time:.6f}s, total={total_time:.6f}s"
            )

        return d

    def prompts(self, iterations=1) -> "Dataset":
        """Return a Dataset of prompts that will be used with detailed timing.

        >>> from edsl.jobs import Jobs
        >>> Jobs.example().prompts()
        Dataset(...)
        """
        import time

        method_start = time.time()

        # Initialize data structure
        init_start = time.time()
        dataset_of_prompts = {k: [] for k in self.relevant_keys}
        init_time = time.time() - init_start

        # Get interviews (this may trigger interview creation)
        interviews_start = time.time()
        interviews = self.interviews
        interviews_time = time.time() - interviews_start
        num_interviews = len(interviews)

        print(f"\n{'='*60}")
        print(f"PROMPTS METHOD TIMING ANALYSIS")
        print(f"{'='*60}")
        print(f"Initialization: {init_time:.6f}s")
        print(f"Getting {num_interviews} interviews: {interviews_time:.6f}s")

        # Timing accumulators
        total_fetch_invigilator_time = 0.0
        total_process_invigilator_time = 0.0
        total_data_append_time = 0.0
        invigilator_count = 0

        # Process each interview and invigilator
        for interview_index, interview in enumerate(interviews):
            interview_start = time.time()

            # Create FetchInvigilator instances for all questions
            fetch_start = time.time()
            invigilators = [
                FetchInvigilator(interview)(question)
                for question in interview.survey.questions
            ]
            fetch_time = time.time() - fetch_start
            total_fetch_invigilator_time += fetch_time

            # Process each invigilator
            for invigilator in invigilators:
                invigilator_start = time.time()

                # Process the invigilator and get all data as a dictionary
                process_start = time.time()
                data = self._process_one_invigilator(
                    invigilator, interview_index, iterations
                )
                process_time = time.time() - process_start
                total_process_invigilator_time += process_time

                # Append data to dataset
                append_start = time.time()
                for k in self.relevant_keys:
                    dataset_of_prompts[k].append(data[k])
                append_time = time.time() - append_start
                total_data_append_time += append_time

                invigilator_count += 1

                # Log slow invigilator processing
                total_invig_time = time.time() - invigilator_start
                if total_invig_time > 0.01:  # Log if > 10ms
                    print(
                        f"  SLOW invigilator {invigilator_count}: "
                        f"process={process_time:.6f}s, append={append_time:.6f}s, "
                        f"total={total_invig_time:.6f}s"
                    )

            interview_time = time.time() - interview_start
            if interview_index % 10 == 0 or interview_time > 0.1:
                print(
                    f"Interview {interview_index+1}/{num_interviews}: "
                    f"fetch_invig={fetch_time:.6f}s, "
                    f"process_all={interview_time-fetch_time:.6f}s, "
                    f"total={interview_time:.6f}s"
                )

        # Create final Dataset
        dataset_start = time.time()
        result = Dataset([{k: dataset_of_prompts[k]} for k in self.relevant_keys])
        dataset_time = time.time() - dataset_start

        total_time = time.time() - method_start

        # Print summary
        print(f"\n{'='*60}")
        print(f"PROMPTS METHOD SUMMARY")
        print(f"{'='*60}")
        print(f"Total interviews processed: {num_interviews}")
        print(f"Total invigilators processed: {invigilator_count}")
        print(
            f"Average invigilators per interview: {invigilator_count/max(num_interviews,1):.1f}"
        )
        print(f"\nTiming Breakdown:")
        print(
            f"  Getting interviews: {interviews_time:.6f}s ({interviews_time/total_time*100:.1f}%)"
        )
        print(
            f"  Creating FetchInvigilators: {total_fetch_invigilator_time:.6f}s ({total_fetch_invigilator_time/total_time*100:.1f}%)"
        )
        print(
            f"  Processing invigilators: {total_process_invigilator_time:.6f}s ({total_process_invigilator_time/total_time*100:.1f}%)"
        )
        print(
            f"  Appending data: {total_data_append_time:.6f}s ({total_data_append_time/total_time*100:.1f}%)"
        )
        print(
            f"  Creating Dataset: {dataset_time:.6f}s ({dataset_time/total_time*100:.1f}%)"
        )
        print(f"\nAverages per invigilator:")
        print(f"  Fetch: {total_fetch_invigilator_time/max(invigilator_count,1):.6f}s")
        print(
            f"  Process: {total_process_invigilator_time/max(invigilator_count,1):.6f}s"
        )
        print(f"  Append: {total_data_append_time/max(invigilator_count,1):.6f}s")
        print(f"\nTotal time: {total_time:.6f}s")
        print(f"{'='*60}")

        return result

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
            model=model,
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
        for interview in self.interviews:
            invigilators = [
                FetchInvigilator(interview)(question)
                for question in self.survey.questions
            ]
            for invigilator in invigilators:
                prompt_details = self._extract_prompt_details(invigilator)
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
