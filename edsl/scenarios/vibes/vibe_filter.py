"""
ScenarioList Vibe Filter: Filter scenario lists using natural language criteria.

This module provides a VibeFilter class that can filter scenario lists based on
natural language descriptions of filtering criteria.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from openai import OpenAI
import os
import json
from dotenv import load_dotenv
from pathlib import Path


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
    Filter scenario lists using natural language criteria.

    This class uses an LLM to generate Python filtering logic based on natural
    language descriptions. It creates executable filter expressions that can be
    applied to scenario lists.

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
    ...     keys=["age", "occupation"],  # doctest: +SKIP
    ...     sample_scenarios=[{"age": 25, "occupation": "student"}, {"age": 35, "occupation": "engineer"}],  # doctest: +SKIP
    ...     criteria="Keep only people over 30"  # doctest: +SKIP
    ... )  # doctest: +SKIP
    """

    model: str = "gpt-4o"
    temperature: float = 0.1

    def __post_init__(self):
        self.client = OpenAI()  # reads OPENAI_API_KEY from env

    def create_filter(
        self,
        keys: List[str],
        sample_scenarios: List[Dict[str, Any]],
        criteria: str,
    ) -> str:
        """
        Generate a Python filter expression from natural language criteria.

        Parameters
        ----------
        keys : List[str]
            List of scenario keys available in the scenario list
        sample_scenarios : List[Dict[str, Any]]
            Sample scenarios from the scenario list to understand data types and values
        criteria : str
            Natural language description of the filtering criteria.
            Examples:
            - "Keep only people over 30"
            - "Remove scenarios with missing data"
            - "Only include scenarios from the US"
            - "Filter out any scenarios where age is less than 18"

        Returns
        -------
        str
            A Python expression that can be evaluated to filter scenarios.
            The expression should return True to keep a scenario, False to filter it out.
            The expression has access to scenario keys directly as variables.

        Examples
        --------
        >>> filter_tool = VibeFilter(model="gpt-4o", temperature=0.1)  # doctest: +SKIP
        >>> keys = ["age", "occupation"]  # doctest: +SKIP
        >>> sample = [{"age": 25, "occupation": "student"}]  # doctest: +SKIP
        >>> expr = filter_tool.create_filter(keys, sample, "age over 30")  # doctest: +SKIP
        >>> "age" in expr and "30" in expr  # doctest: +SKIP
        True
        """
        system = (
            "You are an expert at writing data filtering expressions. "
            "Given a natural language description of filtering criteria and information "
            "about a scenario list, generate a simple filter expression. "
            "\n\n"
            "Your task is to:\n"
            "1. Understand the natural language filtering criteria\n"
            "2. Examine the available scenario keys and sample data\n"
            "3. Generate a simple boolean expression that returns True to KEEP a scenario, False to filter it out\n"
            "4. Reference scenario keys by their names directly (not as dictionary keys)\n"
            "5. Keep expressions simple and readable\n"
            "\n"
            "Important guidelines:\n"
            "- Reference scenario keys directly by name: age, occupation, city, country, etc.\n"
            "- Return a single boolean expression as a string\n"
            "- Use appropriate operators: ==, !=, >, <, >=, <=, in, and, or, not\n"
            "- For string matching with quotes: occupation == 'engineer'\n"
            "- For numeric comparisons: age > 30\n"
            "- For compound conditions: age > 30 and occupation == 'engineer'\n"
            "- For membership tests: country in ['US', 'CA', 'UK']\n"
            "- The expression should be simple and readable\n"
            "\n"
            "Examples:\n"
            "- 'Keep people over 30' -> \"age > 30\"\n"
            "- 'Only engineers' -> \"occupation == 'engineer'\"\n"
            "- 'Engineers in Boston' -> \"occupation == 'engineer' and city == 'Boston'\"\n"
            "- 'High satisfaction scores' -> \"satisfaction >= 4\"\n"
            "- 'Engineers or teachers' -> \"occupation == 'engineer' or occupation == 'teacher'\"\n"
            "- 'US or Canadian residents' -> \"country in ['US', 'CA']\"\n"
        )

        user_prompt = {
            "task": "Generate a Python filter expression for a ScenarioList",
            "criteria": criteria,
            "available_keys": keys,
            "sample_scenarios": sample_scenarios[
                :3
            ],  # Just show first 3 scenarios as examples
            "instructions": (
                "Based on the filtering criteria, generate a Python boolean expression. "
                "The expression should return True to keep a scenario, False to filter it out. "
                "Reference scenario keys directly by their names (e.g., 'age', 'occupation'). "
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
    keys = ["age", "occupation", "city"]
    sample_scenarios = [
        {"age": 25, "occupation": "student", "city": "Boston"},
        {"age": 35, "occupation": "engineer", "city": "San Francisco"},
        {"age": 28, "occupation": "teacher", "city": "New York"},
    ]
    expr = filter_tool.create_filter(keys, sample_scenarios, "Keep only people over 30")
    print(f"Filter expression: {expr}")
    print()

    # Example 2: String matching
    print("Example 2: Filter by occupation")
    expr2 = filter_tool.create_filter(keys, sample_scenarios, "Only engineers")
    print(f"Filter expression: {expr2}")
    print()

    # Example 3: Complex criteria
    print("Example 3: Complex filter")
    expr3 = filter_tool.create_filter(
        keys, sample_scenarios, "People over 25 in technical roles"
    )
    print(f"Filter expression: {expr3}")
