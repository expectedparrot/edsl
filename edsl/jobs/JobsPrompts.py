from typing import List, TYPE_CHECKING

from edsl.results.Dataset import Dataset

if TYPE_CHECKING:
    from edsl.jobs import Jobs

    # from edsl.jobs.interviews.Interview import Interview
    # from edsl.results.Dataset import Dataset
    # from edsl.agents.AgentList import AgentList
    # from edsl.scenarios.ScenarioList import ScenarioList
    # from edsl.surveys.Survey import Survey


class JobsPrompts:
    def __init__(self, jobs: "Jobs"):
        self.interviews = jobs.interviews()
        self.agents = jobs.agents
        self.scenarios = jobs.scenarios
        self.survey = jobs.survey
        self._price_lookup = None

    @property
    def price_lookup(self):
        if self._price_lookup is None:
            from edsl import Coop

            c = Coop()
            self._price_lookup = c.fetch_prices()
        return self._price_lookup

    def prompts(self) -> "Dataset":
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

        for interview_index, interview in enumerate(interviews):
            invigilators = [
                interview._get_invigilator(question)
                for question in self.survey.questions
            ]
            for _, invigilator in enumerate(invigilators):
                prompts = invigilator.get_prompts()
                user_prompt = prompts["user_prompt"]
                system_prompt = prompts["system_prompt"]
                user_prompts.append(user_prompt)
                system_prompts.append(system_prompt)
                agent_index = self.agents.index(invigilator.agent)
                agent_indices.append(agent_index)
                interview_indices.append(interview_index)
                scenario_index = self.scenarios.index(invigilator.scenario)
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
        """Estimates the cost of a prompt. Takes piping into account."""
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
                "Price data could not be retrieved. Using default estimates for input and output token prices. Input: $0.15 / 1M tokens; Output: $0.60 / 1M tokens"
            )
            input_price_per_token = 0.00000015  # $0.15 / 1M tokens
            output_price_per_token = 0.00000060  # $0.60 / 1M tokens

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

    def estimate_job_cost_from_external_prices(
        self, price_lookup: dict, iterations: int = 1
    ) -> dict:
        """
        Estimates the cost of a job according to the following assumptions:

        - 1 token = 4 characters.
        - For each prompt, output tokens = input tokens * 0.75, rounded up to the nearest integer.

        price_lookup is an external pricing dictionary.
        """

        import pandas as pd

        interviews = self.interviews
        data = []
        for interview in interviews:
            invigilators = [
                interview._get_invigilator(question)
                for question in self.survey.questions
            ]
            for invigilator in invigilators:
                prompts = invigilator.get_prompts()

                # By this point, agent and scenario data has already been added to the prompts
                user_prompt = prompts["user_prompt"]
                system_prompt = prompts["system_prompt"]
                inference_service = invigilator.model._inference_service_
                model = invigilator.model.model

                prompt_cost = self.estimate_prompt_cost(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    price_lookup=price_lookup,
                    inference_service=inference_service,
                    model=model,
                )

                data.append(
                    {
                        "user_prompt": user_prompt,
                        "system_prompt": system_prompt,
                        "estimated_input_tokens": prompt_cost["input_tokens"],
                        "estimated_output_tokens": prompt_cost["output_tokens"],
                        "estimated_cost_usd": prompt_cost["cost_usd"],
                        "inference_service": inference_service,
                        "model": model,
                    }
                )

        df = pd.DataFrame.from_records(data)

        df = (
            df.groupby(["inference_service", "model"])
            .agg(
                {
                    "estimated_cost_usd": "sum",
                    "estimated_input_tokens": "sum",
                    "estimated_output_tokens": "sum",
                }
            )
            .reset_index()
        )
        df["estimated_cost_usd"] = df["estimated_cost_usd"] * iterations
        df["estimated_input_tokens"] = df["estimated_input_tokens"] * iterations
        df["estimated_output_tokens"] = df["estimated_output_tokens"] * iterations

        estimated_costs_by_model = df.to_dict("records")

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
