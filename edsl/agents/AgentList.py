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
        with io.StringIO() as buf:
            console = Console(file=buf, record=True)
            for agent in self.data:
                console.print(agent.rich_print())
            # table = Table(title="Agent Attributes")
            # table.add_column("Attribute", style="bold")
            # table.add_column("Value")

            # for attr_name, attr_value in self.__dict__.items():
            #     table.add_row(attr_name, str(attr_value))

            #            console.print(table)
            return console.export_text()

    def __str__(self):
        return self.rich_print()


if __name__ == "__main__":
    pass
