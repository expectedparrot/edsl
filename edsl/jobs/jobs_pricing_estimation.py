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
        import time

        start = time.time()
        print(f"[PROMPTS] Starting from_jobs()")

        interviews_start = time.time()
        interviews = jobs.interviews()
        print(
            f"[PROMPTS] Created {len(interviews)} interviews in {time.time() - interviews_start:.3f}s"
        )

        agents = jobs.agents
        scenarios = jobs.scenarios
        survey = jobs.survey

        print(f"[PROMPTS] from_jobs() completed in {time.time() - start:.3f}s")
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
    ):
        """Process a single invigilator and return a dictionary with all needed data fields and timings."""
        import time
        from ..caching import CacheEntry

        other_start = time.time()

        # Track time for getting prompts
        prompts_start = time.time()
        prompts = invigilator.get_prompts()
        prompts_time = time.time() - prompts_start
        if prompts_time > 0.1:  # Log if getting prompts takes more than 100ms
            print(
                f"[PROMPTS] WARNING: get_prompts() took {prompts_time:.3f}s for question {invigilator.question.question_name}"
            )

        # Extract detailed timing breakdown from prompt_constructor if available
        prompt_timing = {}
        if hasattr(invigilator, "prompt_constructor") and hasattr(
            invigilator.prompt_constructor, "_last_get_prompts_timing"
        ):
            prompt_timing = invigilator.prompt_constructor._last_get_prompts_timing

        user_prompt = prompts["user_prompt"]
        system_prompt = prompts["system_prompt"]

        agent_index = self._agent_lookup[invigilator.agent]
        scenario_index = self._scenario_lookup[invigilator.scenario]
        model = invigilator.model.model
        question_name = invigilator.question.question_name

        # Calculate prompt cost
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
        if cost_time > 0.05:  # Log if cost estimation takes more than 50ms
            print(f"[PROMPTS] WARNING: estimate_prompt_cost() took {cost_time:.3f}s")

        # Generate cache keys for each iteration
        cache_start = time.time()
        files_list = prompts.get("files_list", None)
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

        cache_time = time.time() - cache_start
        if cache_time > 0.05:  # Log if cache key generation takes more than 50ms
            print(
                f"[PROMPTS] WARNING: cache key generation took {cache_time:.3f}s for {iterations} iterations"
            )

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

        # Calculate time spent on other operations
        total_time = time.time() - other_start
        other_time = total_time - prompts_time - cost_time - cache_time

        timings = {
            "get_prompts": prompts_time,
            "cost_estimation": cost_time,
            "cache_generation": cache_time,
            "other": other_time,
            "prompt_breakdown": prompt_timing,  # Detailed breakdown of get_prompts()
        }

        return d, timings

    def prompts(self, iterations=1) -> "Dataset":
        """Return a Dataset of prompts that will be used.

        >>> from edsl.jobs import Jobs
        >>> Jobs.example().prompts()
        Dataset(...)
        """
        import time

        overall_start = time.time()
        print(f"[PROMPTS] Starting prompts() with {len(self.interviews)} interviews")

        from ..dataset import Dataset

        # Initialize dataset
        dataset_of_prompts = {k: [] for k in self.relevant_keys}
        interviews = self.interviews

        invigilator_creation_time = 0
        get_prompts_time = 0
        cost_estimation_time = 0
        cache_generation_time = 0
        other_processing_time = 0
        total_invigilators = 0

        # Detailed breakdown of get_prompts() time
        prompt_breakdown = {
            "agent_instructions": 0,
            "agent_persona": 0,
            "question_instructions": 0,
            "prior_question_memory": 0,
            "components_dict": 0,
            "prompt_plan": 0,
            "file_keys": 0,
        }

        # Process interviews
        for interview_index, interview in enumerate(interviews):
            if interview_index % 100 == 0 and interview_index > 0:
                print(
                    f"[PROMPTS] Processed {interview_index}/{len(interviews)} interviews, {total_invigilators} invigilators so far"
                )
                print(f"  - Invigilator creation: {invigilator_creation_time:.3f}s")
                print(f"  - get_prompts(): {get_prompts_time:.3f}s")

                # Show detailed breakdown
                breakdown_total = sum(prompt_breakdown.values())
                if breakdown_total > 0:
                    top_components = sorted(
                        prompt_breakdown.items(), key=lambda x: x[1], reverse=True
                    )[:3]
                    parts = []
                    for component, comp_time in top_components:
                        if comp_time > 0.01:
                            pct = (
                                (comp_time / get_prompts_time * 100)
                                if get_prompts_time > 0
                                else 0
                            )
                            parts.append(f"{component}:{comp_time:.2f}s ({pct:.0f}%)")
                    if parts:
                        print(f"    └─ {', '.join(parts)}")
                else:
                    print(f"    └─ [No breakdown data collected]")

                print(f"  - estimate_cost(): {cost_estimation_time:.3f}s")
                print(f"  - cache_keys: {cache_generation_time:.3f}s")
                print(f"  - other: {other_processing_time:.3f}s")

            # Create invigilators
            inv_start = time.time()
            invigilators = [
                FetchInvigilator(interview)(question)
                for question in interview.survey.questions
            ]
            invigilator_creation_time += time.time() - inv_start
            total_invigilators += len(invigilators)

            # Process invigilators
            for invigilator in invigilators:
                # Process the invigilator and get all data as a dictionary
                data, timings = self._process_one_invigilator(
                    invigilator, interview_index, iterations
                )
                get_prompts_time += timings["get_prompts"]
                cost_estimation_time += timings["cost_estimation"]
                cache_generation_time += timings["cache_generation"]
                other_processing_time += timings["other"]

                # Aggregate prompt breakdown if available
                if timings.get("prompt_breakdown"):
                    for key, value in timings["prompt_breakdown"].items():
                        if key in prompt_breakdown:
                            prompt_breakdown[key] += value

                for k in self.relevant_keys:
                    dataset_of_prompts[k].append(data[k])

        total_processing_time = (
            get_prompts_time
            + cost_estimation_time
            + cache_generation_time
            + other_processing_time
        )
        print(
            f"[PROMPTS] Processed all {len(interviews)} interviews, {total_invigilators} total invigilators"
        )
        print(f"  - Invigilator creation: {invigilator_creation_time:.3f}s")
        print(
            f"  - get_prompts(): {get_prompts_time:.3f}s ({get_prompts_time/total_processing_time*100:.1f}%)"
        )

        # Show detailed breakdown of get_prompts() time
        breakdown_total = sum(prompt_breakdown.values())
        if breakdown_total > 0:
            print(f"    Breakdown of get_prompts():")
            for component, comp_time in sorted(
                prompt_breakdown.items(), key=lambda x: x[1], reverse=True
            ):
                if (
                    comp_time > 0.01
                ):  # Only show components that took more than 10ms total
                    pct_of_prompts = (
                        (comp_time / get_prompts_time * 100)
                        if get_prompts_time > 0
                        else 0
                    )
                    pct_of_total = (
                        (comp_time / total_processing_time * 100)
                        if total_processing_time > 0
                        else 0
                    )
                    print(
                        f"      • {component}: {comp_time:.3f}s ({pct_of_prompts:.1f}% of get_prompts, {pct_of_total:.1f}% of total)"
                    )

        print(
            f"  - estimate_cost(): {cost_estimation_time:.3f}s ({cost_estimation_time/total_processing_time*100:.1f}%)"
        )
        print(
            f"  - cache_keys: {cache_generation_time:.3f}s ({cache_generation_time/total_processing_time*100:.1f}%)"
        )
        print(
            f"  - other: {other_processing_time:.3f}s ({other_processing_time/total_processing_time*100:.1f}%)"
        )
        print(f"  - Total processing: {total_processing_time:.3f}s")

        # Show cache statistics
        from ..prompts.prompt import _get_compiled_template

        cache_info = _get_compiled_template.cache_info()
        print(f"[PROMPTS] Jinja2 template cache: {cache_info}")
        if cache_info.misses > 0:
            hit_rate = cache_info.hits / (cache_info.hits + cache_info.misses) * 100
            print(
                f"[PROMPTS] Cache hit rate: {hit_rate:.1f}% ({cache_info.hits:,} hits / {cache_info.misses:,} misses)"
            )
            if cache_info.currsize >= cache_info.maxsize:
                print(
                    f"[PROMPTS] WARNING: Cache is full! Consider increasing maxsize from {cache_info.maxsize:,}"
                )

        # Create final dataset
        dataset_start = time.time()
        result = Dataset([{k: dataset_of_prompts[k]} for k in self.relevant_keys])
        print(f"[PROMPTS] Created Dataset in {time.time() - dataset_start:.3f}s")

        print(f"[PROMPTS] Total prompts() time: {time.time() - overall_start:.3f}s")
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
