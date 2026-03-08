"""Results representation operations module."""

from __future__ import annotations

import io
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .results import Results


class ResultsRepresentation:
    """Handles string representation operations for Results objects.

    Instantiated with a reference to a Results instance; provides __repr__
    dispatch, eval-safe repr, and rich summary formatting.
    """

    def __init__(self, results: "Results") -> None:
        self._results = results

    def repr(self) -> str:
        """Return a string representation of the Results.

        Uses traditional repr format when running doctests, otherwise uses
        rich-based display for better readability. In Jupyter notebooks,
        returns a minimal string since _repr_html_ handles the display.
        """
        if os.environ.get("EDSL_RUNNING_DOCTESTS") == "True":
            return self.eval_repr()

        try:
            from IPython import get_ipython

            ipy = get_ipython()
            if ipy is not None and "IPKernelApp" in ipy.config:
                return "Results(...)"
        except (NameError, ImportError):
            pass

        return self.summary_repr()

    def eval_repr(self) -> str:
        """Return an eval-able string representation of the Results.

        This representation can be used with eval() to recreate the Results object.
        Used primarily for doctests and debugging.
        """
        r = self._results
        return f"Results(data = {r.data}, survey = {repr(r.survey)}, created_columns = {r.created_columns})"

    def summary_repr(self, max_text_preview: int = 60, max_items: int = 25) -> str:
        """Generate a summary representation of the Results with Rich formatting.

        Args:
            max_text_preview: Maximum characters to show for question text previews
            max_items: Maximum number of items to show in lists before truncating
        """
        from rich.console import Console
        from rich.text import Text
        from edsl.config import RICH_STYLES

        r = self._results

        output = Text()
        output.append("Results(\n", style=RICH_STYLES["primary"])
        output.append(
            f"    num_observations={len(r)},\n", style=RICH_STYLES["default"]
        )
        output.append(
            f"    num_agents={len(set(r.agents))},\n", style=RICH_STYLES["default"]
        )
        output.append(
            f"    num_models={len(set(r.models))},\n", style=RICH_STYLES["default"]
        )
        output.append(
            f"    num_scenarios={len(set(r.scenarios))},\n",
            style=RICH_STYLES["default"],
        )

        if len(r.agents) > 0:
            agent_keys = r.agent_keys
            if agent_keys:
                output.append("    agent_traits: [", style=RICH_STYLES["default"])
                trait_keys = [k for k in agent_keys if not k.startswith("agent_")]
                if trait_keys:
                    output.append(
                        f"{', '.join(repr(k) for k in trait_keys[:max_items])}",
                        style=RICH_STYLES["secondary"],
                    )
                    if len(trait_keys) > max_items:
                        output.append(
                            f", ... ({len(trait_keys) - max_items} more)",
                            style=RICH_STYLES["dim"],
                        )
                output.append("],\n", style=RICH_STYLES["default"])

        if len(r.scenarios) > 0:
            scenario_keys = r.scenario_keys
            if scenario_keys:
                output.append("    scenario_fields: [", style=RICH_STYLES["default"])
                field_keys = [k for k in scenario_keys if not k.startswith("scenario_")]
                if field_keys:
                    output.append(
                        f"{', '.join(repr(k) for k in field_keys[:max_items])}",
                        style=RICH_STYLES["secondary"],
                    )
                    if len(field_keys) > max_items:
                        output.append(
                            f", ... ({len(field_keys) - max_items} more)",
                            style=RICH_STYLES["dim"],
                        )
                output.append("],\n", style=RICH_STYLES["default"])

        if r.survey and hasattr(r.survey, "questions"):
            questions = r.survey.questions
            output.append(
                f"    num_questions={len(questions)},\n", style=RICH_STYLES["default"]
            )
            output.append("    questions: [\n", style=RICH_STYLES["default"])

            for question in questions[:max_items]:
                q_name = question.question_name
                q_text = question.question_text

                if len(q_text) > max_text_preview:
                    q_text = q_text[:max_text_preview] + "..."

                output.append("        ", style=RICH_STYLES["default"])
                output.append(f"'{q_name}'", style=RICH_STYLES["secondary"])
                output.append(": ", style=RICH_STYLES["default"])
                output.append(f'"{q_text}"', style=RICH_STYLES["dim"])
                output.append(",\n", style=RICH_STYLES["default"])

            if len(questions) > max_items:
                output.append(
                    f"        ... ({len(questions) - max_items} more)\n",
                    style=RICH_STYLES["dim"],
                )

            output.append("    ],\n", style=RICH_STYLES["default"])

        if r.created_columns:
            output.append(
                f"    created_columns={r.created_columns}\n",
                style=RICH_STYLES["key"],
            )

        output.append(")", style=RICH_STYLES["primary"])

        console = Console(file=io.StringIO(), force_terminal=True, width=120)
        console.print(output, end="")
        return console.file.getvalue()

    def summary(self) -> dict:
        """Return a dictionary containing summary statistics about the Results object.

        The summary includes:
        - Number of observations (results)
        - Number of unique agents
        - Number of unique models
        - Number of unique scenarios
        - Number of questions in the survey
        - Survey question names (truncated for readability)

        Returns:
            dict: A dictionary containing the summary statistics

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> summary = r._summary()
            >>> isinstance(summary, dict)
            True
            >>> all(key in summary for key in ['observations', 'agents', 'models', 'scenarios', 'questions', 'Survey question names'])
            True
            >>> summary['observations'] > 0
            True
            >>> summary['questions'] > 0
            True
        """
        import reprlib

        r = self._results
        d = {
            "observations": len(r),
            "agents": len(set(r.agents)),
            "models": len(set(r.models)),
            "scenarios": len(set(r.scenarios)),
            "questions": len(r.survey),
            "Survey question names": reprlib.repr(r.survey.question_names),
        }
        return d
