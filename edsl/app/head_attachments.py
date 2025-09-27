from __future__ import annotations

from typing import Optional
from dataclasses import dataclass

from ..scenarios import Scenario, ScenarioList
from ..surveys import Survey
from ..agents import AgentList
from .output_formatter import ObjectFormatter


@dataclass
class HeadAttachments:
    """Attach objects to the head of a jobs object."""

    scenario: Optional[ScenarioList] = None
    survey: Optional[Survey] = None
    agent_list: Optional[AgentList] = None

    def apply_formatter(
        self, formatter: ObjectFormatter, params: dict | None = None
    ) -> "HeadAttachments":
        # Render starting from the targeted slot
        if formatter.target == "scenario":
            starting_value = self.scenario
        elif formatter.target == "survey":
            starting_value = self.survey
        elif formatter.target == "agent_list":
            starting_value = self.agent_list
        else:
            starting_value = None

        rendered = formatter.render(starting_value, params=params)

        # Route to the correct slot based on the rendered value type
        if isinstance(rendered, (Scenario, ScenarioList)):
            self.scenario = rendered
            # If we transformed a Survey into scenarios, avoid also attaching the original Survey
            if formatter.target == "survey":
                self.survey = None
        elif isinstance(rendered, Survey):
            self.survey = rendered
        elif isinstance(rendered, AgentList):
            self.agent_list = rendered
        else:
            # Fallback: write back to the targeted slot
            if formatter.target == "scenario":
                self.scenario = rendered
            elif formatter.target == "survey":
                self.survey = rendered
            elif formatter.target == "agent_list":
                self.agent_list = rendered
        return self

    def attach_to_head(self, jobs: "Jobs") -> "Jobs":
        if self.scenario:
            jobs = jobs.add_scenario_head(self.scenario)
        if self.survey:
            jobs = jobs.add_survey_to_head(self.survey)
        if self.agent_list:
            jobs = jobs.add_agent_list_to_head(self.agent_list)
        return jobs


