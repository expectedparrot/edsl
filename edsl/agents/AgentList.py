from __future__ import annotations
from collections import UserList
from typing import Optional, Union
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

    def update_traits(self, new_attributes: list):
        for agent in self.data:
            agent.update_traits(new_attributes)

    def print(self, html=False):
        html = ""
        for agent in self.data:
            html += agent.dict_to_html()
        from edsl.utilities.interface import gen_html_sandwich
        from edsl.utilities.interface import view_html

        view_html(gen_html_sandwich(html))

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


if __name__ == "__main__":
    a = AgentList([1, 2, 3])
    print(a)

    from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
    from edsl.agents.Agent import Agent

    q = QuestionMultipleChoice(
        question_text="How are you feeling?",
        question_options=["Very sad.", "Sad.", "Neutral.", "Happy.", "Very happy."],
        question_name="feelings",
    )

    a = Agent(traits={"feeling": "Very sad."})
    agent_list = AgentList([a])
    results = agent_list.to(q).run()

    print(results)

    results2 = q.by(agent_list).run()

    print(results2)
