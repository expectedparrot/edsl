import enum
from typing import Dict, Optional, TYPE_CHECKING
from collections import UserList

if TYPE_CHECKING:
    from ..prompts import Prompt


class PromptComponent(enum.Enum):
    AGENT_INSTRUCTIONS = "agent_instructions"
    AGENT_PERSONA = "agent_persona"
    QUESTION_INSTRUCTIONS = "question_instructions"
    PRIOR_QUESTION_MEMORY = "prior_question_memory"


class PromptList(UserList):
    from ..prompts import Prompt

    separator = Prompt("")

    def reduce(self):
        """Reduce the list of prompts to a single prompt.

        >>> from edsl.prompts import Prompt
        >>> p = PromptList([Prompt("You are a happy-go lucky agent."), Prompt("You are an agent with the following persona: {'age': 22, 'hair': 'brown', 'height': 5.5}")])
        >>> p.reduce()
        Prompt(text=\"""You are a happy-go lucky agent.You are an agent with the following persona: {'age': 22, 'hair': 'brown', 'height': 5.5}\""")

        >>> PromptList([]).reduce()
        Prompt(text=\"""\""")

        """
        if len(self) == 0:
            return self.Prompt("")
        p = self[0]
        for prompt in self[1:]:
            if len(prompt) > 0:
                p = p + self.separator + prompt
        return p


class PromptPlan:
    """A plan for how prompt components are distributed between system and user prompts.

    Every LLM call in EDSL has four prompt components (see :class:`PromptComponent`):

    - **agent_instructions**: Directives for how the agent should behave.
    - **agent_persona**: The agent's traits (age, occupation, etc.).
    - **question_instructions**: The question text and response format instructions.
    - **prior_question_memory**: Context from previous questions in a survey.

    A ``PromptPlan`` specifies which of these components go into the system prompt
    and which go into the user prompt. Every component must appear in exactly one
    of the two prompts.

    By default, agent-related components go in the system prompt and
    question-related components go in the user prompt. For models that don't
    support system prompts (e.g., reasoning models like o1/o3, or smaller models
    like Gemma), use :meth:`user_prompt_only` to put everything in the user prompt.

    A ``PromptPlan`` can be passed to a ``Model`` via the ``prompt_plan`` parameter::

        from edsl import Model
        from edsl.invigilators.prompt_helpers import PromptPlan

        # All prompt components in the user prompt (no system prompt)
        m = Model("gpt-4o", prompt_plan=PromptPlan.user_prompt_only())

        # Default behavior (same as omitting prompt_plan)
        m = Model("gpt-4o", prompt_plan=PromptPlan.default())

    The plan is serialized with the model, so it persists through
    ``to_dict()`` / ``from_dict()`` roundtrips.

    Examples:

    >>> p = PromptPlan(user_prompt_order=(PromptComponent.AGENT_INSTRUCTIONS, PromptComponent.AGENT_PERSONA),system_prompt_order=(PromptComponent.QUESTION_INSTRUCTIONS, PromptComponent.PRIOR_QUESTION_MEMORY))
    >>> p._is_valid_plan()
    True

    >>> p.arrange_components(agent_instructions=1, agent_persona=2, question_instructions=3, prior_question_memory=4)
    {'user_prompt': ..., 'system_prompt': ...}

    >>> p = PromptPlan(user_prompt_order=("agent_instructions", ), system_prompt_order=("question_instructions", "prior_question_memory"))  # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    edsl.invigilators.exceptions.InvigilatorValueError: Invalid plan: must contain each value of PromptComponent exactly once.
    ...

    """

    def __init__(
        self,
        user_prompt_order: Optional[tuple] = None,
        system_prompt_order: Optional[tuple] = None,
    ):
        """Initialize the PromptPlan.

        Args:
            user_prompt_order: Tuple of :class:`PromptComponent` values (or their
                string names) specifying which components appear in the user prompt
                and in what order. Defaults to ``(QUESTION_INSTRUCTIONS, PRIOR_QUESTION_MEMORY)``.
            system_prompt_order: Tuple of :class:`PromptComponent` values (or their
                string names) specifying which components appear in the system prompt
                and in what order. Defaults to ``(AGENT_INSTRUCTIONS, AGENT_PERSONA)``.

        Raises:
            InvigilatorValueError: If the combined tuples don't contain each
                PromptComponent exactly once.
            InvigilatorTypeError: If either argument is not a tuple.
        """

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

    def arrange_components(self, **kwargs) -> Dict[PromptComponent, "Prompt"]:
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

    @classmethod
    def default(cls) -> "PromptPlan":
        """Create the default prompt plan.

        System prompt gets agent instructions and persona;
        user prompt gets question instructions and prior memory.

        This is equivalent to calling ``PromptPlan()`` with no arguments, and
        matches the behavior when no ``prompt_plan`` is specified on a ``Model``.

        Returns:
            A PromptPlan with the default component arrangement.

        Example:

        >>> pp = PromptPlan.default()
        >>> pp.system_prompt_order
        (<PromptComponent.AGENT_INSTRUCTIONS: 'agent_instructions'>, <PromptComponent.AGENT_PERSONA: 'agent_persona'>)
        """
        return cls()

    @classmethod
    def user_prompt_only(cls) -> "PromptPlan":
        """Create a prompt plan that puts all components in the user prompt.

        The system prompt will be empty. This is useful for models that don't
        support system prompts, such as:

        - OpenAI reasoning models (o1, o3)
        - Small/local models (Gemma, Phi, etc.)
        - Any model where you want full control over a single prompt

        Returns:
            A PromptPlan with all four components in the user prompt.

        Example:

        >>> pp = PromptPlan.user_prompt_only()
        >>> pp.system_prompt_order
        ()
        >>> len(pp.user_prompt_order)
        4
        """
        return cls(
            user_prompt_order=(
                PromptComponent.AGENT_INSTRUCTIONS,
                PromptComponent.AGENT_PERSONA,
                PromptComponent.QUESTION_INSTRUCTIONS,
                PromptComponent.PRIOR_QUESTION_MEMORY,
            ),
            system_prompt_order=(),
        )

    def to_dict(self) -> dict:
        """Serialize the prompt plan to a dictionary."""
        return {
            "user_prompt_order": [c.value for c in self.user_prompt_order],
            "system_prompt_order": [c.value for c in self.system_prompt_order],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PromptPlan":
        """Create a PromptPlan from a dictionary."""
        return cls(
            user_prompt_order=tuple(data["user_prompt_order"]),
            system_prompt_order=tuple(data["system_prompt_order"]),
        )

    def __eq__(self, other):
        if not isinstance(other, PromptPlan):
            return NotImplemented
        return (
            self.user_prompt_order == other.user_prompt_order
            and self.system_prompt_order == other.system_prompt_order
        )

    def __repr__(self):
        return (
            f"PromptPlan(user_prompt_order={self.user_prompt_order}, "
            f"system_prompt_order={self.system_prompt_order})"
        )

    def get_prompts(self, **kwargs) -> Dict[str, "Prompt"]:
        """Get both prompts for the LLM call."""
        from ..prompts import Prompt

        prompts = self.arrange_components(**kwargs)
        result = {
            "user_prompt": Prompt("".join(str(p) for p in prompts["user_prompt"])),
            "system_prompt": Prompt("".join(str(p) for p in prompts["system_prompt"])),
        }
        return result
