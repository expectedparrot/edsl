import pytest
import doctest
import edsl.prompts


def test_doctests_in_prompt():
    doctest.testmod(edsl.prompts)


from edsl.prompts.Prompt import PromptBase
from edsl.prompts.prompt_config import ComponentTypes

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
