from __future__ import annotations

from typing import Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

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
        logger.info(
            f"apply_formatter called: formatter.target={formatter.target}, formatter.description={getattr(formatter, 'description', None)}"
        )
        logger.info(
            f"Current attachments before: scenario={self.scenario is not None}, survey={self.survey is not None}, agent_list={self.agent_list is not None}"
        )

        # Render starting from the targeted slot
        if formatter.target == "scenario":
            starting_value = self.scenario
        elif formatter.target == "survey":
            starting_value = self.survey
        elif formatter.target == "agent_list":
            starting_value = self.agent_list
        else:
            starting_value = None

        logger.info(
            f"Starting value for target '{formatter.target}': {type(starting_value).__name__ if starting_value else None}"
        )

        # Guard: if a typed formatter is applied but no starting attachment exists,
        # raise a clear error to help the caller fix missing inputs.
        if (
            formatter.target in {"scenario", "survey", "agent_list"}
            and starting_value is None
        ):
            raise ValueError(
                f"AttachmentFormatter targeting '{formatter.target}' requires an existing attachment. "
                f"No '{formatter.target}' is currently attached. Ensure your initial_survey and params "
                f"provide a {formatter.target} attachment before applying this formatter."
            )

        logger.info(f"About to render formatter on {type(starting_value).__name__}")
        rendered = formatter.render(starting_value, params=params)
        logger.info(f"Rendered result type: {type(rendered).__name__}")

        # Route to the correct slot based on the rendered value type
        if isinstance(rendered, (Scenario, ScenarioList)):
            logger.info("Rendered is Scenario/ScenarioList, setting to scenario slot")
            self.scenario = rendered
            # If we transformed a Survey into scenarios, avoid also attaching the original Survey
            if formatter.target == "survey":
                logger.info("Formatter target was survey, clearing survey slot")
                self.survey = None
        elif isinstance(rendered, Survey):
            logger.info("Rendered is Survey, setting to survey slot")
            self.survey = rendered
        elif isinstance(rendered, AgentList):
            logger.info("Rendered is AgentList, setting to agent_list slot")
            self.agent_list = rendered
        else:
            logger.info(
                f"Rendered is other type, falling back to target slot: {formatter.target}"
            )
            # Fallback: write back to the targeted slot
            if formatter.target == "scenario":
                self.scenario = rendered
            elif formatter.target == "survey":
                self.survey = rendered
            elif formatter.target == "agent_list":
                self.agent_list = rendered

        logger.info(
            f"Attachments after formatter: scenario={self.scenario is not None}, survey={self.survey is not None}, agent_list={self.agent_list is not None}"
        )
        return self

    def attach_to_head(self, jobs: "Jobs") -> "Jobs":
        logger.info(
            f"attach_to_head called with scenario={self.scenario is not None}, survey={self.survey is not None}, agent_list={self.agent_list is not None}"
        )
        if self.scenario:
            logger.info(f"Adding scenario to head: type={type(self.scenario).__name__}")
            if hasattr(self.scenario, "__len__"):
                logger.info(f"Scenario has {len(self.scenario)} items")
            jobs = jobs.add_scenario_head(self.scenario)
        if self.survey:
            logger.info(f"Adding survey to head: type={type(self.survey).__name__}")
            jobs = jobs.add_survey_to_head(self.survey)
        if self.agent_list:
            logger.info(
                f"Adding agent_list to head: type={type(self.agent_list).__name__}"
            )
            jobs = jobs.add_agent_list_to_head(self.agent_list)
        return jobs
