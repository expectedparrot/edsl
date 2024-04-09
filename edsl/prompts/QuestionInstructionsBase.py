"""Class for creating question instructions to be used in a survey."""
from edsl.prompts.Prompt import PromptBase
from edsl.prompts.prompt_config import ComponentTypes


class QuestionInstuctionsBase(PromptBase):
    """Class for creating question instructions to be used in a survey."""

    component_type = ComponentTypes.QUESTION_INSTRUCTIONS
