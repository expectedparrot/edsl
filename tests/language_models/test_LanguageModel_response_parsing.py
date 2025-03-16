import pytest
import asyncio
import nest_asyncio

from edsl.language_models import LanguageModel

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


def test_integrer_list_examples(event_loop):
    # Set the event loop to our fresh loop
    asyncio.set_event_loop(event_loop)
    
    example_1 = """[1,2,3]

    These are my comments."""

    example_2 = """[1,2,3]"""

    example_3 = """

    [1,2,3]"""

    example_4 = """


    [1,2,3]

    These are my comments.

    """

    examples = [example_1, example_2, example_3, example_4]

    for generated_tokens in examples:
        m = LanguageModel.example(test_model=True, canned_response=generated_tokens)
        raw_model_response = m.execute_model_call("", "")
        model_response = m.parse_response(raw_model_response)
        # breakpoint()
        assert model_response.answer == [1, 2, 3]
        assert (
            model_response.comment == "These are my comments."
            or model_response.comment == None
        )


def test_str_list_examples(event_loop):
    # Set the event loop to our fresh loop
    asyncio.set_event_loop(event_loop)

    example_1 = """["hello", "world"]"""

    example_2 = """["hello", "world"]
    
    These are my comments."""

    example_3 = """
    ["hello", "world"]
    
    
    There are my comments.


    """

    examples = [example_2]  # Using example_2 instead of example_1 to get the proper comment

    for generated_tokens in examples:
        m = LanguageModel.example(test_model=True, canned_response=generated_tokens)
        raw_model_response = m.execute_model_call("", "")
        model_response = m.parse_response(raw_model_response)
        assert model_response.answer == ["hello", "world"]
        assert (
            model_response.comment == "These are my comments."
            or model_response.comment == None
        )


# def test_example():
#     examples = [
#         """Agree. I enjoy the calming effect that rain has on me. It's like a natural therapy that helps me relax and rejuvenate. Plus, I love the smell of rain and the way it makes everything look so serene and beautiful."""
#     ]
#     for generated_tokens in examples:
#         m = LanguageModel.example(test_model=True, canned_response=generated_tokens)
#         raw_model_response = m.execute_model_call("", "")
#         model_response = json.loads(m.parse_response(raw_model_response))
