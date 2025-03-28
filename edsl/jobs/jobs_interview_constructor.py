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

def test_gc():
    """Test that interviews are properly garbage collected after being yielded."""
    from ..caching import Cache
    import weakref
    import gc
    
    from edsl import Jobs
    
    jobs = Jobs.example()
    jobs.replace_missing_objects()
    assert len(jobs.agents) > 0, "No agents in example job"
    assert len(jobs.models) > 0, "No models in example job"
    assert len(jobs.scenarios) > 0, "No scenarios in example job"
    

    constructor = InterviewsConstructor(jobs=jobs, cache=Cache())
    
    # Get the first interview and create a weak reference
    interview_iter = constructor.create_interviews()
    interview = next(interview_iter)  # Get the first interview
    interview_ref = weakref.ref(interview)
    
    # Verify we have a valid reference before deletion
    assert interview_ref() is not None, "Failed to create weak reference"
    
    # Remove our reference to the interview
    del interview
    
    # Force garbage collection
    gc.collect()
    assert interview_ref() is None, "Interview was not garbage collected"
    print("✓ Interview was successfully garbage collected")

if __name__ == "__main__":
    #test_gc()
    import doctest
    doctest.testmod()
