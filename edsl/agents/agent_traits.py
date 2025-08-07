"""Agent traits container functionality.

This module provides the AgentTraits class, which is a MutableMapping that
acts as a proxy around trait dictionaries with validation and guard functionality
to prevent modifications when dynamic traits functions are present.
"""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
from collections.abc import MutableMapping

if TYPE_CHECKING:
    from .agent import Agent


class AgentTraits(MutableMapping):
    """A proxy around the real trait dict.

    All writes go through _guard(), which delegates to the parent Agent
    to enforce whatever rules it wants (no dynamic-traits override, etc.).

    This class implements the MutableMapping interface to provide dict-like
    access to agent traits while maintaining validation and consistency.

    Args:
        data: Dictionary of traits data
        parent: The parent Agent instance

    Examples:
        Basic usage with trait access:

        >>> from edsl.agents import Agent
        >>> agent = Agent(traits={'age': 30})
        >>> agent._traits['age']
        30

        Setting and getting traits:

        >>> agent._traits['height'] = 5.5
        >>> agent._traits['height']
        5.5

        Dict-like operations:

        >>> len(agent._traits)
        2
        >>> list(agent._traits)
        ['age', 'height']
    """

    def __init__(self, data: dict, parent: "Agent") -> None:
        """Initialize AgentTraits.

        Args:
            data: Dictionary of traits data
            parent: The parent Agent instance
        """
        from ..scenarios import Scenario
        self._store = Scenario(data)
        self._parent = parent

    # ---- internal helper -------------------------------------------------
    def _guard(self) -> None:
        """Check if trait modifications are allowed.

        Raises:
            AgentErrors: If the parent agent has a dynamic traits function.
        """
        self._parent.traits_manager.check_before_modifying_traits()  # raise if not allowed

    # ---- MutableMapping interface ----------------------------------------
    def __getitem__(self, key: str) -> Any:
        """Get a trait value by key.

        Args:
            key: The trait key to retrieve

        Returns:
            The trait value

        Example:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30})
            >>> agent._traits['age']
            30
        """
        return self._store[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set a trait value by key.

        Args:
            key: The trait key to set
            value: The trait value to set

        Raises:
            AgentErrors: If the parent agent has a dynamic traits function.

        Example:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30})
            >>> agent._traits['height'] = 5.5
            >>> agent._traits['height']
            5.5
        """
        self._guard()
        self._store[key] = value

    def __delitem__(self, key: str) -> None:
        """Delete a trait by key.

        Args:
            key: The trait key to delete

        Raises:
            AgentErrors: If the parent agent has a dynamic traits function.

        Example:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30, 'height': 5.5})
            >>> del agent._traits['height']
            >>> 'height' in agent._traits
            False
        """
        self._guard()
        del self._store[key]

    def __iter__(self):
        """Iterate over trait keys.

        Returns:
            Iterator over trait keys

        Example:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30, 'height': 5.5})
            >>> list(agent._traits)
            ['age', 'height']
        """
        return iter(self._store)

    def __len__(self) -> int:
        """Get the number of traits.

        Returns:
            The number of traits

        Example:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30, 'height': 5.5})
            >>> len(agent._traits)
            2
        """
        return len(self._store)

    # nice repr for debugging
    def __repr__(self) -> str:
        """Return string representation of traits.

        Returns:
            String representation of the traits dictionary

        Example:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30})
            >>> repr(agent._traits)
            "{'age': 30}"
        """
        return dict(self._store).__repr__()

    # allow dict | union syntax to work like normal dicts
    def __or__(self, other):
        """Return a regular dictionary that is the union of this mapping and *other*.

        Mirrors the behaviour of ``dict.__or__`` introduced in Python 3.9 so that
        ``AgentTraits | AgentTraits`` (or ``|`` with any mapping) behaves the
        same as with plain ``dict`` objects.  The result is a **new** *dict*
        (not an ``AgentTraits`` instance) which matches the semantics of the
        built-in type.
        """
        if isinstance(other, MutableMapping):
            return {**dict(self), **dict(other)}
        return NotImplemented

    # support reversed operand order (e.g. ``dict | AgentTraits``)
    def __ror__(self, other):
        if isinstance(other, MutableMapping):
            return {**dict(other), **dict(self)}
        return NotImplemented

    # in-place union ``|=`` – delegates to __setitem__ so guards still fire
    def __ior__(self, other):
        if isinstance(other, MutableMapping):
            for k, v in other.items():
                self[k] = v  # will trigger _guard()
            return self
        return NotImplemented 