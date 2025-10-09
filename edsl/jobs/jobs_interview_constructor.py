from typing import Generator, TYPE_CHECKING
from itertools import product

if TYPE_CHECKING:
    from ..interviews import Interview
    from .jobs import Jobs
    from ..caching import Cache


# Module-level timing dictionary for create_interviews performance tracking
_create_interviews_timing = {
    "hash_agents": 0.0,
    "hash_models": 0.0,
    "hash_scenarios": 0.0,
    "product_iteration": 0.0,
    "survey_draw": 0.0,
    "interview_creation": 0.0,
    "hash_lookups": 0.0,
    "total": 0.0,
    "call_count": 0,
}


class InterviewsConstructor:
    def __init__(self, jobs: "Jobs", cache: "Cache"):
        self.jobs = jobs
        self.cache = cache

    def create_interviews(self) -> Generator["Interview", None, None]:
        """
        Generates interviews.

        Note that this sets the agents, model and scenarios if they have not been set. This is a side effect of the method.
        This is useful because a user can create a job without setting the agents, models, or scenarios, and the job will still run,
        with us filling in defaults.

        """
        import time
        from ..interviews import Interview

        global _create_interviews_timing
        method_start = time.time()
        _create_interviews_timing["call_count"] += 1

        t0 = time.time()
        agent_index = {
            hash(agent): index for index, agent in enumerate(self.jobs.agents)
        }
        _create_interviews_timing["hash_agents"] += time.time() - t0

        t1 = time.time()
        model_index = {
            hash(model): index for index, model in enumerate(self.jobs.models)
        }
        _create_interviews_timing["hash_models"] += time.time() - t1

        t2 = time.time()
        scenario_index = {}
        for index, scenario in enumerate(self.jobs.scenarios):
            scenario.my_hash = hash(scenario)
            scenario_index[scenario.my_hash] = index
        _create_interviews_timing["hash_scenarios"] += time.time() - t2

        t3 = time.time()
        for agent, scenario, model in product(
            self.jobs.agents, self.jobs.scenarios, self.jobs.models
        ):
            t4 = time.time()
            agent_hash = hash(agent)
            model_hash = hash(model)

            if hasattr(scenario, "my_hash"):
                scenario_hash = scenario.my_hash
            else:
                scenario_hash = hash(scenario)
                scenario.my_hash = scenario_hash
            _create_interviews_timing["hash_lookups"] += time.time() - t4

            t5 = time.time()
            drawn_survey = (
                self.jobs.survey.draw()
            )  # this draw is to support shuffling of question options
            _create_interviews_timing["survey_draw"] += time.time() - t5

            t6 = time.time()
            interview = Interview(
                survey=drawn_survey,
                agent=agent,
                scenario=scenario,
                model=model,
                cache=self.cache,
                skip_retry=self.jobs.run_config.parameters.skip_retry,
                raise_validation_errors=self.jobs.run_config.parameters.raise_validation_errors,
                indices={
                    "agent": agent_index[agent_hash],
                    "model": model_index[model_hash],
                    "scenario": scenario_index[scenario_hash],
                },
            )
            _create_interviews_timing["interview_creation"] += time.time() - t6

            yield interview

        _create_interviews_timing["product_iteration"] += time.time() - t3
        _create_interviews_timing["total"] += time.time() - method_start


if __name__ == "__main__":
    # test_gc()
    import doctest

    doctest.testmod()
