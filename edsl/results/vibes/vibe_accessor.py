"""
Results Vibe Accessor: Provides a namespace for vibe-based results methods.

This module provides the ResultsVibeAccessor class that enables the
`results.vibe.analyze()`, `results.vibe.plot()`, and `results.vibe.sql()`
interface pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..results import Results
    from .vibe_analyze_handler import ResultsVibeAnalysis


class ResultsVibeAccessor:
    """
    Accessor class for vibe-based results analysis methods.

    This class provides a namespace for all vibe-related results methods,
    enabling the `results.vibe.*` interface pattern.

    Examples
    --------
    >>> results = Results.example()  # doctest: +SKIP
    >>> results.vibe.analyze()  # doctest: +SKIP
    >>> results.vibe.plot()  # doctest: +SKIP
    >>> results.vibe.sql()  # doctest: +SKIP
    >>> results.vibe.describe()  # doctest: +SKIP
    """

    def __init__(self, results: "Results"):
        """
        Initialize the accessor with a results instance.

        Args:
            results: The Results instance to operate on
        """
        self._results = results

    def analyze(
        self,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        include_visualizations: bool = False,
        generate_summary: bool = True,
    ) -> "ResultsVibeAnalysis":
        """Analyze all questions with LLM-powered insights.

        This method iterates through each question in the survey, generates
        standard analysis using the existing analyze() method, and uses an LLM
        to provide natural language insights about the data patterns. Optionally,
        it can also send visualizations to OpenAI's vision API for analysis.

        In a Jupyter notebook, the results will display automatically with rich
        formatting. For the best experience with interactive plots, call .display()
        on the returned object.

        Args:
            model: OpenAI model to use for generating insights (default: "gpt-4o")
            temperature: Temperature for LLM generation (default: 0.7)
            include_visualizations: Whether to send visualizations to OpenAI for analysis
                (default: False). WARNING: This can significantly increase API costs.
            generate_summary: Whether to generate an overall summary report across
                all questions (default: True)

        Returns:
            ResultsVibeAnalysis: Container object with analyses for all questions.
                In Jupyter notebooks, will display automatically with HTML formatting.
                For interactive plots, call .display() method.

        Raises:
            ValueError: If no survey is available or visualization dependencies missing
            ImportError: If required packages are not installed

        Examples:
            >>> results = Results.example()  # doctest: +SKIP

            >>> # Basic usage - will show HTML summary in notebooks
            >>> results.vibe.analyze()  # doctest: +SKIP

            >>> # For interactive plots and rich display
            >>> analysis = results.vibe.analyze()  # doctest: +SKIP
            >>> analysis.display()  # Shows plots inline with insights  # doctest: +SKIP

            >>> # Access a specific question's analysis
            >>> q_analysis = analysis["how_feeling"]  # doctest: +SKIP
            >>> q_analysis.analysis.bar_chart  # doctest: +SKIP
            >>> print(q_analysis.llm_insights)  # doctest: +SKIP
            >>> # Charts are stored as PNG bytes for serialization
            >>> q_analysis.chart_png  # PNG bytes  # doctest: +SKIP

            >>> # With visualization analysis (more expensive - uses vision API)
            >>> analysis = results.vibe.analyze(  # doctest: +SKIP
            ...     include_visualizations=True
            ... )  # doctest: +SKIP
            >>> analysis.display()  # doctest: +SKIP

            >>> # Export to serializable format for notebooks
            >>> data = analysis.to_dict()  # doctest: +SKIP
            >>> import json  # doctest: +SKIP
            >>> json.dumps(data)  # Fully serializable  # doctest: +SKIP
        """
        from .vibe_analyze_handler import analyze_with_vibes

        return analyze_with_vibes(
            self._results,
            model=model,
            temperature=temperature,
            include_visualizations=include_visualizations,
            generate_summary=generate_summary,
        )

    def plot(
        self,
        description: str,
        show_code: bool = True,
        show_expression: bool = False,
        height: float = 4,
        width: float = 6,
    ):
        """Generate and display a ggplot2 visualization using natural language description.

        Parameters:
            description: Natural language description of the desired plot
            show_code: If True, displays the generated R code alongside the plot
            show_expression: If True, prints the R code used (alias for show_code)
            height: Plot height in inches (default: 4)
            width: Plot width in inches (default: 6)

        Returns:
            A plot object that renders in Jupyter notebooks

        Examples:
            >>> results = Results.example()  # doctest: +SKIP
            >>> results.vibe.plot("bar chart of how_feeling")  # doctest: +SKIP
            >>> results.vibe.plot("scatter plot of age vs income", height=8, width=10)  # doctest: +SKIP
        """
        return self._results.vibe_plot(
            description=description,
            show_code=show_code,
            show_expression=show_expression,
            height=height,
            width=width,
        )

    def sql(
        self,
        description: str,
        show_code: bool = True,
        show_expression: bool = False,
        transpose: bool = None,
        transpose_by: str = None,
        remove_prefix: bool = True,
        shape: str = "wide",
    ):
        """Generate and execute a SQL query using natural language description.

        Parameters:
            description: Natural language description of the desired query
            show_code: If True, displays the generated SQL query with copy button
            show_expression: If True, displays the generated SQL query (alias for show_code)
            transpose: Whether to transpose the resulting table (rows become columns)
            transpose_by: Column to use as the new index when transposing
            remove_prefix: Whether to remove type prefixes from column names
            shape: Data shape to use ("wide" or "long")

        Returns:
            A Dataset object containing the query results

        Examples:
            >>> results = Results.example()  # doctest: +SKIP
            >>> results.vibe.sql("Show all people over 30")  # doctest: +SKIP
            >>> results.vibe.sql("Count by occupation", show_expression=True)  # doctest: +SKIP
            >>> results.vibe.sql("Average age by city")  # doctest: +SKIP
        """
        return self._results.vibe_sql(
            description=description,
            show_code=show_code,
            show_expression=show_expression,
            transpose=transpose,
            transpose_by=transpose_by,
            remove_prefix=remove_prefix,
            shape=shape,
        )

    def describe(
        self,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
    ) -> "Scenario":
        """Generate a title and description for the Results object.

        Uses an LLM to analyze the Results object (including Survey, AgentList, and ScenarioList)
        and generate a descriptive title and detailed description of what the study/research is about.

        Args:
            model: OpenAI model to use for generation (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.7)

        Returns:
            Scenario: A Scenario with keys:
                - "proposed_title": A single sentence title for the results
                - "description": A paragraph-length description of the results

        Examples:
            >>> results = Results.example()  # doctest: +SKIP
            >>> info = results.vibe.describe()  # doctest: +SKIP
            >>> print(info["proposed_title"])  # doctest: +SKIP
            >>> print(info["description"])  # doctest: +SKIP
        """
        from .vibe_describe_handler import describe_results_with_vibes

        d = describe_results_with_vibes(
            self._results,
            model=model,
            temperature=temperature,
        )
        from ...scenarios import Scenario

        return Scenario(**d)
