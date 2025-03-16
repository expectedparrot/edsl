import asyncio
import pytest
import nest_asyncio

from edsl.agents import Agent
from edsl.surveys import Survey
from edsl.scenarios import Scenario
from edsl.questions import QuestionMultipleChoice
from edsl.interviews import Interview

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

@pytest.fixture(scope="function")
def event_loop():
    """Create an instance of the default event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    # Cleanup properly after each test
    loop.run_until_complete(asyncio.sleep(0))
    loop.close()


def test_retry(event_loop):
    #  a survey with skip logic
    q0 = QuestionMultipleChoice(
        question_text="Do you like school?",
        question_options=["yes", "no"],
        question_name="q0",
    )
    q1 = QuestionMultipleChoice(
        question_text="Why not?",
        question_options=["killer bees in cafeteria", "other"],
        question_name="q1",
    )
    q2 = QuestionMultipleChoice(
        question_text="Why?",
        question_options=["**lack*** of killer bees in cafeteria", "other"],
        question_name="q2",
    )
    s = Survey(questions=[q0, q1, q2])
    s = s.add_rule(q0, "q0 == 'yes'", q2)

    # create an interview
    a = Agent(traits=None)

    def service_that_fails_set_times(num_fails):
        "Closure that generates a function that fails num_fails times before succeeding."
        counter = 0

        def service_that_fails(self, question, scenario):
            nonlocal counter
            if counter < num_fails:
                counter += 1
                raise Exception("Failed!")
            else:
                return "yes"

        return service_that_fails

    direct_question_answering_method = service_that_fails_set_times(2)

    a.add_direct_question_answering_method(direct_question_answering_method)
    scenario = Scenario()
    from edsl.language_models.model import Model

    m = Model()
    I = Interview(agent=a, survey=s, scenario=scenario, model=m)

    # Set the event loop to our fresh loop
    asyncio.set_event_loop(event_loop)
    
    # Use the event loop object instead of asyncio.run which creates its own loop
    result = event_loop.run_until_complete(I.async_conduct_interview())
