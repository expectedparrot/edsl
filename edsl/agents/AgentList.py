from __future__ import annotations
import io
from collections import UserList
from typing import Optional, Union

from rich.console import Console
from rich.table import Table

from edsl.agents import Agent
from edsl.agents.AgentListExportMixin import AgentListExportMixin
from edsl.Base import Base


class AgentList(UserList, Base, AgentListExportMixin):
    def __init__(self, data: Optional[list] = None):
        if data is not None:
            super().__init__(data)
        else:
            super().__init__()

    def to(self, question_or_survey: Union["Question", "Survey"]):
        return question_or_survey.by(*self)

    def to_dict(self):
        return {"agent_list": [agent.to_dict() for agent in self.data]}

    @classmethod
    def from_dict(cls, data: dict) -> "AgentList":
        """Deserializes the dictionary back to an Agent List object."""
        agents = [Agent.from_dict(agent_dict) for agent_dict in data["agent_list"]]
        return cls(agents)

    @classmethod
    def example(cls):
        return cls([Agent.example(), Agent.example()])

    def code(self):
        lines = [
            "from edsl.agents.Agent import Agent",
            "from edsl.agents.AgentList import AgentList",
        ]
        lines.append(f"agent_list = AgentList({self.data})")
        return lines

    def rich_print(self):
        """Displays an object as a table."""
        table = Table(title="AgentList")
        table.add_column("Agents", style="bold")
        for agent in self.data:
            table.add_row(agent.rich_print())
        return table


if __name__ == "__main__":
    pass
