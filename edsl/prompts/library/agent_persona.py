import textwrap

from edsl.prompts.Prompt import PromptBase
from edsl.prompts.prompt_config import ComponentTypes

from edsl.enums import LanguageModelType


class AgentPersona(PromptBase):
    model = "gpt-4-1106-preview"
    component_type = ComponentTypes.AGENT_PERSONA
    default_instructions = textwrap.dedent(
        """\
            You are an agent with the following persona:
            {{ traits }}
        """
    )
