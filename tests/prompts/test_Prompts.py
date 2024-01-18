import doctest
import edsl.prompts.Prompt


def test_doctests_in_prompt():
    doctest.testmod(edsl.prompts.Prompt)


def test_foo():
    pass
