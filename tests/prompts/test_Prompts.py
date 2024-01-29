import pytest
import doctest
import edsl.prompts


def test_doctests_in_prompt():
    doctest.testmod(edsl.prompts)


from edsl.prompts.Prompt import PromptBase
from edsl.prompts.prompt_config import ComponentTypes

from edsl.exceptions.prompts import TemplateRenderError

from edsl.exceptions.prompts import (
    PromptBadQuestionTypeError,
    PromptBadLanguageModelTypeError,
)


def test_instantiation():
    class NewPrompt(PromptBase):
        component_type = ComponentTypes.GENERIC

    # questions have to have a question_type
    with pytest.raises(PromptBadQuestionTypeError):

        class NewBadQuestionPrompt(PromptBase):
            component_type = ComponentTypes.QUESTION_INSTRUCTIONS

    # if they have a type, it has to be from the enum of question types
    with pytest.raises(PromptBadQuestionTypeError):

        class NewNewBadQuestionPrompt(PromptBase):
            component_type = ComponentTypes.QUESTION_INSTRUCTIONS
            question_type = "poo"

    class NewGoogQuestionPrompt(PromptBase):
        component_type = ComponentTypes.QUESTION_INSTRUCTIONS
        question_type = "free_text"

    # if they have a model, it has to be from the enum of language models
    with pytest.raises(PromptBadLanguageModelTypeError):

        class NewBadLanguageModelPrompt(PromptBase):
            component_type = ComponentTypes.QUESTION_INSTRUCTIONS
            question_type = "free_text"
            model = "poo"


from edsl.prompts.Prompt import Prompt


# Testing __add__ method
def test_prompt_addition():
    p = Prompt("Hello, {{person}}")
    p2 = Prompt("How are you?")
    assert str(p + p2) == "Hello, {{person}}How are you?"
    assert str(p + "How are you?") == "Hello, {{person}}How are you?"


# Testing __str__ method
def test_prompt_str():
    p = Prompt("Hello, {{person}}")
    assert str(p) == "Hello, {{person}}"


# Testing __contains__ method
def test_prompt_contains():
    p = Prompt("Hello, {{person}}")
    assert "person" in p
    assert "person2" not in p


# Testing __repr__ method
def test_prompt_repr():
    p = Prompt("Hello, {{person}}")
    assert repr(p) == "Prompt(text='Hello, {{person}}')"


# Testing template_variables method
def test_prompt_template_variables():
    p = Prompt("Hello, {{person}}")
    assert p.template_variables() == ["person"]


# Testing has_variables property
def test_prompt_has_variables():
    p = Prompt("Hello, {{person}}")
    assert p.has_variables is True
    p = Prompt("Hello, person")
    assert p.has_variables is False


# Testing render method
def test_prompt_render():
    p = Prompt("Hello, {{person}}")
    p.render({"person": "John"})
    assert p.text == "Hello, John"

    p = Prompt("Hello, {{person}}")
    p.render({"person": "Mr. {{last_name}}", "last_name": "Horton"})
    assert p.text == "Hello, Mr. Horton"

    # p = Prompt("Hello, {{person}}")
    # with pytest.raises(
    #     TemplateRenderError
    # ):  # Replace TemplateRenderError with the correct exception
    #     p.render(
    #         {"person": "Mr. {{last_name}}", "last_name": "Ho{{letter}}ton"},
    #         max_nesting=1,
    #     )


# Testing to_dict method
def test_prompt_to_dict():
    p = Prompt("Hello, {{person}}")
    assert p.to_dict() == {"text": "Hello, {{person}}", "class_name": "Prompt"}


# Testing from_dict method
def test_prompt_from_dict():
    p = Prompt("Hello, {{person}}")
    p2 = Prompt.from_dict(p.to_dict())
    assert repr(p2) == "Prompt(text='Hello, {{person}}')"
