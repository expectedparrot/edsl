"""Analysis and debugging functionality for Results objects.

This module provides the ResultsAnalyzer class which handles specialized analysis
operations for Results objects, including prompt issue detection and improvement
suggestions.
"""

from typing import TYPE_CHECKING, Optional
import pandas as pd

if TYPE_CHECKING:
    from .results import Results
    from ..language_models import ModelList

from .exceptions import ResultsError


class ResultsAnalyzer:
    """Handles analysis and debugging operations for Results objects.

    This class encapsulates specialized analysis functionality for Results objects,
    particularly focused on identifying and suggesting improvements for problematic
    prompts that resulted in null or bad model responses.

    Attributes:
        results: The Results object to analyze
    """

    def __init__(self, results: "Results"):
        """Initialize the analyzer with a Results object.

        Args:
            results: The Results object to analyze
        """
        self.results = results

    def spot_issues(self, models: Optional["ModelList"] = None) -> "Results":
        """Run a survey to spot issues and suggest improvements for prompts that had no model response.

        This method analyzes the Results object to identify prompts that resulted in null or bad
        model responses, then creates a new survey asking an AI model to identify potential issues
        and suggest improvements for those problematic prompts.

        Args:
            models: Optional ModelList to use for the analysis. If None, uses the default model.

        Returns:
            Results: A new Results object containing the analysis and suggestions for improvement.

        Raises:
            ResultsError: If models parameter is not a ModelList when provided.

        Notes:
            Future version: Allow user to optionally pass a list of questions to review,
            regardless of whether they had a null model response.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> analyzer = ResultsAnalyzer(r)
            >>> # analysis_results = analyzer.spot_issues()  # Would analyze null responses
        """
        from ..questions import QuestionFreeText, QuestionDict
        from ..surveys import Survey
        from ..scenarios import Scenario, ScenarioList
        from ..language_models import ModelList

        df = self.results.select(
            "agent.*", "scenario.*", "answer.*", "raw_model_response.*", "prompt.*"
        ).to_pandas()
        scenario_list = []

        for _, row in df.iterrows():
            for col in df.columns:
                if col.endswith("_raw_model_response") and pd.isna(row[col]):
                    q = col.split("_raw_model_response")[0].replace(
                        "raw_model_response.", ""
                    )

                    s = Scenario(
                        {
                            "original_question": q,
                            "original_agent_index": row["agent.agent_index"],
                            "original_scenario_index": row["scenario.scenario_index"],
                            "original_prompts": f"User prompt: {row[f'prompt.{q}_user_prompt']}\nSystem prompt: {row[f'prompt.{q}_system_prompt']}",
                        }
                    )

                    scenario_list.append(s)

        sl = ScenarioList(set(scenario_list))

        q1 = QuestionFreeText(
            question_name="issues",
            question_text="""
            The following prompts generated a bad or null response: '{{ original_prompts }}'
            What do you think was the likely issue(s)?
            """,
        )

        q2 = QuestionDict(
            question_name="revised",
            question_text="""
            The following prompts generated a bad or null response: '{{ original_prompts }}'
            You identified the issue(s) as '{{ issues.answer }}'.
            Please revise the prompts to address the issue(s).
            """,
            answer_keys=["revised_user_prompt", "revised_system_prompt"],
        )

        survey = Survey(questions=[q1, q2])

        if models is not None:
            if not isinstance(models, ModelList):
                raise ResultsError("models must be a ModelList")
            results = survey.by(sl).by(models).run()
        else:
            results = survey.by(sl).run()  # use the default model

        return results
