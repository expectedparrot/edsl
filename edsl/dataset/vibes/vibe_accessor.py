"""
Dataset Vibe Accessor: Provides a namespace for vibe-based dataset methods.

This module provides the DatasetVibeAccessor class that enables the
`dataset.vibe.filter()`, `dataset.vibe.plot()`, and `dataset.vibe.sql()`
interface pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..dataset import Dataset


class DatasetVibeAccessor:
    """
    Accessor class for vibe-based dataset methods.

    This class provides a namespace for all vibe-related dataset methods,
    enabling the `dataset.vibe.*` interface pattern.

    Examples
    --------
    >>> from edsl.dataset import Dataset
    >>> data = Dataset.example()  # doctest: +SKIP
    >>> data.vibe.filter("Keep only people over 30")  # doctest: +SKIP
    >>> data.vibe.plot("bar chart of satisfaction scores")  # doctest: +SKIP
    >>> data.vibe.sql("Show average satisfaction by age group")  # doctest: +SKIP
    """

    def __init__(self, dataset: "Dataset"):
        """
        Initialize the accessor with a dataset instance.

        Args:
            dataset: The Dataset instance to operate on
        """
        self._dataset = dataset

    def filter(
        self,
        criteria: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.1,
        show_expression: bool = False,
    ) -> "Dataset":
        """Filter the dataset using natural language criteria.

        This method uses an LLM to generate a filter expression based on
        natural language criteria, then applies it using the dataset's filter method.

        Parameters:
            criteria: Natural language description of the filtering criteria.
                Examples:
                - "Keep only people over 30"
                - "Remove outliers in the satisfaction scores"
                - "Only include responses from the last month"
            model: OpenAI model to use for generating the filter (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.1 for consistent logic)
            show_expression: If True, prints the generated filter expression

        Returns:
            Dataset: A new Dataset containing only rows that match the criteria

        Examples:
            Basic filtering:

            >>> from edsl.dataset import Dataset
            >>> data = Dataset([  # doctest: +SKIP
            ...     {"name": "Alice", "age": 30, "score": 85},
            ...     {"name": "Bob", "age": 25, "score": 92}
            ... ])
            >>> filtered = data.vibe.filter("Keep only people over 25")  # doctest: +SKIP
            >>> len(filtered)  # doctest: +SKIP
            2

            With expression display:

            >>> filtered = data.vibe.filter(  # doctest: +SKIP
            ...     "Only high performers",
            ...     show_expression=True
            ... )
            Generated filter expression: score >= 90

            Complex criteria:

            >>> filtered = data.vibe.filter("Keep people aged 25-35 with high scores")  # doctest: +SKIP

        Notes:
            - Requires OPENAI_API_KEY environment variable to be set
            - Uses LLM to generate Python expressions with operators: ==, !=, >, <, >=, <=, in, and, or, not
            - The generated expression is applied using the dataset's built-in filter() method
            - Supports complex boolean logic and range operations
        """
        from .vibe_filter import VibeFilter

        # Get column names and sample data
        columns = self._dataset.relevant_columns()

        # Get a few sample rows to help the LLM understand the data structure
        sample_dicts = self._dataset.to_dicts(remove_prefix=False)[:5]

        # Create the filter generator
        filter_gen = VibeFilter(model=model, temperature=temperature)

        # Generate the filter expression
        filter_expr = filter_gen.create_filter(columns, sample_dicts, criteria)

        if show_expression:
            print(f"Generated filter expression: {filter_expr}")

        # Use the dataset's built-in filter method which returns Dataset
        return self._dataset.filter(filter_expr)

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
            >>> from edsl.dataset import Dataset
            >>> data = Dataset.example()  # doctest: +SKIP
            >>> data.vibe.plot("bar chart of satisfaction scores")  # doctest: +SKIP
            >>> data.vibe.plot("scatter plot of age vs income", height=8, width=10)  # doctest: +SKIP

        Notes:
            - Requires R and ggplot2 to be installed
            - Generates R/ggplot2 code from natural language descriptions
            - Uses OpenAI's LLM to understand data structure and create appropriate visualizations
        """
        return self._dataset.vibe_plot(
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
    ) -> "Dataset":
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
            Dataset: A Dataset object containing the query results

        Examples:
            >>> from edsl.dataset import Dataset
            >>> data = Dataset.example()  # doctest: +SKIP
            >>> data.vibe.sql("Show average satisfaction by age group")  # doctest: +SKIP
            >>> data.vibe.sql("Count responses by month", show_expression=True)  # doctest: +SKIP
            >>> data.vibe.sql("Find top 10 highest scoring responses")  # doctest: +SKIP

        Notes:
            - Generates SQL queries using OpenAI's LLM
            - Executes queries against an in-memory SQLite representation of the data
            - SQL queries are optimized for SQLite syntax
            - Results are returned as a new Dataset object
        """
        return self._dataset.vibe_sql(
            description=description,
            show_code=show_code,
            show_expression=show_expression,
            transpose=transpose,
            transpose_by=transpose_by,
            remove_prefix=remove_prefix,
            shape=shape,
        )
