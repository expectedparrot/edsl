"""A list of Agent objects.

Example usage:

.. code-block:: python

    al = AgentList([Agent.example(), Agent.example()])
    len(al)
    2
    
"""

from __future__ import annotations
from collections import UserList
from typing import Optional, Union
from rich import print_json
from rich.table import Table
import json
import csv

from edsl.Base import Base
from edsl.agents import Agent
from edsl.utilities.decorators import (
    add_edsl_version,
    remove_edsl_version,
)


class AgentList(UserList, Base):
    """A list of Agents."""

    def __init__(self, data: Optional[list[Agent]] = None):
        """Initialize a new AgentList.

        :param data: A list of Agents.
        """
        if data is not None:
            super().__init__(data)
        else:
            super().__init__()

    @classmethod
    def from_csv(cls, file_path: str):
        """Load AgentList from a CSV file.

        >>> import csv
        >>> import os
        >>> with open('/tmp/agents.csv', 'w') as f:
        ...     writer = csv.writer(f)
        ...     _ = writer.writerow(['age', 'hair', 'height'])
        ...     _ = writer.writerow([22, 'brown', 5.5])
        >>> al = AgentList.from_csv('/tmp/agents.csv')
        >>> al
        AgentList([Agent(traits = {'age': '22', 'hair': 'brown', 'height': '5.5'})])
        >>> os.remove('/tmp/agents.csv')

        :param file_path: The path to the CSV file.
        """
        agent_list = []
        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                agent_list.append(Agent(row))
        return cls(agent_list)

    def translate_traits(self, values_codebook: dict[str, str]):
        """Translate traits to a new codebook.

        :param codebook: The new codebook.
        """
        for agent in self.data:
            agent.translate_traits(codebook)
        return self

    def remove_trait(self, trait: str):
        """Remove traits from the AgentList.

        :param traits: The traits to remove.

        >>> al = AgentList([Agent({'age': 22, 'hair': 'brown', 'height': 5.5}), Agent({'age': 22, 'hair': 'brown', 'height': 5.5})])
        >>> al.remove_trait('age')
        AgentList([Agent(traits = {'hair': 'brown', 'height': 5.5}), Agent(traits = {'hair': 'brown', 'height': 5.5})])
        """
        for agent in self.data:
            _ = agent.remove_trait(trait)
        return self

    @staticmethod
    def get_codebook(file_path: str):
        """Return the codebook for a CSV file.

        :param file_path: The path to the CSV file.
        """
        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            return {field: None for field in reader.fieldnames}

    @add_edsl_version
    def to_dict(self):
        """Return dictionary of AgentList to serialization.

        >>> AgentList.example().to_dict()
        {'agent_list': [{'traits': {'age': 22, 'hair': 'brown', 'height': 5.5}, 'edsl_version': '...', 'edsl_class_name': 'Agent'}, {'traits': {'age': 22, 'hair': 'brown', 'height': 5.5}, 'edsl_version': '...', 'edsl_class_name': 'Agent'}], 'edsl_version': '...', 'edsl_class_name': 'AgentList'}
        """
        return {"agent_list": [agent.to_dict() for agent in self.data]}

    def __repr__(self):
        return f"AgentList({self.data})"

    def print(self, format: Optional[str] = None):
        """Print the AgentList."""
        print_json(json.dumps(self.to_dict()))

    def _repr_html_(self):
        """Return an HTML representation of the AgentList."""
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.to_dict()["agent_list"])

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict) -> "AgentList":
        """Deserialize the dictionary back to an AgentList object.

        :param: data: A dictionary representing an AgentList.

        >>> al = AgentList([Agent.example(), Agent.example()])
        >>> al2 = AgentList.from_dict(al.to_dict())
        >>> al2 == al
        True
        """
        agents = [Agent.from_dict(agent_dict) for agent_dict in data["agent_list"]]
        return cls(agents)

    @classmethod
    def example(cls) -> "AgentList":
        """Return an example AgentList.

        >>> al = AgentList.example()
        >>> len(al)
        2

        """
        return cls([Agent.example(), Agent.example()])

    def code(self, string=True) -> Union[str, list[str]]:
        """Return code to construct an AgentList.

        >>> al = AgentList.example()
        >>> print(al.code())
        from edsl.agents.Agent import Agent
        from edsl.agents.AgentList import AgentList
        agent_list = AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5}), Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})])
        """
        lines = [
            "from edsl.agents.Agent import Agent",
            "from edsl.agents.AgentList import AgentList",
        ]
        lines.append(f"agent_list = AgentList({self.data})")
        if string:
            return "\n".join(lines)
        return lines

    def rich_print(self) -> Table:
        """Display an object as a rich table."""
        table = Table(title="AgentList")
        table.add_column("Agents", style="bold")
        for agent in self.data:
            table.add_row(agent.rich_print())
        return table


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
