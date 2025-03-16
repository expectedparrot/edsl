import enum
from typing import Dict, Optional
from collections import UserList

from ..prompts import Prompt


class PromptComponent(enum.Enum):
    AGENT_INSTRUCTIONS = "agent_instructions"
    AGENT_PERSONA = "agent_persona"
    QUESTION_INSTRUCTIONS = "question_instructions"
    PRIOR_QUESTION_MEMORY = "prior_question_memory"


class PromptList(UserList):
    separator = Prompt("")

    def reduce(self):
        """Reduce the list of prompts to a single prompt.

        >>> p = PromptList([Prompt("You are a happy-go lucky agent."), Prompt("You are an agent with the following persona: {'age': 22, 'hair': 'brown', 'height': 5.5}")])
        >>> p.reduce()
        Prompt(text=\"""You are a happy-go lucky agent.You are an agent with the following persona: {'age': 22, 'hair': 'brown', 'height': 5.5}\""")

        """
        p = self[0]
        for prompt in self[1:]:
            if len(prompt) > 0:
                p = p + self.separator + prompt
        return p


class PromptPlan:
    """A plan for constructing prompts for the LLM call.
    Every prompt plan has a user prompt order and a system prompt order.
    It must contain each of the values in the PromptComponent enum.


    >>> p = PromptPlan(user_prompt_order=(PromptComponent.AGENT_INSTRUCTIONS, PromptComponent.AGENT_PERSONA),system_prompt_order=(PromptComponent.QUESTION_INSTRUCTIONS, PromptComponent.PRIOR_QUESTION_MEMORY))
    >>> p._is_valid_plan()
    True

    >>> p.arrange_components(agent_instructions=1, agent_persona=2, question_instructions=3, prior_question_memory=4)
    {'user_prompt': ..., 'system_prompt': ...}

    >>> p = PromptPlan(user_prompt_order=("agent_instructions", ), system_prompt_order=("question_instructions", "prior_question_memory"))
    Traceback (most recent call last):
    ...
    ValueError: Invalid plan: must contain each value of PromptComponent exactly once.

    """

    def __init__(
        self,
        user_prompt_order: Optional[tuple] = None,
        system_prompt_order: Optional[tuple] = None,
    ):
        """Initialize the PromptPlan."""

        if user_prompt_order is None:
            user_prompt_order = (
                PromptComponent.QUESTION_INSTRUCTIONS,
                PromptComponent.PRIOR_QUESTION_MEMORY,
            )
        if system_prompt_order is None:
            system_prompt_order = (
                PromptComponent.AGENT_INSTRUCTIONS,
                PromptComponent.AGENT_PERSONA,
            )

        # very commmon way to screw this up given how python treats single strings as iterables
        if isinstance(user_prompt_order, str):
            user_prompt_order = (user_prompt_order,)

        if isinstance(system_prompt_order, str):
            system_prompt_order = (system_prompt_order,)

        if not isinstance(user_prompt_order, tuple):
            from edsl.invigilators.exceptions import InvigilatorTypeError
            raise InvigilatorTypeError(
                f"Expected a tuple, but got {type(user_prompt_order).__name__}"
            )

        if not isinstance(system_prompt_order, tuple):
            from edsl.invigilators.exceptions import InvigilatorTypeError
            raise InvigilatorTypeError(
                f"Expected a tuple, but got {type(system_prompt_order).__name__}"
            )

        self.user_prompt_order = self._convert_to_enum(user_prompt_order)
        self.system_prompt_order = self._convert_to_enum(system_prompt_order)
        if not self._is_valid_plan():
            from edsl.invigilators.exceptions import InvigilatorValueError
            raise InvigilatorValueError(
                "Invalid plan: must contain each value of PromptComponent exactly once."
            )

    def _convert_to_enum(self, prompt_order: tuple):
        """Convert string names to PromptComponent enum values."""
        return tuple(
            PromptComponent(component) if isinstance(component, str) else component
            for component in prompt_order
        )

    def _is_valid_plan(self):
        """Check if the plan is valid."""
        combined = self.user_prompt_order + self.system_prompt_order
        return set(combined) == set(PromptComponent)

    def arrange_components(self, **kwargs) -> Dict[PromptComponent, Prompt]:
        """Arrange the components in the order specified by the plan."""
        # check is valid components passed
        component_strings = set([pc.value for pc in PromptComponent])
        if not set(kwargs.keys()) == component_strings:
            from edsl.invigilators.exceptions import InvigilatorValueError
            raise InvigilatorValueError(
                f"Invalid components passed: {set(kwargs.keys())} but expected {PromptComponent}"
            )

        user_prompt = PromptList(
            [kwargs[component.value] for component in self.user_prompt_order]
        )
        system_prompt = PromptList(
            [kwargs[component.value] for component in self.system_prompt_order]
        )
        return {"user_prompt": user_prompt, "system_prompt": system_prompt}

    def get_prompts(self, **kwargs) -> Dict[str, Prompt]:
        """Get both prompts for the LLM call."""
        prompts = self.arrange_components(**kwargs)
        return {
            "user_prompt": Prompt("".join(str(p) for p in prompts["user_prompt"])),
            "system_prompt": Prompt("".join(str(p) for p in prompts["system_prompt"])),
        }
