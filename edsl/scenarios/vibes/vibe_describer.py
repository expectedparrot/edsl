"""
ScenarioList Vibe Describer: Generate descriptive titles and descriptions for scenario lists.

This module provides a VibeDescribe class that analyzes a scenario list and generates
a descriptive title and detailed description of what the scenario list represents.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any
from pydantic import BaseModel, Field
import os
import json
from dotenv import load_dotenv
from pathlib import Path
from ...base.openai_utils import create_openai_client


def find_dotenv_upwards(start_path: str | None = None) -> Path | None:
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


# ---------- 1) Pydantic schema for scenario list description ----------
class ScenarioListDescriptionSchema(BaseModel):
    """
    Schema for a scenario list description.

    Attributes
    ----------
    proposed_title : str
        A single sentence title that captures the essence of the scenario list
    description : str
        A paragraph-length description of what the scenario list represents
    """

    proposed_title: str = Field(
        description="A single sentence title that captures the essence of the scenario list"
    )
    description: str = Field(
        description="A paragraph-length description explaining what the scenario list represents, its purpose, and what data it contains"
    )


# ---------- 2) The main describer class ----------
@dataclass
class VibeDescribe:
    """
    Generate descriptive titles and descriptions for scenario lists.

    This class uses an LLM to analyze a scenario list and generate a descriptive
    title and detailed description of what the scenario list represents.

    Parameters
    ----------
    model : str
        The OpenAI model to use for generation (default: "gpt-4o")
    temperature : float
        Temperature for generation (default: 0.7)

    Examples
    --------
    >>> describer = VibeDescribe()  # doctest: +SKIP
    >>> result = describer.describe_scenario_list(scenario_data)  # doctest: +SKIP
    >>> print(result["proposed_title"])  # doctest: +SKIP
    >>> print(result["description"])  # doctest: +SKIP
    """

    model: str = "gpt-4o"
    temperature: float = 0.7

    def __post_init__(self):
        self.client = create_openai_client()  # reads OPENAI_API_KEY from env with proper error handling

    def describe_scenario_list(
        self,
        scenario_data: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Generate a title and description for a scenario list.

        Parameters
        ----------
        scenario_data : Dict[str, Any]
            Dictionary containing:
            - "keys": List of all unique keys across scenarios
            - "sample_values": Dict mapping each key to a list of sample values
            - "codebook": Optional dict mapping keys to their descriptions
            - "num_scenarios": Number of scenarios in the list

        Returns
        -------
        dict
            Dictionary with keys:
            - "proposed_title": A single sentence title for the scenario list
            - "description": A paragraph-length description of the scenario list

        Examples
        --------
        >>> describer = VibeDescribe(model="gpt-4o", temperature=0.7)  # doctest: +SKIP
        >>> data = {  # doctest: +SKIP
        ...     "keys": ["name", "age", "city"],  # doctest: +SKIP
        ...     "sample_values": {  # doctest: +SKIP
        ...         "name": ["Alice", "Bob", "Charlie"],  # doctest: +SKIP
        ...         "age": [25, 30, 35],  # doctest: +SKIP
        ...         "city": ["NYC", "SF", "LA"]  # doctest: +SKIP
        ...     },  # doctest: +SKIP
        ...     "num_scenarios": 100  # doctest: +SKIP
        ... }  # doctest: +SKIP
        >>> result = describer.describe_scenario_list(data)  # doctest: +SKIP
        >>> result["proposed_title"]  # doctest: +SKIP
        'Demographic Data Collection'
        """
        system = (
            "You are an expert data analyst and copywriter. "
            "Given information about a scenario list (a collection of parameterized data records), "
            "your task is to analyze the data and generate: "
            "\n\n"
            "1. A clear, concise title (single sentence) that captures the essence of the scenario list\n"
            "2. A detailed description (paragraph length) that explains:\n"
            "   - What the scenario list represents\n"
            "   - What data fields it contains\n"
            "   - What purpose or use case it serves\n"
            "   - What patterns or themes are evident in the data\n"
            "\n"
            "Guidelines for the title:\n"
            "- Should be a single sentence (not a fragment)\n"
            "- Should be clear and informative\n"
            "- Should capture the main theme or purpose of the data\n"
            "- Should be suitable as a dataset title or heading\n"
            "\n"
            "Guidelines for the description:\n"
            "- Should be one paragraph (3-5 sentences)\n"
            "- Should provide context about what the scenario list represents\n"
            "- Should mention the key fields/attributes included\n"
            "- Should explain what the data could be used for\n"
            "- Should be written in a professional, neutral tone\n"
            "- Should help users understand the nature and scope of the data\n"
        )

        user_prompt = {
            "task": "Analyze this scenario list and generate a title and description",
            "scenario_list_data": scenario_data,
            "instructions": (
                "Based on the keys, sample values, and metadata provided, generate a descriptive title "
                "and detailed description that accurately captures what this scenario list represents "
                "and what it could be used for."
            ),
        }

        resp = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_prompt, indent=2)},
            ],
            text_format=ScenarioListDescriptionSchema,
            temperature=self.temperature,
        )

        out = resp.output_parsed
        # Convert Pydantic model to dict
        return out.model_dump()


# ---------- 3) Example usage ----------
if __name__ == "__main__":
    describer = VibeDescribe(model="gpt-4o", temperature=0.7)

    # Example scenario list data
    sample_data = {
        "keys": ["name", "age", "city", "occupation"],
        "sample_values": {
            "name": ["Alice Johnson", "Bob Smith", "Charlie Brown"],
            "age": [25, 30, 35],
            "city": ["New York", "San Francisco", "Los Angeles"],
            "occupation": ["Engineer", "Designer", "Manager"],
        },
        "codebook": {
            "name": "Full name of the person",
            "age": "Age in years",
            "city": "City of residence",
            "occupation": "Current job title",
        },
        "num_scenarios": 100,
    }

    # Generate description
    result = describer.describe_scenario_list(sample_data)
    print("Title:", result["proposed_title"])
    print("\nDescription:", result["description"])
