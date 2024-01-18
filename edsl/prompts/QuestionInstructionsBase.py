from edsl.prompts.Prompt import PromptBase
from edsl.prompts.prompt_config import ComponentTypes


class QuestionInstuctionsBase(PromptBase):
    component_type = ComponentTypes.QUESTION_INSTRUCTIONS
