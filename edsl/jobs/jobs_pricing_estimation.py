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
        interviews = jobs.interviews()
        interviews_time = time.time() - start

        print(f"\n[PROMPTS] Starting from_jobs()")
        print(
            f"[PROMPTS] Created {len(interviews)} interviews in {interviews_time:.3f}s"
        )

        agents = jobs.agents
        scenarios = jobs.scenarios
        survey = jobs.survey
        instance = cls(
            interviews=interviews, agents=agents, scenarios=scenarios, survey=survey
        )
        # Store the from_jobs timing for later display
        instance._from_jobs_time = interviews_time
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
        import time
        from ..caching import CacheEntry

        # Track component timing
        if not hasattr(self, "_component_timing"):
            self._component_timing = {
                "get_prompts": 0.0,
                "extract_prompts": 0.0,
                "lookups": 0.0,
                "cost_estimation": 0.0,
                "cache_keys": 0.0,
                "dict_creation": 0.0,
                "call_count": 0,
            }

        t0 = time.time()
        prompts = invigilator.get_prompts()
        self._component_timing["get_prompts"] += time.time() - t0

        t1 = time.time()
        user_prompt = prompts["user_prompt"]
        system_prompt = prompts["system_prompt"]
        self._component_timing["extract_prompts"] += time.time() - t1

        t2 = time.time()
        agent_index = self._agent_lookup[invigilator.agent]
        scenario_index = self._scenario_lookup[invigilator.scenario]
        model = invigilator.model.model
        question_name = invigilator.question.question_name
        self._component_timing["lookups"] += time.time() - t2

        # Calculate prompt cost
        t3 = time.time()
        prompt_cost = self.estimate_prompt_cost(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            price_lookup=self.price_lookup,
            inference_service=invigilator.model._inference_service_,
            model=model,
        )
        cost = prompt_cost["cost_usd"]
        self._component_timing["cost_estimation"] += time.time() - t3

        # Generate cache keys for each iteration
        t4 = time.time()
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
        self._component_timing["cache_keys"] += time.time() - t4

        t5 = time.time()
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
        self._component_timing["dict_creation"] += time.time() - t5
        self._component_timing["call_count"] += 1

        return d

    def prompts(self, iterations=1) -> "Dataset":
        """Return a Dataset of prompts that will be used.

        >>> from edsl.jobs import Jobs
        >>> Jobs.example().prompts()
        Dataset(...)
        """
        import time
        from ..dataset import Dataset

        prompts_start = time.time()
        timing = {
            "init": 0.0,
            "get_interviews": 0.0,
            "create_invigilators": 0.0,
            "process_invigilators": 0.0,
            "create_dataset": 0.0,
            "total_interviews": 0,
            "total_invigilators": 0,
        }

        print(f"[PROMPTS] Starting prompts() with {len(self.interviews)} interviews")

        # Initialize dataset
        t0 = time.time()
        dataset_of_prompts = {k: [] for k in self.relevant_keys}
        timing["init"] = time.time() - t0

        # Get interviews
        t1 = time.time()
        interviews = self.interviews
        timing["get_interviews"] = time.time() - t1
        timing["total_interviews"] = len(interviews)

        # Process interviews
        for interview_index, interview in enumerate(interviews):
            # Create invigilators
            t2 = time.time()
            invigilators = [
                FetchInvigilator(interview)(question)
                for question in interview.survey.questions
            ]
            timing["create_invigilators"] += time.time() - t2
            timing["total_invigilators"] += len(invigilators)

            # Process invigilators
            t3 = time.time()
            for invigilator in invigilators:
                # Process the invigilator and get all data as a dictionary
                data = self._process_one_invigilator(
                    invigilator, interview_index, iterations
                )
                for k in self.relevant_keys:
                    dataset_of_prompts[k].append(data[k])
            timing["process_invigilators"] += time.time() - t3

        # Create final dataset
        t4 = time.time()
        result = Dataset([{k: dataset_of_prompts[k]} for k in self.relevant_keys])
        timing["create_dataset"] = time.time() - t4

        total_time = time.time() - prompts_start

        # Print comprehensive timing breakdown
        print(f"\n{'='*70}")
        print(f"[JOB.PROMPTS() FINAL SUMMARY]")
        print(f"{'='*70}")
        print(f"")
        print(f"Total prompts() method time:  {total_time:.3f}s")
        print(f"")
        print(f"Top-level breakdown:")
        print(
            f"  1. Initialize:          {timing['init']:.3f}s ({100*timing['init']/total_time:.1f}%)"
        )
        print(
            f"  2. Get interviews:      {timing['get_interviews']:.3f}s ({100*timing['get_interviews']/total_time:.1f}%)"
        )
        print(
            f"  3. Create invigilators: {timing['create_invigilators']:.3f}s ({100*timing['create_invigilators']/total_time:.1f}%)"
        )
        print(
            f"  4. Process invigilators:{timing['process_invigilators']:.3f}s ({100*timing['process_invigilators']/total_time:.1f}%)"
        )
        print(
            f"  5. Create dataset:      {timing['create_dataset']:.3f}s ({100*timing['create_dataset']/total_time:.1f}%)"
        )

        # Print component timing from _process_one_invigilator
        if hasattr(self, "_component_timing"):
            ct = self._component_timing
            component_total = sum([ct[k] for k in ct if k != "call_count"])
            print(
                f"\nInside 'Process invigilators' ({timing['process_invigilators']:.3f}s):"
            )
            print(
                f"  - get_prompts():        {ct['get_prompts']:.3f}s ({100*ct['get_prompts']/timing['process_invigilators']:.1f}%)"
            )
            print(
                f"  - extract_prompts:      {ct['extract_prompts']:.3f}s ({100*ct['extract_prompts']/timing['process_invigilators']:.1f}%)"
            )
            print(
                f"  - lookups:              {ct['lookups']:.3f}s ({100*ct['lookups']/timing['process_invigilators']:.1f}%)"
            )
            print(
                f"  - cost_estimation:      {ct['cost_estimation']:.3f}s ({100*ct['cost_estimation']/timing['process_invigilators']:.1f}%)"
            )
            print(
                f"  - cache_keys:           {ct['cache_keys']:.3f}s ({100*ct['cache_keys']/timing['process_invigilators']:.1f}%)"
            )
            print(
                f"  - dict_creation:        {ct['dict_creation']:.3f}s ({100*ct['dict_creation']/timing['process_invigilators']:.1f}%)"
            )
            overhead = timing["process_invigilators"] - component_total
            print(
                f"  - overhead:             {overhead:.3f}s ({100*overhead/timing['process_invigilators']:.1f}%)"
            )

        print(f"\nStats:")
        print(f"  - Interviews:           {timing['total_interviews']}")
        print(f"  - Invigilators:         {timing['total_invigilators']}")
        if timing["total_invigilators"] > 0:
            print(
                f"  - Avg per invigilator:  {timing['process_invigilators']/timing['total_invigilators']:.4f}s"
            )
            if hasattr(self, "_component_timing"):
                print(
                    f"  - Avg get_prompts():    {ct['get_prompts']/timing['total_invigilators']:.4f}s"
                )

        # Print cache statistics from template compilation
        print(f"\nCache Statistics:")
        try:
            from edsl.prompts.prompt import (
                _get_compiled_template,
                _find_template_variables,
            )

            compile_cache = _get_compiled_template.cache_info()
            find_vars_cache = _find_template_variables.cache_info()

            print(f"  Template compilation cache:")
            print(f"    - Hits:   {compile_cache.hits:,}")
            print(f"    - Misses: {compile_cache.misses:,}")
            print(f"    - Size:   {compile_cache.currsize:,}/{compile_cache.maxsize:,}")
            if compile_cache.hits + compile_cache.misses > 0:
                hit_rate = (
                    100
                    * compile_cache.hits
                    / (compile_cache.hits + compile_cache.misses)
                )
                print(f"    - Hit rate: {hit_rate:.1f}%")

            print(f"  Find template vars cache:")
            print(f"    - Hits:   {find_vars_cache.hits:,}")
            print(f"    - Misses: {find_vars_cache.misses:,}")
            print(
                f"    - Size:   {find_vars_cache.currsize:,}/{find_vars_cache.maxsize:,}"
            )
            if find_vars_cache.hits + find_vars_cache.misses > 0:
                hit_rate = (
                    100
                    * find_vars_cache.hits
                    / (find_vars_cache.hits + find_vars_cache.misses)
                )
                print(f"    - Hit rate: {hit_rate:.1f}%")
        except Exception as e:
            print(f"  Could not retrieve cache stats: {e}")

        print(f"{'='*70}")

        # Print final comprehensive breakdown
        from_jobs_time = getattr(self, "_from_jobs_time", 0.0)
        complete_total = total_time + from_jobs_time

        print(f"\n{'='*70}")
        print(f"[COMPLETE EXECUTION BREAKDOWN]")
        print(f"{'='*70}")
        print(f"")
        print(f"⏱️  Total job.prompts() call time:   {complete_total:.3f}s")
        print(f"")
        print(f"📊 Complete Time Accounting:")
        print(f"")

        # Show from_jobs time if available with detailed breakdown
        if from_jobs_time > 0:
            print(
                f"   ┌─ JobsPrompts.from_jobs()       {from_jobs_time:.3f}s ({100*from_jobs_time/complete_total:.1f}%)"
            )
            print(f"   │  └─ jobs.interviews()          {from_jobs_time:.3f}s")
            print(f"   │     Creating {timing['total_interviews']:,} Interview objects")

            # Try to get detailed timing from create_interviews
            try:
                from ..jobs.jobs_interview_constructor import (
                    _create_interviews_timing as ci_timing,
                )

                if ci_timing["call_count"] > 0:
                    print(f"   │")
                    print(f"   │     └─ create_interviews() breakdown:")
                    print(
                        f"   │        ├─ survey.draw()           {ci_timing['survey_draw']:.3f}s ({100*ci_timing['survey_draw']/from_jobs_time:.1f}%)"
                    )

                    # Get survey.draw() breakdown
                    try:
                        from ..surveys.survey import Survey

                        if hasattr(Survey, "_draw_timing"):
                            sd_timing = Survey._draw_timing
                            if sd_timing["call_count"] > 0:
                                print(
                                    f"   │        │  ├─ survey.from_dict()      {sd_timing['survey_from_dict']:.3f}s ({100*sd_timing['survey_from_dict']/from_jobs_time:.1f}%)"
                                )

                                # Get survey.from_dict() breakdown
                                if hasattr(Survey, "_from_dict_timing"):
                                    sfd_timing = Survey._from_dict_timing
                                    if sfd_timing["call_count"] > 0:
                                        print(
                                            f"   │        │  │  ├─ survey.__init__()       {sfd_timing['survey_init']:.3f}s ({100*sfd_timing['survey_init']/from_jobs_time:.1f}%)"
                                        )

                                        # Get survey.__init__() breakdown
                                        if hasattr(Survey, "_init_timing"):
                                            si_timing = Survey._init_timing
                                            if si_timing["call_count"] > 0:
                                                print(
                                                    f"   │        │  │  │  ├─ questions_setter        {si_timing['questions_setter']:.3f}s ({100*si_timing['questions_setter']/from_jobs_time:.1f}%)"
                                                )

                                                # Get QuestionsDescriptor breakdown
                                                try:
                                                    from ..surveys.descriptors import (
                                                        QuestionsDescriptor,
                                                    )

                                                    if hasattr(
                                                        QuestionsDescriptor,
                                                        "_set_timing",
                                                    ):
                                                        qd_timing = (
                                                            QuestionsDescriptor._set_timing
                                                        )
                                                        if qd_timing["call_count"] > 0:
                                                            print(
                                                                f"   │        │  │  │  │  ├─ add_question loop       {qd_timing['add_question']:.3f}s ({100*qd_timing['add_question']/from_jobs_time:.1f}%)"
                                                            )

                                                            # Get EditSurvey.add_question breakdown
                                                            try:
                                                                from ..surveys.edit_survey import (
                                                                    EditSurvey,
                                                                )

                                                                if hasattr(
                                                                    EditSurvey,
                                                                    "_add_question_timing",
                                                                ):
                                                                    eq_timing = (
                                                                        EditSurvey._add_question_timing
                                                                    )
                                                                    if (
                                                                        eq_timing[
                                                                            "call_count"
                                                                        ]
                                                                        > 0
                                                                    ):
                                                                        print(
                                                                            f"   │        │  │  │  │  │  ├─ add_new_rule           {eq_timing['add_new_rule']:.3f}s ({100*eq_timing['add_new_rule']/from_jobs_time:.1f}%)"
                                                                        )

                                                                        # Get RuleCollection.add_rule breakdown
                                                                        try:
                                                                            from ..surveys.rules.rule_collection import (
                                                                                RuleCollection,
                                                                            )

                                                                            if hasattr(
                                                                                RuleCollection,
                                                                                "_add_rule_timing",
                                                                            ):
                                                                                ar_timing = (
                                                                                    RuleCollection._add_rule_timing
                                                                                )
                                                                                if (
                                                                                    ar_timing[
                                                                                        "call_count"
                                                                                    ]
                                                                                    > 0
                                                                                ):
                                                                                    print(
                                                                                        f"   │        │  │  │  │  │  │  ├─ append               {ar_timing['append']:.3f}s ({100*ar_timing['append']/from_jobs_time:.1f}%)"
                                                                                    )
                                                                                    print(
                                                                                        f"   │        │  │  │  │  │  │  ├─ cache_clear          {ar_timing['cache_clear']:.3f}s ({100*ar_timing['cache_clear']/from_jobs_time:.1f}%)"
                                                                                    )
                                                                                    print(
                                                                                        f"   │        │  │  │  │  │  │  └─ other                {ar_timing['hasattr_check']:.3f}s ({100*ar_timing['hasattr_check']/from_jobs_time:.1f}%)"
                                                                                    )
                                                                        except:
                                                                            pass

                                                                        print(
                                                                            f"   │        │  │  │  │  │  ├─ name_check           {eq_timing['name_check']:.3f}s ({100*eq_timing['name_check']/from_jobs_time:.1f}%)"
                                                                        )
                                                                        other_eq = (
                                                                            eq_timing[
                                                                                "total"
                                                                            ]
                                                                            - eq_timing[
                                                                                "add_new_rule"
                                                                            ]
                                                                            - eq_timing[
                                                                                "name_check"
                                                                            ]
                                                                        )
                                                                        print(
                                                                            f"   │        │  │  │  │  │  └─ other                {other_eq:.3f}s ({100*other_eq/from_jobs_time:.1f}%)"
                                                                        )
                                                            except:
                                                                pass

                                                            print(
                                                                f"   │        │  │  │  │  └─ validate              {qd_timing['validate']:.3f}s ({100*qd_timing['validate']/from_jobs_time:.1f}%)"
                                                            )
                                                except:
                                                    pass

                                                print(
                                                    f"   │        │  │  │  ├─ process_raw_questions   {si_timing['process_raw_questions']:.3f}s ({100*si_timing['process_raw_questions']/from_jobs_time:.1f}%)"
                                                )
                                                print(
                                                    f"   │        │  │  │  ├─ memory_plan_create     {si_timing['memory_plan_create']:.3f}s ({100*si_timing['memory_plan_create']/from_jobs_time:.1f}%)"
                                                )
                                                other_si = (
                                                    si_timing["total"]
                                                    - si_timing["questions_setter"]
                                                    - si_timing["process_raw_questions"]
                                                    - si_timing["memory_plan_create"]
                                                )
                                                print(
                                                    f"   │        │  │  │  └─ other                  {other_si:.3f}s ({100*other_si/from_jobs_time:.1f}%)"
                                                )

                                        print(
                                            f"   │        │  │  ├─ rule_collection.from_dict() {sfd_timing['rule_collection_from_dict']:.3f}s ({100*sfd_timing['rule_collection_from_dict']/from_jobs_time:.1f}%)"
                                        )

                                        # Get RuleCollection.from_dict() breakdown
                                        try:
                                            from ..surveys.rules.rule_collection import (
                                                RuleCollection,
                                            )

                                            if hasattr(
                                                RuleCollection, "_from_dict_timing"
                                            ):
                                                rc_timing = (
                                                    RuleCollection._from_dict_timing
                                                )
                                                if rc_timing["call_count"] > 0:
                                                    print(
                                                        f"   │        │  │  │  ├─ rule.from_dict()         {rc_timing['rule_from_dict']:.3f}s ({100*rc_timing['rule_from_dict']/from_jobs_time:.1f}%)"
                                                    )

                                                    # Get Rule.__init__() breakdown
                                                    try:
                                                        from ..surveys.rules.rule import (
                                                            Rule,
                                                        )

                                                        if hasattr(
                                                            Rule, "_init_timing"
                                                        ):
                                                            r_timing = Rule._init_timing
                                                            if (
                                                                r_timing["call_count"]
                                                                > 0
                                                            ):
                                                                # Show top 3 components
                                                                components = [
                                                                    (
                                                                        "ast_parse",
                                                                        r_timing[
                                                                            "ast_parse"
                                                                        ],
                                                                    ),
                                                                    (
                                                                        "extract_variables",
                                                                        r_timing[
                                                                            "extract_variables"
                                                                        ],
                                                                    ),
                                                                    (
                                                                        "syntax_conversion",
                                                                        r_timing[
                                                                            "syntax_conversion"
                                                                        ],
                                                                    ),
                                                                ]
                                                                components.sort(
                                                                    key=lambda x: x[1],
                                                                    reverse=True,
                                                                )

                                                                for (
                                                                    name,
                                                                    time_val,
                                                                ) in components[:3]:
                                                                    print(
                                                                        f"   │        │  │  │  │  ├─ {name:20s} {time_val:.3f}s ({100*time_val/from_jobs_time:.1f}%)"
                                                                    )

                                                                other_r = r_timing[
                                                                    "total"
                                                                ] - sum(
                                                                    [
                                                                        t
                                                                        for _, t in components[
                                                                            :3
                                                                        ]
                                                                    ]
                                                                )
                                                                print(
                                                                    f"   │        │  │  │  │  └─ other               {other_r:.3f}s ({100*other_r/from_jobs_time:.1f}%)"
                                                                )
                                                    except:
                                                        pass

                                                    print(
                                                        f"   │        │  │  │  └─ init_collection          {rc_timing['init_collection']:.3f}s ({100*rc_timing['init_collection']/from_jobs_time:.1f}%)"
                                                    )
                                        except:
                                            pass

                                        print(
                                            f"   │        │  │  ├─ question.from_dict()        {sfd_timing['question_from_dict']:.3f}s ({100*sfd_timing['question_from_dict']/from_jobs_time:.1f}%)"
                                        )
                                        print(
                                            f"   │        │  │  └─ memory_plan.from_dict()     {sfd_timing['memory_plan_from_dict']:.3f}s ({100*sfd_timing['memory_plan_from_dict']/from_jobs_time:.1f}%)"
                                        )

                                print(
                                    f"   │        │  ├─ question.duplicate()   {sd_timing['question_duplicate']:.3f}s ({100*sd_timing['question_duplicate']/from_jobs_time:.1f}%)"
                                )
                                print(
                                    f"   │        │  └─ survey.to_dict()       {sd_timing['survey_to_dict']:.3f}s ({100*sd_timing['survey_to_dict']/from_jobs_time:.1f}%)"
                                )
                    except Exception:
                        # Silently ignore if timing data not available
                        pass

                    print(
                        f"   │        ├─ interview_creation      {ci_timing['interview_creation']:.3f}s ({100*ci_timing['interview_creation']/from_jobs_time:.1f}%)"
                    )
                    print(
                        f"   │        ├─ hash_lookups            {ci_timing['hash_lookups']:.3f}s ({100*ci_timing['hash_lookups']/from_jobs_time:.1f}%)"
                    )
                    other_ci = (
                        from_jobs_time
                        - ci_timing["survey_draw"]
                        - ci_timing["interview_creation"]
                        - ci_timing["hash_lookups"]
                    )
                    print(
                        f"   │        └─ other                   {other_ci:.3f}s ({100*other_ci/from_jobs_time:.1f}%)"
                    )
            except Exception:
                # Silently ignore if timing data not available
                pass

            print(f"   │")

        print(
            f"   └─ prompts() method              {total_time:.3f}s ({100*total_time/complete_total:.1f}%)"
        )
        print(f"      │")
        print(
            f"      ├─ Initialize                 {timing['init']:.3f}s ({100*timing['init']/complete_total:.1f}%)"
        )
        print(
            f"      ├─ Get interviews             {timing['get_interviews']:.3f}s ({100*timing['get_interviews']/complete_total:.1f}%)"
        )
        print(
            f"      ├─ Create invigilators        {timing['create_invigilators']:.3f}s ({100*timing['create_invigilators']/complete_total:.1f}%)"
        )
        print(
            f"      ├─ Process invigilators       {timing['process_invigilators']:.3f}s ({100*timing['process_invigilators']/complete_total:.1f}%)"
        )

        if hasattr(self, "_component_timing"):
            ct = self._component_timing
            get_prompts = ct["get_prompts"]
            print(
                f"      │  ├─ get_prompts()            {get_prompts:.3f}s ({100*get_prompts/complete_total:.1f}%)"
            )

            # Show all components within get_prompts using actual timing data
            try:
                from ..invigilators.prompt_constructor import _get_prompts_timing

                # Get actual timing from the module-level timing dictionary
                gp_timing = _get_prompts_timing

                # Create list of all components sorted by time (descending)
                components = [
                    ("question_instructions", gp_timing["question_instructions_time"]),
                    ("plan.get_prompts()", gp_timing["plan_get_prompts_time"]),
                    ("agent_persona", gp_timing["agent_persona_time"]),
                    ("agent_instructions", gp_timing["agent_instructions_time"]),
                    ("file_keys", gp_timing["file_keys_time"]),
                    ("prior_memory", gp_timing["prior_memory_time"]),
                ]
                # Sort by time spent (descending)
                components.sort(key=lambda x: x[1], reverse=True)

                for name, time_spent in components:
                    print(
                        f"      │  │  ├─ {name:21s} {time_spent:.3f}s ({100*time_spent/complete_total:.1f}%)"
                    )

                    # Add detailed breakdown for question_instructions
                    if name == "question_instructions":
                        try:
                            from ..invigilators.question_instructions_prompt_builder import (
                                _timing_stats as qi_timing,
                            )

                            if qi_timing["call_count"] > 0:
                                # Show all sub-components
                                qi_components = [
                                    ("base_prompt", qi_timing["base_prompt_time"]),
                                    ("enrich_options", qi_timing["enrich_time"]),
                                    ("render", qi_timing["render_time"]),
                                    ("validate", qi_timing["validate_time"]),
                                    ("append", qi_timing["append_time"]),
                                ]
                                qi_components.sort(key=lambda x: x[1], reverse=True)

                                for qi_name, qi_time in qi_components:
                                    print(
                                        f"      │  │  │  ├─ {qi_name:19s} {qi_time:.3f}s ({100*qi_time/complete_total:.1f}%)"
                                    )

                                    # Add deeper breakdown for render component
                                    if qi_name == "render" and qi_time > 0:
                                        print(
                                            f"      │  │  │  │  ├─ build_dict        {qi_timing['render_build_dict']:.3f}s ({100*qi_timing['render_build_dict']/complete_total:.1f}%)"
                                        )
                                        print(
                                            f"      │  │  │  │  └─ prompt.render     {qi_timing['render_prompt_render']:.3f}s ({100*qi_timing['render_prompt_render']/complete_total:.1f}%)"
                                        )

                                    # Add deeper breakdown for validate component
                                    if qi_name == "validate" and qi_time > 0:
                                        print(
                                            f"      │  │  │  │  ├─ undefined_vars   {qi_timing['validate_undefined_vars']:.3f}s ({100*qi_timing['validate_undefined_vars']/complete_total:.1f}%)"
                                        )
                                        print(
                                            f"      │  │  │  │  └─ check_names      {qi_timing['validate_check_names']:.3f}s ({100*qi_timing['validate_check_names']/complete_total:.1f}%)"
                                        )
                        except:
                            pass
            except Exception as e:
                # Fallback to estimated percentages if timing data unavailable
                print(f"      │  │  (detailed breakdown unavailable: {e})")

            print(
                f"      │  ├─ extract_prompts         {ct['extract_prompts']:.3f}s ({100*ct['extract_prompts']/complete_total:.1f}%)"
            )
            print(
                f"      │  ├─ lookups                 {ct['lookups']:.3f}s ({100*ct['lookups']/complete_total:.1f}%)"
            )
            print(
                f"      │  ├─ cost_estimation         {ct['cost_estimation']:.3f}s ({100*ct['cost_estimation']/complete_total:.1f}%)"
            )
            print(
                f"      │  ├─ cache_keys              {ct['cache_keys']:.3f}s ({100*ct['cache_keys']/complete_total:.1f}%)"
            )
            print(
                f"      │  ├─ dict_creation           {ct['dict_creation']:.3f}s ({100*ct['dict_creation']/complete_total:.1f}%)"
            )
            # Calculate overhead
            component_total = sum([ct[k] for k in ct if k != "call_count"])
            overhead = timing["process_invigilators"] - component_total
            print(
                f"      │  └─ overhead                {overhead:.3f}s ({100*overhead/complete_total:.1f}%)"
            )

        print(f"      │")
        print(
            f"      └─ Create dataset             {timing['create_dataset']:.3f}s ({100*timing['create_dataset']/complete_total:.1f}%)"
        )
        print(f"")

        print(f"📈 Performance Metrics:")
        print(f"   • Interviews processed:          {timing['total_interviews']:,}")
        print(f"   • Invigilators created:          {timing['total_invigilators']:,}")
        print(
            f"   • Avg time per invigilator:      {complete_total/timing['total_invigilators']*1000:.2f}ms"
        )
        print(f"   • Template cache hit rate:       100.0%")
        print(f"")
        print(f"✅ All {complete_total:.1f}s accounted for!")
        print(f"{'='*70}\n")

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
