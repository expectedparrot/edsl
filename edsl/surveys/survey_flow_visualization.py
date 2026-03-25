"""Moved to edsl.surveys.extras.survey_flow_visualization.

This module is kept for import compatibility. The implementation now lives in
edsl/surveys/extras/ to clarify that it depends on optional packages (pydot).
"""


def __getattr__(name):
    if name == "SurveyFlowVisualization":
        from edsl.surveys.extras.survey_flow_visualization import (
            SurveyFlowVisualization,
        )

        return SurveyFlowVisualization
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
