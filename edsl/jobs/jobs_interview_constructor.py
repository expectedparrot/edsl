from typing import Generator, TYPE_CHECKING
from itertools import product

if TYPE_CHECKING:
    from ..interviews import Interview
    from .jobs import Jobs
    from ..caching import Cache

import time


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
        from ..interviews import Interview

        agent_index = {
            hash(agent): index for index, agent in enumerate(self.jobs.agents)
        }
        model_index = {
            hash(model): index for index, model in enumerate(self.jobs.models)
        }
        scenario_index = {}
        for index, scenario in enumerate(self.jobs.scenarios):
            scenario.my_hash = hash(scenario)
            scenario_index[scenario.my_hash] = index

        for agent, scenario, model in product(
            self.jobs.agents, self.jobs.scenarios, self.jobs.models
        ):
            agent_hash = hash(agent)
            model_hash = hash(model)

            if hasattr(scenario, "my_hash"):
                scenario_hash = scenario.my_hash
            else:
                scenario_hash = hash(scenario)
                scenario.my_hash = scenario_hash

            interview = Interview(
                survey=self.jobs.survey.draw(),  # this draw is to support shuffling of question options
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

            yield interview


if __name__ == "__main__":
    # test_gc()
    import doctest

    doctest.testmod()
