"""A module for lists of agents."""
from __future__ import annotations
from collections import UserList
from typing import Optional, Union

from rich.table import Table

from edsl.agents import Agent
from edsl.agents.AgentListExportMixin import AgentListExportMixin
from edsl.Base import Base


class AgentList(UserList, Base, AgentListExportMixin):
    """A list of Agents.

    This is a list of Agents.
    """

    def __init__(self, data: Optional[list] = None):
        """Initialize a new AgentList."""
        if data is not None:
            super().__init__(data)
        else:
            super().__init__()

    def to(self, question_or_survey: Union["Question", "Survey"]) -> "Jobs":
        """Return a Job with a question or survey taken by the agent."""
        return question_or_survey.by(*self)

    def to_dict(self):
        """Return dictionary of AgentList to serialization."""
        return {"agent_list": [agent.to_dict() for agent in self.data]}

    @classmethod
    def from_dict(cls, data: dict) -> "AgentList":
        """Deserialize the dictionary back to an AgentList object."""
        agents = [Agent.from_dict(agent_dict) for agent_dict in data["agent_list"]]
        return cls(agents)

    @classmethod
    def example(cls):
        """Return an example AgentList."""
        return cls([Agent.example(), Agent.example()])

    def code(self):
        """Return code to construct an AgentList."""
        lines = [
            "from edsl.agents.Agent import Agent",
            "from edsl.agents.AgentList import AgentList",
        ]
        lines.append(f"agent_list = AgentList({self.data})")
        return lines

    def rich_print(self):
        """Display an object as a rich table."""
        table = Table(title="AgentList")
        table.add_column("Agents", style="bold")
        for agent in self.data:
            table.add_row(agent.rich_print())
        return table


if __name__ == "__main__":
    pass
