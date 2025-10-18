from __future__ import annotations

from typing import Any, Optional

from ..scenarios import ScenarioList
from ..surveys import Survey
from ..agents import AgentList


class StubJob:
    """A minimal job that passes through attached head objects.

    The run method returns whichever object type this StubJob is configured for.
    """

    def __init__(self, return_type: str = "survey"):
        self.scenario: Optional[ScenarioList] = None
        self.survey: Optional[Survey] = None
        self.agent_list: Optional[AgentList] = None
        self.return_type = return_type

        self._depends_on = None

        self.head_parameters: dict[str, Any] = {}
        self.has_post_run_methods = False

    def add_scenario_head(self, scenario: ScenarioList) -> "StubJob":
        self.scenario = scenario
        return self

    def add_survey_to_head(self, survey: Survey) -> "StubJob":
        self.survey = survey
        return self

    def add_agent_list_to_head(self, agent_list: AgentList) -> "StubJob":
        self.agent_list = agent_list
        return self

    def run(self, **kwargs) -> Any:
        if self.return_type == "survey":
            return self.survey
        elif self.return_type == "scenario":
            return self.scenario
        elif self.return_type == "agent_list":
            return self.agent_list
        else:
            raise ValueError(f"Invalid return type: {self.return_type}")

    def to_dict(self, **kwargs) -> dict:
        return {
            "return_type": self.return_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StubJob":
        return cls(return_type=data["return_type"])
