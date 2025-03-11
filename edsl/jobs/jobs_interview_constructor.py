from typing import Generator, TYPE_CHECKING
from itertools import product

if TYPE_CHECKING:
    from ..interviews import Interview
    from .jobs import Jobs
    from ..caching import Cache

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
        scenario_index = {
            hash(scenario): index for index, scenario in enumerate(self.jobs.scenarios)
        }

        for agent, scenario, model in product(
            self.jobs.agents, self.jobs.scenarios, self.jobs.models
        ):
            yield Interview(
                survey=self.jobs.survey.draw(), # this draw is to support shuffling of question options
                agent=agent,
                scenario=scenario,
                model=model,
                cache=self.cache,
                skip_retry=self.jobs.run_config.parameters.skip_retry,
                raise_validation_errors=self.jobs.run_config.parameters.raise_validation_errors,
                indices={
                    "agent": agent_index[hash(agent)],
                    "model": model_index[hash(model)],
                    "scenario": scenario_index[hash(scenario)],
                },
            )

if __name__ == "__main__":
    import doctest
    doctest.testmod()
