import pytest
import asyncio
import nest_asyncio

from edsl.language_models import Model
from edsl.questions import QuestionFreeText

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

m = Model("test", canned_response="Hi", exception_probability=0.1, throw_exception=True)
q = QuestionFreeText(question_text="What is your name?", question_name="name")


def test_repair_enabled(event_loop):
    # Set the event loop to our fresh loop
    asyncio.set_event_loop(event_loop)
    
    results = q.by(m).run(n=100, progress_bar=False, cache=False, stop_on_exception=False)
    assert len([x for x in results.select("answer.name").to_list() if x == None]) == 0


def test_repair_off(event_loop):
    # Set the event loop to our fresh loop
    asyncio.set_event_loop(event_loop)
    
    with pytest.raises(Exception):
        results = q.by(m).run(
            n=100, progress_bar=False, cache=False, stop_on_exception=True
        )
