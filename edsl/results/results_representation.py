"""Results representation operations module."""

from __future__ import annotations

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

        result = self.summary_repr()
        info = self._results._store_info_line()
        if info:
            result = result.rstrip() + "\n" + info
        return result

    def eval_repr(self) -> str:
        """Return an eval-able string representation of the Results.

        This representation can be used with eval() to recreate the Results object.
        Used primarily for doctests and debugging.
        """
        r = self._results
        return f"Results(data = {r.data}, survey = {repr(r.survey)}, created_columns = {r.created_columns})"

    def summary_repr(self, max_text_preview: int = 60, max_items: int = 500) -> str:
        """Generate a summary representation of the Results as a Rich table."""
        from ..utilities.summary_table import ColumnDef, render_summary_table

        r = self._results

        num_obs = len(r)
        num_agents = len(set(r.agents))
        num_models = len(set(r.models))
        num_scenarios = len(set(r.scenarios))
        num_questions = len(r.survey.questions) if r.survey and hasattr(r.survey, "questions") else 0

        title = (
            f"Results ({num_obs} observation{'s' if num_obs != 1 else ''}, "
            f"{num_questions} question{'s' if num_questions != 1 else ''})"
        )

        columns = [
            ColumnDef("Component", style="bold green", no_wrap=True),
            ColumnDef("Count", style="dim", no_wrap=True, justify="right"),
            ColumnDef("Details"),
        ]

        rows: list[tuple] = []

        # Questions
        if r.survey and hasattr(r.survey, "questions"):
            names = [q.question_name for q in r.survey.questions]
            rows.append(("Questions", str(num_questions), ", ".join(names)))

        # Agents
        agent_detail = ""
        if num_agents > 0:
            trait_keys = [k for k in r.agent_keys if not k.startswith("agent_")]
            if trait_keys:
                agent_detail = f"traits: {', '.join(trait_keys)}"
        rows.append(("Agents", str(num_agents), agent_detail))

        # Models
        model_names = []
        for m in set(r.models):
            model_names.append(getattr(m, "model", getattr(m, "_model_", "unknown")))
        rows.append(("Models", str(num_models), ", ".join(sorted(set(model_names)))))

        # Scenarios
        scenario_detail = ""
        if num_scenarios > 0:
            field_keys = [k for k in r.scenario_keys if not k.startswith("scenario_")]
            if field_keys:
                scenario_detail = f"keys: {', '.join(field_keys)}"
        rows.append(("Scenarios", str(num_scenarios), scenario_detail))

        caption_parts: list[str] = []
        if r.created_columns:
            caption_parts.append(f"created_columns: {r.created_columns}")

        return render_summary_table(
            title=title,
            columns=columns,
            rows=rows,
            caption=", ".join(caption_parts) if caption_parts else None,
        )

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
