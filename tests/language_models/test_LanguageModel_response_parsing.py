from edsl.language_models import LanguageModel


def test_integrer_list_examples():
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


def test_str_list_examples():

    example_1 = """["hello", "world"]"""

    example_1 = """["hello", "world"]
    
    These are my comments."""

    example_3 = """
    ["hello", "world"]
    
    
    There are my comments.


    """

    examples = [example_1]

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
