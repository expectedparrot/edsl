"""
Dataset Vibe Filter: Filter datasets using natural language criteria.

This module provides a VibeFilter class that can filter datasets based on
natural language descriptions of filtering criteria.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import os
import json
from dotenv import load_dotenv
from pathlib import Path
from ...base.openai_utils import create_openai_client


def find_dotenv_upwards(start_path: Optional[str] = None) -> Optional[Path]:
    """
    Search for .env file starting from start_path and moving up the directory tree.

    Parameters
    ----------
    start_path : str, optional
        Starting directory for the search. Defaults to current working directory.

    Returns
    -------
    Path or None
        Path to the .env file if found, None otherwise.
    """
    if start_path is None:
        start_path = os.getcwd()

    current = Path(start_path).resolve()

    # Search upwards until we find .env or reach the root
    while True:
        env_file = current / ".env"
        if env_file.is_file():
            return env_file

        # Check if we've reached the root
        parent = current.parent
        if parent == current:
            # We've reached the root directory
            return None

        current = parent


# Load environment variables from .env file (search upwards from current directory)
env_path = find_dotenv_upwards()
if env_path:
    load_dotenv(env_path)


@dataclass
class VibeFilter:
    """
    Filter datasets using natural language criteria.

    This class uses an LLM to generate Python filtering logic based on natural
    language descriptions. It creates executable filter expressions that can be
    applied to datasets.

    Parameters
    ----------
    model : str
        The OpenAI model to use (default: "gpt-4o")
    temperature : float
        Temperature for generation (default: 0.1 for consistent logic)

    Examples
    --------
    >>> filter_tool = VibeFilter()  # doctest: +SKIP
    >>> filter_expr = filter_tool.create_filter(  # doctest: +SKIP
    ...     columns=["age", "occupation"],
    ...     sample_data=[{"age": 25, "occupation": "student"}, {"age": 35, "occupation": "engineer"}],
    ...     criteria="Keep only people over 30"
    ... )  # doctest: +SKIP
    """

    model: str = "gpt-4o"
    temperature: float = 0.1

    def __post_init__(self):
        self.client = (
            create_openai_client()
        )  # reads OPENAI_API_KEY from env with proper error handling

    def create_filter(
        self,
        columns: List[str],
        sample_data: List[Dict[str, Any]],
        criteria: str,
    ) -> str:
        """
        Generate a Python filter expression from natural language criteria.

        Parameters
        ----------
        columns : List[str]
            List of column names available in the dataset
        sample_data : List[Dict[str, Any]]
            Sample rows from the dataset to understand data types and values
        criteria : str
            Natural language description of the filtering criteria.
            Examples:
            - "Keep only people over 30"
            - "Remove outliers in the satisfaction scores"
            - "Only include responses from the last month"
            - "Filter out any rows with missing data"

        Returns
        -------
        str
            A Python expression that can be evaluated to filter rows.
            The expression should return True to keep a row, False to filter it out.
            The expression has access to row data as a dictionary called 'row'.

        Examples
        --------
        >>> filter_tool = VibeFilter(model="gpt-4o", temperature=0.1)  # doctest: +SKIP
        >>> columns = ["age", "occupation"]  # doctest: +SKIP
        >>> sample = [{"age": 25, "occupation": "student"}]  # doctest: +SKIP
        >>> expr = filter_tool.create_filter(columns, sample, "age over 30")  # doctest: +SKIP
        >>> "age" in expr and "30" in expr  # doctest: +SKIP
        True  # doctest: +SKIP
        """
        system = (
            "You are an expert at writing data filtering expressions. "
            "Given a natural language description of filtering criteria and information "
            "about a dataset, generate a simple filter expression. "
            "\n\n"
            "Your task is to:\n"
            "1. Understand the natural language filtering criteria\n"
            "2. Examine the available columns and sample data\n"
            "3. Generate a simple boolean expression that returns True to KEEP a row, False to filter it out\n"
            "4. Reference columns by their names directly (not as dictionary keys)\n"
            "5. Keep expressions simple and readable\n"
            "\n"
            "Important guidelines:\n"
            "- Reference columns directly by name: age, occupation, city, etc.\n"
            "- Return a single boolean expression as a string\n"
            "- Use appropriate operators: ==, !=, >, <, >=, <=, in, and, or, not\n"
            "- For string matching with quotes: occupation == 'engineer'\n"
            "- For numeric comparisons: age > 30\n"
            "- For compound conditions: age > 30 and occupation == 'engineer'\n"
            "- The expression should be simple and readable\n"
            "\n"
            "Examples:\n"
            "- 'Keep people over 30' -> \"age > 30\"\n"
            "- 'Only engineers' -> \"occupation == 'engineer'\"\n"
            "- 'Engineers in Boston' -> \"occupation == 'engineer' and city == 'Boston'\"\n"
            "- 'High satisfaction scores' -> \"satisfaction >= 4\"\n"
            "- 'Engineers or teachers' -> \"occupation == 'engineer' or occupation == 'teacher'\"\n"
        )

        user_prompt = {
            "task": "Generate a Python filter expression",
            "criteria": criteria,
            "available_columns": columns,
            "sample_data": sample_data[:3],  # Just show first 3 rows as examples
            "instructions": (
                "Based on the filtering criteria, generate a Python boolean expression. "
                "The expression should return True to keep a row, False to filter it out. "
                "Use 'row' as the dictionary containing the current row's data. "
                "Return ONLY a valid JSON object with a 'filter_expression' key containing the Python expression as a string."
            ),
        }

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_prompt, indent=2)},
            ],
            response_format={"type": "json_object"},
            temperature=self.temperature,
        )

        # Parse the JSON response
        result = json.loads(resp.choices[0].message.content)
        return result.get("filter_expression", "True")


# ---------- Example usage ----------
if __name__ == "__main__":
    filter_tool = VibeFilter(model="gpt-4o", temperature=0.1)

    # Example 1: Age filtering
    print("Example 1: Filter by age")
    columns = ["age", "occupation", "city"]
    sample_data = [
        {"age": 25, "occupation": "student", "city": "Boston"},
        {"age": 35, "occupation": "engineer", "city": "San Francisco"},
        {"age": 28, "occupation": "teacher", "city": "New York"},
    ]
    expr = filter_tool.create_filter(columns, sample_data, "Keep only people over 30")
    print(f"Filter expression: {expr}")
    print()

    # Example 2: String matching
    print("Example 2: Filter by occupation")
    expr2 = filter_tool.create_filter(columns, sample_data, "Only engineers")
    print(f"Filter expression: {expr2}")
    print()

    # Example 3: Complex criteria
    print("Example 3: Complex filter")
    expr3 = filter_tool.create_filter(
        columns, sample_data, "People over 25 in technical roles"
    )
    print(f"Filter expression: {expr3}")
