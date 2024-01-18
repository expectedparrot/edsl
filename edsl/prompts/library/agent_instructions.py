import textwrap

from edsl.prompts.Prompt import PromptBase
from edsl.prompts.prompt_config import ComponentTypes


class AgentInstruction(PromptBase):
    model = "gpt-3.5-turbo"
    component_type = ComponentTypes.AGENT_INSTRUCTIONS
    default_instructions = textwrap.dedent(
        """\
    You are playing the role of a human answering survey questions.
    Do not break character.
    Your traits are: {{traits}}
    """
    )
