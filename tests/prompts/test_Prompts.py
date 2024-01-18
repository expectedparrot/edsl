import doctest
import edsl.prompts


def test_doctests_in_prompt():
    doctest.testmod(edsl.prompts)


def test_foo():
    pass
