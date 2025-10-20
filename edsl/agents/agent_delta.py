"""AgentDelta class for representing trait updates to agents.

This module provides the AgentDelta class, which represents a set of trait updates
that can be applied to an Agent to create a new agent with modified trait values.
AgentDeltas are typically generated through comparison analysis between two agents'
responses and can be used to systematically update agent personas.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, Optional

from ..base import Base
from ..utilities import dict_hash, remove_edsl_version

if TYPE_CHECKING:
    from .agent import Agent


class AgentDelta(Base):
    """Represents a set of trait updates that can be applied to an Agent.

    An AgentDelta is essentially a dictionary mapping trait names to new values.
    It can be created manually or generated automatically through comparison analysis
    of two agents' responses. The delta can then be applied to an agent to create
    a new agent with updated traits.

    Key features:
    - Dictionary-like interface for easy manipulation
    - Serializable for storage and retrieval
    - Composable through merging multiple deltas
    - Immutable operations (returns new instances)

    Examples:
        Create a delta manually:

        >>> from edsl.agents import AgentDelta
        >>> delta = AgentDelta({'age': 35, 'occupation': 'manager'})
        >>> delta.traits
        {'age': 35, 'occupation': 'manager'}

        Apply a delta to an agent:

        >>> from edsl import Agent
        >>> agent = Agent(traits={'age': 30, 'occupation': 'teacher', 'city': 'Boston'})
        >>> updated_agent = delta.apply(agent)
        >>> updated_agent.traits
        {'age': 35, 'occupation': 'manager', 'city': 'Boston'}

        Merge multiple deltas:

        >>> delta1 = AgentDelta({'age': 35})
        >>> delta2 = AgentDelta({'occupation': 'manager'})
        >>> merged = delta1.merge(delta2)
        >>> merged.traits
        {'age': 35, 'occupation': 'manager'}

        Add or remove trait updates:

        >>> delta = AgentDelta({'age': 30})
        >>> delta_with_more = delta.add_update('occupation', 'teacher')
        >>> delta_with_more.traits
        {'age': 30, 'occupation': 'teacher'}
        >>> delta_less = delta_with_more.remove_update('age')
        >>> delta_less.traits
        {'occupation': 'teacher'}
    """

    def __init__(self, traits: Optional[Dict[str, Any]] = None):
        """Initialize an AgentDelta with trait updates.

        Args:
            traits: Dictionary mapping trait names to new values. If None,
                   creates an empty delta.
        """
        self.traits = traits or {}

    def apply(self, agent: "Agent") -> "Agent":
        """Apply this delta to an agent to create a new agent with updated traits.

        This method creates a new agent by updating the specified traits while
        preserving all other agent properties (name, codebook, instruction, etc.).
        Only traits that exist in the agent will be updated; attempting to update
        a non-existent trait will raise an error.

        Args:
            agent: The agent to apply the delta to

        Returns:
            A new Agent instance with the updated trait values

        Raises:
            AgentErrors: If any trait in the delta doesn't exist in the agent

        Examples:
            >>> from edsl import Agent
            >>> from edsl.agents import AgentDelta
            >>> agent = Agent(traits={'age': 30, 'height': 5.5})
            >>> delta = AgentDelta({'age': 31})
            >>> updated = delta.apply(agent)
            >>> updated.traits
            {'age': 31, 'height': 5.5}

            Error when trait doesn't exist:

            >>> bad_delta = AgentDelta({'weight': 150})
            >>> bad_delta.apply(agent)  # doctest: +ELLIPSIS
            Traceback (most recent call last):
            ...
            edsl.agents.exceptions.AgentErrors: ...
        """
        from .exceptions import AgentErrors

        # Check that all traits in the delta exist in the agent
        missing_traits = set(self.traits.keys()) - set(agent.traits.keys())
        if missing_traits:
            raise AgentErrors(
                f"Cannot apply delta: traits {sorted(missing_traits)} do not exist in agent. "
                f"Agent has traits: {sorted(agent.traits.keys())}"
            )

        # Create a new agent with updated traits
        new_agent = agent.duplicate()
        for trait_name, new_value in self.traits.items():
            new_agent = new_agent.update_trait(trait_name, new_value)

        return new_agent

    def merge(self, other: "AgentDelta") -> "AgentDelta":
        """Merge this delta with another delta.

        When traits overlap, the other delta's values take precedence.

        Args:
            other: Another AgentDelta to merge with

        Returns:
            A new AgentDelta with the merged trait updates

        Examples:
            >>> delta1 = AgentDelta({'age': 35, 'risk_tolerance': 'medium'})
            >>> delta2 = AgentDelta({'occupation': 'manager', 'risk_tolerance': 'high'})
            >>> merged = delta1.merge(delta2)
            >>> merged.traits
            {'age': 35, 'risk_tolerance': 'high', 'occupation': 'manager'}
        """
        merged_traits = {**self.traits, **other.traits}
        return AgentDelta(merged_traits)

    def add_update(self, trait_name: str, value: Any) -> "AgentDelta":
        """Add a trait update to this delta.

        Args:
            trait_name: The name of the trait to update
            value: The new value for the trait

        Returns:
            A new AgentDelta with the added trait update

        Examples:
            >>> delta = AgentDelta({'age': 30})
            >>> new_delta = delta.add_update('occupation', 'teacher')
            >>> new_delta.traits
            {'age': 30, 'occupation': 'teacher'}
        """
        new_traits = {**self.traits, trait_name: value}
        return AgentDelta(new_traits)

    def remove_update(self, trait_name: str) -> "AgentDelta":
        """Remove a trait update from this delta.

        Args:
            trait_name: The name of the trait to remove

        Returns:
            A new AgentDelta without the specified trait update

        Examples:
            >>> delta = AgentDelta({'age': 30, 'occupation': 'teacher'})
            >>> smaller = delta.remove_update('occupation')
            >>> smaller.traits
            {'age': 30}
        """
        new_traits = {k: v for k, v in self.traits.items() if k != trait_name}
        return AgentDelta(new_traits)

    def items(self):
        """Return an iterator over (trait_name, value) pairs.

        This allows treating the delta like a dictionary.

        Returns:
            An iterator over trait name and value pairs

        Examples:
            >>> delta = AgentDelta({'age': 30, 'occupation': 'teacher'})
            >>> sorted(delta.items())
            [('age', 30), ('occupation', 'teacher')]
        """
        return self.traits.items()

    def keys(self):
        """Return an iterator over trait names in this delta.

        Returns:
            An iterator over trait names

        Examples:
            >>> delta = AgentDelta({'age': 30, 'occupation': 'teacher'})
            >>> sorted(delta.keys())
            ['age', 'occupation']
        """
        return self.traits.keys()

    def values(self):
        """Return an iterator over trait values in this delta.

        Returns:
            An iterator over trait values

        Examples:
            >>> delta = AgentDelta({'age': 30, 'occupation': 'teacher'})
            >>> list(delta.values())  # doctest: +SKIP
            [30, 'teacher']
        """
        return self.traits.values()

    def __getitem__(self, key: str) -> Any:
        """Get a trait value by name.

        Args:
            key: The trait name

        Returns:
            The trait value

        Examples:
            >>> delta = AgentDelta({'age': 30})
            >>> delta['age']
            30
        """
        return self.traits[key]

    def __len__(self) -> int:
        """Return the number of trait updates in this delta.

        Returns:
            The number of trait updates

        Examples:
            >>> delta = AgentDelta({'age': 30, 'occupation': 'teacher'})
            >>> len(delta)
            2
        """
        return len(self.traits)

    def __repr__(self) -> str:
        """Return a string representation of this delta.

        Returns:
            A string representation

        Examples:
            >>> delta = AgentDelta({'age': 30})
            >>> repr(delta)
            "AgentDelta({'age': 30})"
        """
        return f"AgentDelta({self.traits!r})"

    def __eq__(self, other: object) -> bool:
        """Check if this delta equals another delta.

        Args:
            other: Another object to compare with

        Returns:
            True if the deltas have the same trait updates

        Examples:
            >>> delta1 = AgentDelta({'age': 30})
            >>> delta2 = AgentDelta({'age': 30})
            >>> delta1 == delta2
            True
            >>> delta3 = AgentDelta({'age': 31})
            >>> delta1 == delta3
            False
        """
        if not isinstance(other, AgentDelta):
            return False
        return self.traits == other.traits

    def __hash__(self) -> int:
        """Return a hash of this delta.

        Returns:
            A hash value

        Examples:
            >>> delta = AgentDelta({'age': 30})
            >>> isinstance(hash(delta), int)
            True
        """
        return dict_hash(self.to_dict(add_edsl_version=False))

    def to_dict(self, add_edsl_version: bool = True) -> Dict[str, Any]:
        """Serialize this delta to a dictionary.

        Args:
            add_edsl_version: Whether to include EDSL version information

        Returns:
            A dictionary representation of this delta

        Examples:
            >>> delta = AgentDelta({'age': 30, 'occupation': 'teacher'})
            >>> d = delta.to_dict(add_edsl_version=False)
            >>> d['traits']
            {'age': 30, 'occupation': 'teacher'}
            >>> d['edsl_class_name']
            'AgentDelta'
        """
        d = {
            "traits": self.traits,
            "edsl_class_name": "AgentDelta",
        }

        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__

        return d

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: Dict[str, Any]) -> "AgentDelta":
        """Deserialize an AgentDelta from a dictionary.

        Args:
            data: A dictionary representation of an AgentDelta

        Returns:
            An AgentDelta instance

        Examples:
            >>> data = {'traits': {'age': 30, 'occupation': 'teacher'}}
            >>> delta = AgentDelta.from_dict(data)
            >>> delta.traits
            {'age': 30, 'occupation': 'teacher'}
        """
        return cls(traits=data.get("traits", {}))

    def code(self) -> str:
        """Return Python code to recreate this AgentDelta.

        Returns:
            Python code string to recreate this delta

        Examples:
            >>> delta = AgentDelta({'age': 35, 'occupation': 'manager'})
            >>> print(delta.code())  # doctest: +NORMALIZE_WHITESPACE
            from edsl.agents import AgentDelta
            agent_delta = AgentDelta({'age': 35, 'occupation': 'manager'})
        """
        return f"from edsl.agents import AgentDelta\nagent_delta = AgentDelta({self.traits!r})"

    @classmethod
    def example(cls) -> "AgentDelta":
        """Return an example AgentDelta instance.

        Returns:
            An example AgentDelta

        Examples:
            >>> delta = AgentDelta.example()
            >>> 'age' in delta.traits
            True
        """
        return cls(
            traits={"age": 35, "occupation": "manager", "risk_tolerance": "medium"}
        )

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the AgentDelta.

        Returns:
            str: A string that can be evaluated to recreate the AgentDelta
        """
        return f"AgentDelta({self.traits!r})"

    def _summary_repr(self) -> str:
        """Generate a summary representation of the AgentDelta with Rich formatting.

        Returns:
            str: A formatted summary representation of the AgentDelta
        """
        from rich.console import Console
        from rich.text import Text
        import io

        output = Text()
        output.append("AgentDelta(", style="bold cyan")

        if self.traits:
            output.append("traits=", style="white")
            traits_str = ", ".join(
                f"{k}={v!r}" for k, v in list(self.traits.items())[:3]
            )
            if len(self.traits) > 3:
                traits_str += f", ... ({len(self.traits) - 3} more)"
            output.append(f"{{{traits_str}}}", style="yellow")
        else:
            output.append("empty", style="dim")

        output.append(")", style="bold cyan")

        console = Console(file=io.StringIO(), force_terminal=True, width=120)
        console.print(output, end="")
        return console.file.getvalue()


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
