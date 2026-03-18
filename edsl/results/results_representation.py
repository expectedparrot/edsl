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
        r = self._results

        num_obs = len(r)
        num_agents = len(set(r.agents))
        num_models = len(set(r.models))
        num_scenarios = len(set(r.scenarios))
        num_questions = len(r.survey.questions) if r.survey and hasattr(r.survey, "questions") else 0

        title = (
            f"Results (observations: {num_obs}, questions: {num_questions}, "
            f"agents: {num_agents}, models: {num_models}, scenarios: {num_scenarios})"
        )

        ds = r.to_dataset()

        caption_parts: list[str] = []
        if r.created_columns:
            caption_parts.append(f"created_columns: {r.created_columns}")

        return ds._summary_repr(
            title=title,
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
