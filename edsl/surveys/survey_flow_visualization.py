"""A mixin for visualizing the flow of a survey with parameter nodes.

This module now delegates to the FlowVisualizationService.
The original pydot-based code has been moved to the service.
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..surveys.survey import Survey
    from ..scenarios import Scenario
    from ..agents import Agent


class SurveyFlowVisualization:
    """A mixin for visualizing the flow of a survey with parameter visualization.

    This class now delegates to the FlowVisualizationService.
    """

    def __init__(
        self,
        survey: "Survey",
        scenario: Optional["Scenario"] = None,
        agent: Optional["Agent"] = None,
    ):
        self.survey = survey
        self.scenario = scenario or {}
        self.agent = agent

    def show_flow(self, filename: Optional[str] = None, verbose: bool = True):
        """Create an image showing the flow of users through the survey.

        This method delegates to the FlowVisualizationService.

        Args:
            filename: Optional path to save the PNG. If None, displays inline.
            verbose: Whether to show progress messages.

        Returns:
            FileStore containing the PNG image.
        """
        from edsl_services.flow_visualization_service import FlowVisualizationService

        if verbose:
            print("[flow_visualization] Generating survey flow diagram...")

        params = {
            "operation": "flow",
            "data": self.survey.to_dict(),
            "scenario": (
                self.scenario.to_dict() if hasattr(self.scenario, "to_dict") else None
            ),
            "agent": (
                self.agent.to_dict()
                if self.agent and hasattr(self.agent, "to_dict")
                else None
            ),
            "filename": filename,
        }

        result = FlowVisualizationService.execute(params)
        fs = FlowVisualizationService.parse_result(result)

        if verbose:
            print("[flow_visualization] ✓ Flow diagram created")

        if filename is None:
            fs.view()
        else:
            print(f"Flowchart saved to {filename}")

        return fs
