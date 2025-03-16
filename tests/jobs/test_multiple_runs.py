import asyncio
import pytest
import nest_asyncio

from edsl.questions import QuestionFreeText
from edsl.agents import Agent

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

def test_multiple_runs(event_loop):
    # Set the event loop to our fresh loop
    asyncio.set_event_loop(event_loop)
    
    a = Agent(traits={})

    from edsl.caching import Cache

    a.add_direct_question_answering_method(lambda self, question, scenario: "yes")

    q = QuestionFreeText.example()
    results = q.by(a).run(n=2, cache=Cache())
    assert len(results) == 2
