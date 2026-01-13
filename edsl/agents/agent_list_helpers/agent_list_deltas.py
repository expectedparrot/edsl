"""AgentListDeltas class for managing multiple agent trait updates.

This module provides the AgentListDeltas class, which manages multiple AgentDeltas
indexed by agent name. This allows for batch updates to an entire AgentList,
where each agent gets its own set of trait updates.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, Optional

from edsl.base import Base
from edsl.utilities import dict_hash, remove_edsl_version

if TYPE_CHECKING:
    from ..agent_list import AgentList
    from ..agent_helpers.agent_delta import AgentDelta


class AgentListDeltas(Base):
    """Manages multiple AgentDeltas indexed by agent name.

    An AgentListDeltas object maps agent names to their corresponding AgentDeltas,
    enabling batch updates to an AgentList. All agent names in the deltas must
    match the names in the target AgentList for successful application.

    Key features:
    - Dictionary-like interface mapping agent names to AgentDeltas
    - Batch application to AgentLists
    - Serializable for storage and retrieval
    - Name validation to prevent mismatches

    Examples:
        Create deltas for multiple agents:

        >>> from edsl import Agent, AgentList
        >>> from edsl.agents import AgentDelta, AgentListDeltas
        >>> agents = AgentList([
        ...     Agent(name='Alice', traits={'age': 30, 'score': 85}),
        ...     Agent(name='Bob', traits={'age': 25, 'score': 90})
        ... ])
        >>> deltas = AgentListDeltas({
        ...     'Alice': AgentDelta({'age': 31, 'score': 88}),
        ...     'Bob': AgentDelta({'age': 26, 'score': 92})
        ... })
        >>> updated_list = deltas.apply(agents)
        >>> [agent.traits['age'] for agent in updated_list]
        [31, 26]
        >>> [agent.traits['score'] for agent in updated_list]
        [88, 92]

        Error when names don't match:

        >>> bad_deltas = AgentListDeltas({'Charlie': AgentDelta({'age': 40})})
        >>> bad_deltas.apply(agents)  # doctest: +ELLIPSIS
        Traceback (most recent call last):
        ...
        edsl.agents.exceptions.AgentListError: ...
    """

    def __init__(self, deltas: Optional[Dict[str, "AgentDelta"]] = None):
        """Initialize an AgentListDeltas with a mapping of agent names to deltas.

        Args:
            deltas: Dictionary mapping agent names to AgentDelta objects.
                   If None, creates an empty mapping.
        """
        self.deltas = deltas or {}

    def apply(self, agent_list: "AgentList") -> "AgentList":
        """Apply all deltas to an AgentList to create a new list with updated agents.

        This method matches each delta to its corresponding agent by name and
        applies the updates. All agent names in the deltas must exist in the
        agent list, and all agents in the list must have names.

        Args:
            agent_list: The AgentList to apply the deltas to

        Returns:
            A new AgentList with updated agents

        Raises:
            AgentListError: If agent names don't match or agents lack names

        Examples:
            >>> from edsl import Agent, AgentList
            >>> from edsl.agents import AgentDelta, AgentListDeltas
            >>> agents = AgentList([
            ...     Agent(name='Alice', traits={'age': 30}),
            ...     Agent(name='Bob', traits={'age': 25})
            ... ])
            >>> deltas = AgentListDeltas({
            ...     'Alice': AgentDelta({'age': 31}),
            ...     'Bob': AgentDelta({'age': 26})
            ... })
            >>> updated = deltas.apply(agents)
            >>> updated[0].traits['age']
            31
            >>> updated[1].traits['age']
            26
        """
        from ..exceptions import AgentListError

        # Collect agent names from the list
        agent_names = set()
        for agent in agent_list:
            if agent.name is None:
                raise AgentListError(
                    "Cannot apply deltas to an AgentList with unnamed agents. "
                    "All agents must have names."
                )
            agent_names.add(agent.name)

        delta_names = set(self.deltas.keys())

        # Check for name mismatches
        if delta_names != agent_names:
            missing_in_deltas = agent_names - delta_names
            missing_in_agents = delta_names - agent_names
            error_parts = ["Agent names in deltas do not match agent names in list."]
            if missing_in_deltas:
                error_parts.append(
                    f"Agents without deltas: {sorted(missing_in_deltas)}"
                )
            if missing_in_agents:
                error_parts.append(
                    f"Deltas without matching agents: {sorted(missing_in_agents)}"
                )
            raise AgentListError(" ".join(error_parts))

        # Apply deltas to each agent
        from ..agent_list import AgentList

        updated_agents = []
        for agent in agent_list:
            delta = self.deltas[agent.name]
            updated_agent = delta.apply(agent)
            updated_agents.append(updated_agent)

        return AgentList(updated_agents)

    def add_delta(self, agent_name: str, delta: "AgentDelta") -> "AgentListDeltas":
        """Add a delta for a specific agent.

        Args:
            agent_name: The name of the agent
            delta: The AgentDelta to add

        Returns:
            A new AgentListDeltas with the added delta

        Examples:
            >>> from edsl.agents import AgentDelta, AgentListDeltas
            >>> deltas = AgentListDeltas()
            >>> new_deltas = deltas.add_delta('Alice', AgentDelta({'age': 31}))
            >>> 'Alice' in new_deltas.deltas
            True
        """
        new_deltas = {**self.deltas, agent_name: delta}
        return AgentListDeltas(new_deltas)

    def remove_delta(self, agent_name: str) -> "AgentListDeltas":
        """Remove a delta for a specific agent.

        Args:
            agent_name: The name of the agent

        Returns:
            A new AgentListDeltas without the specified delta

        Examples:
            >>> from edsl.agents import AgentDelta, AgentListDeltas
            >>> deltas = AgentListDeltas({'Alice': AgentDelta({'age': 31})})
            >>> new_deltas = deltas.remove_delta('Alice')
            >>> 'Alice' in new_deltas.deltas
            False
        """
        new_deltas = {k: v for k, v in self.deltas.items() if k != agent_name}
        return AgentListDeltas(new_deltas)

    def __getitem__(self, agent_name: str) -> "AgentDelta":
        """Get the delta for a specific agent.

        Args:
            agent_name: The name of the agent

        Returns:
            The AgentDelta for that agent

        Examples:
            >>> from edsl.agents import AgentDelta, AgentListDeltas
            >>> deltas = AgentListDeltas({'Alice': AgentDelta({'age': 31})})
            >>> deltas['Alice'].traits
            {'age': 31}
        """
        return self.deltas[agent_name]

    def __len__(self) -> int:
        """Return the number of agent deltas.

        Returns:
            The number of agent deltas

        Examples:
            >>> from edsl.agents import AgentDelta, AgentListDeltas
            >>> deltas = AgentListDeltas({
            ...     'Alice': AgentDelta({'age': 31}),
            ...     'Bob': AgentDelta({'age': 26})
            ... })
            >>> len(deltas)
            2
        """
        return len(self.deltas)

    def keys(self):
        """Return an iterator over agent names.

        Returns:
            An iterator over agent names

        Examples:
            >>> from edsl.agents import AgentDelta, AgentListDeltas
            >>> deltas = AgentListDeltas({
            ...     'Alice': AgentDelta({'age': 31}),
            ...     'Bob': AgentDelta({'age': 26})
            ... })
            >>> sorted(deltas.keys())
            ['Alice', 'Bob']
        """
        return self.deltas.keys()

    def values(self):
        """Return an iterator over AgentDeltas.

        Returns:
            An iterator over AgentDeltas

        Examples:
            >>> from edsl.agents import AgentDelta, AgentListDeltas
            >>> deltas = AgentListDeltas({'Alice': AgentDelta({'age': 31})})
            >>> list(deltas.values())  # doctest: +SKIP
            [AgentDelta({'age': 31})]
        """
        return self.deltas.values()

    def items(self):
        """Return an iterator over (agent_name, delta) pairs.

        Returns:
            An iterator over agent name and delta pairs

        Examples:
            >>> from edsl.agents import AgentDelta, AgentListDeltas
            >>> deltas = AgentListDeltas({'Alice': AgentDelta({'age': 31})})
            >>> list(deltas.items())  # doctest: +SKIP
            [('Alice', AgentDelta({'age': 31}))]
        """
        return self.deltas.items()

    def __repr__(self) -> str:
        """Return a string representation of this AgentListDeltas.

        Returns:
            A string representation

        Examples:
            >>> from edsl.agents import AgentDelta, AgentListDeltas
            >>> deltas = AgentListDeltas({'Alice': AgentDelta({'age': 31})})
            >>> repr(deltas)  # doctest: +SKIP
            "AgentListDeltas({'Alice': AgentDelta({'age': 31})})"
        """
        return f"AgentListDeltas({self.deltas!r})"

    def __eq__(self, other: object) -> bool:
        """Check if this AgentListDeltas equals another.

        Args:
            other: Another object to compare with

        Returns:
            True if the deltas are the same

        Examples:
            >>> from edsl.agents import AgentDelta, AgentListDeltas
            >>> deltas1 = AgentListDeltas({'Alice': AgentDelta({'age': 31})})
            >>> deltas2 = AgentListDeltas({'Alice': AgentDelta({'age': 31})})
            >>> deltas1 == deltas2
            True
        """
        if not isinstance(other, AgentListDeltas):
            return False
        return self.deltas == other.deltas

    def __hash__(self) -> int:
        """Return a hash of this AgentListDeltas.

        Returns:
            A hash value

        Examples:
            >>> from edsl.agents import AgentDelta, AgentListDeltas
            >>> deltas = AgentListDeltas({'Alice': AgentDelta({'age': 31})})
            >>> isinstance(hash(deltas), int)
            True
        """
        return dict_hash(self.to_dict(add_edsl_version=False))

    def to_dict(self, add_edsl_version: bool = True) -> Dict[str, Any]:
        """Serialize this AgentListDeltas to a dictionary.

        Args:
            add_edsl_version: Whether to include EDSL version information

        Returns:
            A dictionary representation

        Examples:
            >>> from edsl.agents import AgentDelta, AgentListDeltas
            >>> deltas = AgentListDeltas({'Alice': AgentDelta({'age': 31})})
            >>> d = deltas.to_dict(add_edsl_version=False)
            >>> 'deltas' in d
            True
            >>> d['edsl_class_name']
            'AgentListDeltas'
        """
        # Serialize each delta
        serialized_deltas = {
            agent_name: delta.to_dict(add_edsl_version=False)
            for agent_name, delta in self.deltas.items()
        }

        d = {
            "deltas": serialized_deltas,
            "edsl_class_name": "AgentListDeltas",
        }

        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__

        return d

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: Dict[str, Any]) -> "AgentListDeltas":
        """Deserialize an AgentListDeltas from a dictionary.

        Args:
            data: A dictionary representation of an AgentListDeltas

        Returns:
            An AgentListDeltas instance

        Examples:
            >>> from edsl.agents import AgentDelta, AgentListDeltas
            >>> data = {
            ...     'deltas': {
            ...         'Alice': {'traits': {'age': 31}, 'edsl_class_name': 'AgentDelta'}
            ...     }
            ... }
            >>> deltas = AgentListDeltas.from_dict(data)
            >>> 'Alice' in deltas.deltas
            True
        """
        from ..agent_helpers.agent_delta import AgentDelta

        # Deserialize each delta
        deserialized_deltas = {}
        for agent_name, delta_dict in data.get("deltas", {}).items():
            deserialized_deltas[agent_name] = AgentDelta.from_dict(delta_dict)

        return cls(deltas=deserialized_deltas)

    def code(self) -> str:
        """Return Python code to recreate this AgentListDeltas.

        Returns:
            Python code string to recreate this object

        Examples:
            >>> from edsl.agents import AgentDelta, AgentListDeltas
            >>> deltas = AgentListDeltas({'Alice': AgentDelta({'age': 31})})
            >>> code = deltas.code()
            >>> 'from edsl.agents import AgentDelta, AgentListDeltas' in code
            True
        """
        lines = ["from edsl.agents import AgentDelta, AgentListDeltas"]
        delta_lines = []
        for agent_name, delta in self.deltas.items():
            delta_lines.append(f"    {agent_name!r}: AgentDelta({delta.traits!r})")
        deltas_str = "{\n" + ",\n".join(delta_lines) + "\n}"
        lines.append(f"agent_list_deltas = AgentListDeltas({deltas_str})")
        return "\n".join(lines)

    @classmethod
    def example(cls) -> "AgentListDeltas":
        """Return an example AgentListDeltas instance.

        Returns:
            An example AgentListDeltas

        Examples:
            >>> deltas = AgentListDeltas.example()
            >>> 'Alice' in deltas.deltas
            True
            >>> 'Bob' in deltas.deltas
            True
        """
        from ..agent_helpers.agent_delta import AgentDelta

        return cls(
            deltas={
                "Alice": AgentDelta({"age": 31, "score": 88}),
                "Bob": AgentDelta({"age": 26, "score": 92}),
            }
        )

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the AgentListDeltas.

        Returns:
            str: A string that can be evaluated to recreate the AgentListDeltas
        """
        return f"AgentListDeltas({self.deltas!r})"

    def _summary_repr(self) -> str:
        """Generate a summary representation of the AgentListDeltas with Rich formatting.

        Returns:
            str: A formatted summary representation of the AgentListDeltas
        """
        from rich.console import Console
        from rich.text import Text
        import io
        from edsl.config import RICH_STYLES

        output = Text()
        output.append("AgentListDeltas(", style=RICH_STYLES["primary"])
        output.append(f"num_agents={len(self.deltas)}", style=RICH_STYLES["default"])

        if self.deltas:
            output.append(", ", style=RICH_STYLES["default"])
            agents_str = ", ".join(list(self.deltas.keys())[:3])
            if len(self.deltas) > 3:
                agents_str += f", ... ({len(self.deltas) - 3} more)"
            output.append(f"agents=[{agents_str}]", style=RICH_STYLES["secondary"])

        output.append(")", style=RICH_STYLES["primary"])

        console = Console(file=io.StringIO(), force_terminal=True, width=120)
        console.print(output, end="")
        return console.file.getvalue()


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
