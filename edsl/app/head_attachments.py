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

        # Guard: if a typed formatter is applied but no starting attachment exists,
        # raise a clear error to help the caller fix missing inputs.
        if formatter.target in {"scenario", "survey", "agent_list"} and starting_value is None:
            raise ValueError(
                f"AttachmentFormatter targeting '{formatter.target}' requires an existing attachment. "
                f"No '{formatter.target}' is currently attached. Ensure your initial_survey and params "
                f"provide a {formatter.target} attachment before applying this formatter."
            )

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


