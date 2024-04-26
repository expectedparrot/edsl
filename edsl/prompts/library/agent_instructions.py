"""Agent instructions for a human agent."""
import textwrap

from edsl.prompts.Prompt import PromptBase
from edsl.prompts.prompt_config import ComponentTypes

# from edsl.enums import LanguageModelType


class AgentInstruction(PromptBase):
    """Agent instructions for a human agent."""

    # model = LanguageModelType.GPT_3_5_Turbo.value
    # from edsl import Model
    # model = Model().model
    model = "gpt-3.5-turbo"
    component_type = ComponentTypes.AGENT_INSTRUCTIONS
    default_instructions = textwrap.dedent(
        """\
    You are playing the role of a human answering survey questions.
    Do not break character.
    """
    )


# class AgentInstructionLlama(PromptBase):
#     """Agent instructions for a human agent."""

#     model = LanguageModelType.LLAMA_2_70B_CHAT_HF.value
#     component_type = ComponentTypes.AGENT_INSTRUCTIONS
#     default_instructions = textwrap.dedent(
#         """\
#     You are playing the role of a human answering questions.
#     Do not break character.
#     Only respond in JSON, with one answer formatted as specified.
#     """
#     )
